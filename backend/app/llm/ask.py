"""详情页追问: 用这个景点的档案回答一句话问题。

与 interpret.py 的关键区别: 那边模型产出的是**查询条件**, 这边模型要**写字**。
一旦模型写字就有编造空间, 所以这里的护栏更硬 —— 核心是「答案必须可溯源」。

护栏
----
1. 模型只能看到这个景点的档案字段, 提示词里写明「除了这份档案你没有别的信息」。
2. **数字必须可溯源**: 答案里出现的每个数字, 都要能在档案里找到同一个数字,
   否则整条作废, 换成后端拼的保守回答。票价、时长、年份、人数、评分这些
   最容易被编造的东西由这条拦住 —— 它是机械校验, 不依赖模型的自觉。
3. **档案里没有依据的主题**不能提。有数字的由第 2 条拦住; 「可以坐地铁过去」
   这类没有数字的由主题词这一关拦住。但档案自己写了这个词就放行(方案里确实
   写了「排队」「包车」), 依据仍然是我们自己的数据。
4. 模型自报引用了哪些字段(cited), 只有真实存在且非空的字段名才算数。
5. 任何一关没过、或模型不可用: 返回后端拼的保守回答, grounded=false, 不报错。

已知边界: 第 2、3 条拦的是「可机械判定的编造」。纯定性的编造(「这里很适合发呆」)
不在这两关的射程内, 只能靠提示词约束 —— 这是本方案刻意接受的上限。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..models import Attraction
from .client import LLMClient, LLMError

PROMPT_VERSION = "ai-ask-v1"

# 答案上限。要的是两句人话, 不是一篇导览词。
ANSWER_MAX = 300
# 提示词里给模型的字段数上限(方案步骤可能很多, 只带前若干个)
MAX_STEPS = 12

# 档案里**没有**对应字段的主题。模型提这些词时, 除非档案自己也写了这个词
# (比如方案里确实写了「排队」), 或者是否定式提及(「档案里没有开放时间」),
# 否则整条作废。有数字的其实第 2 条已经拦住, 这里是第二道。
UNSUPPORTED_TOPICS = (
    "开放时间", "营业时间", "开门时间", "关门时间", "闭馆", "休息日",
    "天气", "气温", "降雨", "降水", "雨季",
    "地铁", "公交", "巴士", "打车", "包车", "停车", "自驾", "机场", "火车站",
    "电话", "预约", "预订", "限流", "排队", "人流", "客流",
)

# 出现这些词说明是「档案里没有」这种否定式提及, 不是承诺。
NEGATIONS = (
    "没有", "未收录", "未核实", "不提供", "无法", "不含", "未提供",
    "不涉及", "不清楚", "不知道", "待补", "查不到", "未给出", "并不",
)

HERITAGE_CN = {"cultural": "文化遗产", "natural": "自然遗产", "mixed": "文化与自然双遗产"}
BUDGET_CN = {"free": "免费", "low": "较低", "mid": "中等", "high": "较高"}
A_LEVEL_CN = {"5A": "5A 级", "4A": "4A 级", "3A": "3A 级"}

# 可复述的字段。白名单之外的一切(状态、来源、经纬度、id、时间戳)都不给模型 ——
# 给了它也没用, 反而多一个被念出来的机会。
FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("name", "景点名称"),
    ("name_en", "英文名"),
    ("category", "分类"),
    ("city", "城市"),
    ("province", "省份"),
    ("address", "地址"),
    ("best_season", "最佳季节"),
    ("suggested_hours", "建议游览小时数"),
    ("ticket_price", "票价(0 表示免票)"),
    ("rating_avg", "平均评分"),
    ("rating_count", "评分人数"),
    ("a_level", "景区质量等级(GB/T 17775)"),
    ("heritage", "世界遗产类别"),
    ("tags", "标签"),
    ("summary", "一句话简介"),
    ("description", "详细介绍"),
    ("plans", "旅游方案"),
)

DISCLAIMER = "答案只依据本站景点档案里的字段; 档案里没有的信息一律不作答。"

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Answer:
    answer: str
    grounded: bool              # 这段答案有没有档案依据
    degraded: bool              # 是否降级(没配模型 / 调用失败 / 校验没过)
    note: str = ""
    cited: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    model: str | None = None

def _fmt(value: Any) -> str:
    """数值原样写出去。Decimal("4.70") 要变成 "4.7" 而不是 "4.70"。"""
    if isinstance(value, Decimal):
        return str(value.normalize())
    return str(value)


def _plans_text(attraction: Attraction) -> str:
    """把方案压成一段。步骤里含时长、限流、排队这类真实信息, 所以要点全带上。"""
    chunks: list[str] = []
    steps_left = MAX_STEPS
    for plan in attraction.plans:
        budget = BUDGET_CN.get(plan.budget_level or "", plan.budget_level or "")
        head = "%s(%s 天" % (plan.title, plan.days)
        if plan.best_for:
            head += "; 适合: %s" % plan.best_for
        if budget:
            head += "; 花费档次: %s" % budget
        head += "): %s" % plan.summary
        parts = [head]
        for step in plan.steps:
            if steps_left <= 0:
                break
            steps_left -= 1
            piece = "第 %d 天 %s" % (step.day_no, step.title)
            if step.duration_hours is not None:
                piece += "(%s 小时)" % _fmt(step.duration_hours)
            piece += ": " + step.detail
            if step.tip:
                piece += " 提示: " + step.tip
            parts.append(piece)
        chunks.append("; ".join(parts))
    return " || ".join(chunks)


def facts(attraction: Attraction) -> dict[str, str]:
    """这个景点可复述的档案字段。只收非空的 —— 空字段不进提示词, 免得模型拿它编。"""
    values: dict[str, str] = {
        "name": attraction.name,
        "name_en": attraction.name_en or "",
        "category": attraction.category.name if attraction.category else "",
        "city": attraction.city or "",
        "province": attraction.province or "",
        "address": attraction.address or "",
        "best_season": attraction.best_season or "",
        "suggested_hours": _fmt(attraction.suggested_hours) if attraction.suggested_hours is not None else "",
        "ticket_price": _fmt(attraction.ticket_price) if attraction.ticket_price is not None else "",
        "rating_avg": _fmt(attraction.rating_avg) if attraction.rating_count else "",
        "rating_count": str(attraction.rating_count) if attraction.rating_count else "",
        "a_level": A_LEVEL_CN.get(attraction.a_level or "", ""),
        "heritage": HERITAGE_CN.get(attraction.heritage or "", ""),
        "tags": "、".join(tag.name for tag in attraction.tags),
        "summary": attraction.summary or "",
        "description": attraction.description or "",
        "plans": _plans_text(attraction),
    }
    out: dict[str, str] = {}
    for key, label in FIELD_LABELS:
        value = values.get(key, "").strip()
        if value:
            out[key] = "%s: %s" % (label, value)
    return out


def build_system_prompt(sheet: dict[str, str]) -> str:
    keys = "、".join(sheet)
    body = "\n".join(sheet.values())
    return """你是「Have-A-Trip 景点大全」的景点资料助手。
