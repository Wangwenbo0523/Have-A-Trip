"""把推荐理由说成人话。

这一刀最容易越界 —— 让模型碰推荐, 它就有机会改结果。所以边界划得很硬:

模型**碰不到推荐结果**
  进来的 N 条推荐是后端**已经算好**的: 条目、顺序、分数都不变。
  模型只拿到每条的「景点名 + 模板理由」, 任务是把那句话改写得更顺。
  它没有机会增删改任何一条推荐 —— 返回值也只是 {slug: 文案} 的映射, 由调用方
  按自己手里那份列表去取, 取不到就用原来的理由。

护栏
----
1. 返回的 slug 必须 ∈ 输入集合, 多出来的丢掉 —— 模型塞不进新景点。
2. 少了的那几条用**原来的理由**兜底, 页面不会出现空理由。
3. 改写后的文案同样过数字溯源与主题词校验(复用 ask.verify): 理由里不许出现
   原文和景点档案里都没有的数字。
4. 超长的直接不要, 用原理由 —— 推荐位的一句话被撑成一段话就失去意义了。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ask import verify
from .client import LLMClient, LLMError

PROMPT_VERSION = "ai-polish-v1"

# 提示词里按这个要求; 超过硬上限的一律不要。
NOTE_TARGET = 40
NOTE_MAX = 60

DISCLAIMER = "推荐结果由本站的推荐算法给出, AI 只负责把理由写得更顺, 不参与挑选。"

SYSTEM_PROMPT = """你在给一个景点推荐位润色「为什么推荐它」这句话。

下面每一行是一条推荐: slug、景点名、系统算好的理由。
把每条理由改写成一句自然的、口语化的中文。

硬规则:
1. 只改写措辞, 不许改变意思。理由说是因为 A 相似, 就不能改成因为 B。
2. 不许添加理由里没有的事实 —— 评分、价格、距离、开放时间、人多不多都不许加。
3. 每条不超过 %d 字, 一句话。
4. 景点名原样保留。
5. slug 原样返回, 不许增删条目, 不许改变条数。
6. 只输出一个 JSON 对象: {"notes": [{"slug": "…", "note": "…"}]}
""" % NOTE_TARGET


@dataclass
class Polished:
    """slug -> 文案。没润色成功的条目这里仍然是原来的理由。"""

    notes: dict[str, str]
    polished: bool              # 是否真的过了一遍模型
    degraded: bool
    note: str = ""
    model: str | None = None
    dropped: list[str] = field(default_factory=list)


def build_system_prompt(entries: list[tuple[str, str, str]]) -> str:
    lines = [
        "- slug=%s | 景点名=%s | 理由: %s" % (slug, name, reason)
        for slug, name, reason in entries
    ]
    return SYSTEM_PROMPT + "\n推荐:\n" + "\n".join(lines)


def _clean(raw: object, entries: list[tuple[str, str, str]]) -> tuple[dict[str, str], list[str]]:
    """只收 slug 在输入集合里、且能溯源到原文与景点名的文案。"""
    if not isinstance(raw, list):
        return {}, []
    allowed = {slug: (name, reason) for slug, name, reason in entries}
    notes: dict[str, str] = {}
    dropped: list[str] = []

    for item in raw:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        note = item.get("note")
        if not isinstance(slug, str) or not isinstance(note, str):
            continue
        slug = slug.strip()
        note = " ".join(note.split())
        if slug not in allowed:
            dropped.append(slug or "(空 slug)")
            continue
        if slug in notes:
            continue
        if not note or len(note) > NOTE_MAX:
            dropped.append(slug)
            continue
        name, reason = allowed[slug]
        ok, why = verify(note, {"name": "景点名: " + name, "reason": "理由: " + reason})
        if not ok:
            dropped.append("%s(%s)" % (slug, why))
            continue
        notes[slug] = note
    return notes, dropped


def polish(client: LLMClient, entries: list[tuple[str, str, str]]) -> Polished:
    """entries: [(slug, 景点名, 原理由)]。返回值里每条都一定有文案。"""
    fallback = {slug: reason for slug, _, reason in entries}
    if not entries:
        return Polished(notes={}, polished=False, degraded=False)
    if not client.available:
        return Polished(notes=fallback, polished=False, degraded=True,
                        note="未配置模型, 沿用原来的推荐理由。")

    try:
        raw = client.chat_json(build_system_prompt(entries), "请按上面的规则改写。")
    except LLMError as exc:
        return Polished(notes=fallback, polished=False, degraded=True,
                        note="模型调用失败(%s), 沿用原来的推荐理由。" % exc,
                        model=client.model)

    notes, dropped = _clean(raw.get("notes"), entries)
    merged = {slug: notes.get(slug, reason) for slug, _, reason in entries}
    return Polished(
        notes=merged,
        polished=bool(notes),
        degraded=not notes,
        note="" if notes else "模型没有给出可用的改写, 沿用原来的推荐理由。",
        model=client.model,
        dropped=dropped,
    )