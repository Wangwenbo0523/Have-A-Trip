"""行程生成的提示词。

两条硬约束写进 system, 不是「建议」:

1. **只能从候选清单里挑景点**。模型不许自己举出清单外的景点 ——
   这是幻觉的主要入口, 越界由 validator.py 整份拒掉。
2. **不许写票价、开放时间、距离、耗时这类事实性信息**。这些是易变信息, 库里有字段的
   以字段为准, 库里没有的宁可不说。编一个「门票 60 元」比不写要糟得多 ——
   用户会照做, 然后到了门口发现不对。

所以模型在这里的角色是**编排与措辞**, 不是知识来源。
"""
from __future__ import annotations

import json

from ..models import Attraction

SYSTEM_PROMPT = """你是行程编排助手。用户给一段需求, 你从候选景点清单里挑出合适的,
按天排成一份行程。

必须遵守:
1. 只能使用候选清单里出现过的 attraction_id。清单外的景点一律不许出现, 也不许
   用「类似的还有」这类说法带出来。
2. 不要写票价、开放时间、距离、交通耗时、天气。这些信息你没有可靠来源, 写了就是错的。
   只描述安排节奏与为什么这样排。
3. 每天 1 到 {max_per_day} 站, 天数严格等于 {days} 天, day_index 从 1 到 {days},
   同一天内 seq 从 1 连续编号。
4. 同一个景点在整份行程里最多安排一次。重复安排同一个景点等于白白占掉一天,
   宁可少排也不要重复。
5. 一天里的相邻站点要顺路或主题一致, 不要东一榔头西一棒槌。
6. 只输出 JSON, 不要任何解释文字。

输出格式:
{{"items": [{{"day_index": 1, "seq": 1, "attraction_id": 12,
  "note": "一句话说明这一站怎么安排", "reason": "一句话说明为什么它符合用户的需求"}}]}}"""

# 候选清单里每条给模型看多少字的简介。太长会把 prompt 撑大, 而挑选只需要一句话概括。
CANDIDATE_SUMMARY_CHARS = 120


def _candidate_line(attraction: Attraction) -> dict:
    """候选景点的一行。字段越少, 模型越不容易把无关字段抄进行程里。"""
    return {
        "attraction_id": attraction.id,
        "name": attraction.name,
        "city": attraction.city,
        "tags": sorted(tag.name for tag in attraction.tags if tag.name),
        "summary": " ".join((attraction.summary or "").split())[:CANDIDATE_SUMMARY_CHARS],
    }


def build_prompt(
    *,
    request_text: str,
    days: int,
    max_per_day: int,
    candidates: list[Attraction],
    feedback: str | None = None,
) -> tuple[str, str]:
    """返回 (system, user)。策略与 app/llm/interpret.py 一致: 候选来自库, 不由模型猜。

    feedback 是上一次输出被拒的原因。重试时把它写进 user, 模型才有机会改 —— 原样再发
    一遍同一份提示词, 拿回来的多半还是同一份坏输出(而且客户端那份按 (system, user)
    做键的缓存会直接把上次的结果还给你)。system 与输出格式一个字没动, 所以缓存的
    行程仍然有效, PROMPT_VERSION 不需要跟着动。
    """
    system = SYSTEM_PROMPT.format(days=days, max_per_day=max_per_day)
    listing = json.dumps(
        [_candidate_line(attraction) for attraction in candidates],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    user = (
        "用户需求: %s\n\n"
        "天数: %d\n"
        "候选景点清单(共 %d 个, attraction_id 只能从这里取):\n%s"
        % (request_text, days, len(candidates), listing)
    )
    if feedback:
        user += (
            "\n\n上一次的输出不合法, 已被拒绝: %s\n"
            "请重新输出一份完整 JSON: day_index 必须覆盖 1..%d 的每一天, "
            "同一天内 seq 从 1 连续编号, attraction_id 只能取自上面的候选清单。"
            % (feedback, days)
        )
    return system, user
