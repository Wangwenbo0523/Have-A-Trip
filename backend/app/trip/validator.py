"""行程输出的校验: 模型说了不算, 候选集说了算。

这一层是幻觉的唯一防线, 所以规则写成显式的表, 每条都有确定的失败判定 —— 没有
「看起来差不多就放过去」的模糊地带。与 app/llm/interpret.py 的白名单校验同一思路:
模型只能从给定的集合里挑, 挑了集合外的值就整份拒掉, 而不是挑出来再偷偷过滤。

为什么整份拒掉而不是丢掉越界的那一条: 越界说明模型在编景点, 那么它没越界的那几条
也没有可信度可言。丢掉单条会让用户拿到一份"看起来正常"的行程, 里面一半是编的。
同一个景点被排进两天也按整份拒掉: 它不是幻觉, 但一格一天的行程里重复安排
等于把这一天浪费掉, 而用户在页面上看不出这是模型偷懒 —— 这种"看着正常"的错误
比明显报错更难发现。拒掉之后 service 会把原因回灌进提示词重来一次。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 说明文字的长度上限。note/reason 是给用户看的一句话, 不是段落。
ITEM_TEXT_MAX = 120

# 兜底文案。模型没给 reason 时用它 —— reason 是接口契约里的必填字段,
# 不能因为模型偷懒就让前端拿到 null。
DEFAULT_NOTE = "按行程顺序安排。"
DEFAULT_REASON = "与你的描述相符。"


class ValidationError(RuntimeError):
    """模型输出不满足契约。调用方据此把行程置为 failed, 不落半截数据。"""


@dataclass(frozen=True)
class ValidatedItem:
    day_index: int
    seq: int
    attraction_id: int
    note: str
    reason: str


def _text(value: Any, fallback: str) -> str:
    """说明文字: 压空白、截断、空则兜底。不接受非字符串。"""
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.split())[:ITEM_TEXT_MAX]
    return cleaned or fallback


def _int(value: Any, field: str) -> int:
    # 模型常把数字写成字符串, 这里容忍; 但 true/None/小数一律不认
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValidationError("%s 不是整数: %r" % (field, value))
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError("%s 不是整数: %r" % (field, value)) from exc


def validate(
    raw: dict[str, Any],
    *,
    candidate_ids: set[int],
    days: int,
    max_per_day: int,
    candidates_sufficient: bool,
) -> tuple[list[ValidatedItem], str | None]:
    """校验并归一化模型输出。返回 (条目, 降级说明)。

    candidates_sufficient 为假时(候选景点数比天数还少)允许只覆盖部分天, 并在第二个
    返回值里给出说明 —— 这时"排不满"是数据不够, 不是模型的问题。
    """
    items = raw.get("items")
    if not isinstance(items, list):
        raise ValidationError("模型没有给出 items 数组")
    if not items:
        # 空行程按失败处理: 成功返回一份空行程, 用户只会以为是产品坏了
        raise ValidationError("模型返回了 0 条行程")

    parsed: list[ValidatedItem] = []
    # attraction_id -> 它第一次出现在第几条(1 起), 用来报出冲突的两条位置
    seen_at: dict[int, int] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError("第 %d 条不是对象" % (index + 1))

        attraction_id = _int(item.get("attraction_id"), "attraction_id")
        if attraction_id not in candidate_ids:
            raise ValidationError(
                "attraction_id=%d 不在候选集里(共 %d 个候选)" % (attraction_id, len(candidate_ids))
            )

        day_index = _int(item.get("day_index"), "day_index")
        if not 1 <= day_index <= days:
            raise ValidationError("day_index=%d 超出 1..%d" % (day_index, days))

        seq = _int(item.get("seq"), "seq")
        if seq < 1:
            raise ValidationError("seq=%d 必须从 1 起" % seq)

        repeated_at = seen_at.get(attraction_id)
        if repeated_at is not None:
            raise ValidationError(
                "attraction_id=%d 被排了两次(第 %d 条与第 %d 条): 同一次行程里每个景点最多出现一次; "
                "候选景点不够时可以少排几站, 不要用重复安排来凑数"
                % (attraction_id, repeated_at, index + 1)
            )
        seen_at[attraction_id] = index + 1

        parsed.append(
            ValidatedItem(
                day_index=day_index,
                seq=seq,
                attraction_id=attraction_id,
                note=_text(item.get("note"), DEFAULT_NOTE),
                reason=_text(item.get("reason"), DEFAULT_REASON),
            )
        )

    if len(parsed) > days * max_per_day:
        raise ValidationError("总条数 %d 超过 %d 天上限 %d" % (len(parsed), days, days * max_per_day))

    by_day: dict[int, list[ValidatedItem]] = {}
    for item in parsed:
        by_day.setdefault(item.day_index, []).append(item)

    for day_index, entries in by_day.items():
        if len(entries) > max_per_day:
            raise ValidationError("第 %d 天有 %d 站, 超过每天 %d 站" % (day_index, len(entries), max_per_day))
        # 同一天内 seq 必须从 1 连续, 否则"第几站"就没有确定含义
        ordered = sorted(entry.seq for entry in entries)
        if ordered != list(range(1, len(entries) + 1)):
            raise ValidationError(
                "第 %d 天的 seq 不是从 1 连续: %s" % (day_index, sorted(entry.seq for entry in entries))
            )

    covered = sorted(by_day)
    degraded_note: str | None = None
    if not candidates_sufficient:
        # 候选不够排满: 允许缺天, 但缺的必须是尾部 —— 不能出现"只有第 1、3 天"
        if covered != list(range(1, len(covered) + 1)):
            raise ValidationError("天数不连续: %s" % covered)
        if len(covered) < days:
            degraded_note = (
                "库内可编排的景点不足, 只排出了 %d 天(共 %d 天)。" % (len(covered), days)
            )
    elif covered != list(range(1, days + 1)):
        raise ValidationError("天数没有覆盖 1..%d, 实际是 %s" % (days, covered))

    parsed.sort(key=lambda entry: (entry.day_index, entry.seq))
    return parsed, degraded_note