下面是这个景点的**全部**档案。除了这份档案, 你没有别的信息。

硬规则:
1. 只用档案里写的内容回答。档案里没有的, 直接说「档案里没有这项信息」, 不要补常识, 不要猜。
2. 回答里不要出现档案里没有的数字 —— 价格、时长、年份、人数、评分都不行。
3. 档案里没有依据的话题一律不要提, 比如开放时间、天气、交通方式、预约方式、电话。
   档案里自己写了某个说法(方案里确实写了「排队」「包车」), 才可以照着说。
4. 用中文, 2 到 3 句, 总共不超过 %d 字。
5. 只输出一个 JSON 对象, 形如 {"answer": "…", "cited": ["字段名", …]}。
   cited 填你实际用到的字段名, 只能从这些里选: %s

档案:
%s""" % (ANSWER_MAX, keys, body)

def _numbers(text: str) -> set[float]:
    out: set[float] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        try:
            out.add(float(raw))
        except ValueError:
            continue
    return out


def _all_negated(answer: str, topic: str) -> bool:
    """topic 在答案里出现过的每一处, 都得是否定式提及, 才算通过。"""
    seen = False
    start = 0
    while True:
        index = answer.find(topic, start)
        if index < 0:
            return seen
        seen = True
        window = answer[max(0, index - 12): index + len(topic) + 8]
        if not any(marker in window for marker in NEGATIONS):
            return False
        start = index + len(topic)


def verify(answer: str, sheet: dict[str, str]) -> tuple[bool, str]:
    """机械校验: 答案能不能够到档案。返回 (是否通过, 没通过的原因)。"""
    source = "\n".join(sheet.values())

    allowed = _numbers(source)
    stray = sorted(value for value in _numbers(answer) if value not in allowed)
    if stray:
        return False, "答案里的数字在档案里找不到: %s" % "、".join(_fmt(v) for v in stray)

    for topic in UNSUPPORTED_TOPICS:
        if topic in answer and topic not in source and not _all_negated(answer, topic):
            return False, "提到了档案里没有依据的「%s」" % topic

    return True, ""


def _clean_cited(raw: Any, sheet: dict[str, str]) -> tuple[list[str], list[str]]:
    """模型自报引用了哪些字段。只有真实存在且非空的字段名才算数。"""
    if not isinstance(raw, list):
        return [], []
    cited: list[str] = []
    dropped: list[str] = []
    for item in raw:
        key = item.strip() if isinstance(item, str) else ""
        if not key:
            continue
        if key in sheet:
            if key not in cited:
                cited.append(key)
        else:
            dropped.append(key)
    return cited, dropped


def fallback_answer(attraction: Attraction) -> str:
    """模型不可用 / 说法无依据时用这个。它由档案字段直接拼出来, 所以一定有依据。"""
    bits: list[str] = []
    if attraction.best_season:
        bits.append("最佳季节 %s" % attraction.best_season)
    if attraction.suggested_hours is not None:
        bits.append("建议游览 %s 小时" % _fmt(attraction.suggested_hours))
    if attraction.ticket_price is not None:
        bits.append("票价 %s" % ("免费" if attraction.ticket_price == 0 else _fmt(attraction.ticket_price)))
    if attraction.city:
        bits.append("位于 %s" % attraction.city)
    head = "档案里没有能直接回答这个问题的内容。"
    if not bits:
        return head + "可以先看看上面的基本资料。"
    return head + "现有信息: " + "、".join(bits) + "。"


def ask(client: LLMClient, attraction: Attraction, question: str) -> Answer:
    """追问入口。任何模型侧问题都降级成档案摘录, 不抛给调用方。"""
    sheet = facts(attraction)

    if not client.available:
        return Answer(
            answer=fallback_answer(attraction),
            grounded=False,
            degraded=True,
            note="未配置模型, 下面是档案里的现成信息。",
        )

    try:
        raw = client.chat_json(build_system_prompt(sheet), question)
    except LLMError as exc:
        return Answer(
            answer=fallback_answer(attraction),
            grounded=False,
            degraded=True,
            note="模型调用失败(%s), 下面是档案里的现成信息。" % exc,
            model=client.model,
        )

    text = raw.get("answer")
    if not isinstance(text, str) or not text.strip():
        return Answer(
            answer=fallback_answer(attraction),
            grounded=False,
            degraded=True,
            note="模型没有给出答案, 下面是档案里的现成信息。",
            model=client.model,
        )

    answer = text.strip()[:ANSWER_MAX]
    cited, dropped = _clean_cited(raw.get("cited"), sheet)
    ok, why = verify(answer, sheet)
    if not ok:
        return Answer(
            answer=fallback_answer(attraction),
            grounded=False,
            degraded=True,
            note="模型的说法在档案里找不到依据(%s), 已换成档案里的现成信息。" % why,
            cited=cited,
            dropped=dropped,
            model=client.model,
        )

    return Answer(answer=answer, grounded=True, degraded=False, cited=cited, dropped=dropped, model=client.model)