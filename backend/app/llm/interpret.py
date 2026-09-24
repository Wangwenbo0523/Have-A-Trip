"""把一句话需求解析成 /attractions 的查询条件。

护栏(本项目 AI 部分最重要的一段)
--------------------------------
1. 模型只产出查询条件, 不产出景点条目 —— 结果永远由数据库查出来,
   所以它根本没有编造景点的机会。
2. 白名单 + 双向校验: 只接受这几个字段, 取值还必须能在库里对上; 对不上的一律丢掉,
   并在 note 里说明。模型说 category=雪山 这种库里没有的分类, 不会有任何效果。
   取值本身合法、只是被写成一整串(或用顿号隔开)时先拆开再比, 不整条丢掉。
3. 解析失败(没配模型 / 超时 / 不是 JSON)不是错误, 而是降级: 退回关键词检索。
4. 票价、开放时间这类易变信息只存在于库里(而且库里刻意不给具体价格),
   提示词明确禁止在 note 里承诺这些。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attraction, Category, Tag
from .client import LLMClient, LLMError

PROMPT_VERSION = "ai-search-v1"

# 只有这些字段会被采信, 其余一律丢弃
ALLOWED_FIELDS = ("category", "tag", "grade", "city", "q", "sort")
GRADES = ("5A", "4A", "3A", "heritage")
SORTS = ("rating", "newest", "name")
MAX_Q = 60
NOTE_MAX = 60
# 模型偶尔把多个取值写成一整串: "world-heritage, island" / "海岛、世界遗产"。
VALUE_SEPARATORS = re.compile(r"[,、;；/|]+")
SYSTEM_PROMPT = """你是「Have-A-Trip 景点大全」的查询意图解析器。
把用户的一句话需求, 转成下面这套查询条件的 JSON。

只允许输出这些字段(都可以省略):
- category: 分类 slug, 只能从「分类」列表里选
- tag: 标签 slug, 只能从「标签」列表里选
- grade: 等级, 只能是 "5A" / "4A" / "3A" / "heritage"
- city: 城市, 只能从「城市」列表里选
- q: 关键词, 用于匹配景点名称与简介, 不超过 %d 字
- sort: 排序, 只能是 "rating"(评分) / "newest"(最新) / "name"(名称)
- note: 一句话向用户说明你是怎么理解的(中文, 不超过 40 字)

硬规则:
1. 不确定的字段直接省略, 不要猜, 不要编造。
2. 只能用上面列出的取值, 列表里没有的一律不要输出。
3. 不要输出景点名称 —— 景点由数据库检索, 不由你挑选。
4. 不要在 note 里承诺票价、开放时间、天气、交通等易变信息。
5. 只输出 JSON 对象本身, 不要加解释文字或代码块标记。
""" % MAX_Q


@dataclass
class Interpretation:
    """解析结果。filters 可以直接喂给 attractions.build_query。"""

    filters: dict[str, Any]
    note: str
    interpreted: bool          # 是否真的过了模型
    degraded: bool             # 是否处于降级(退回关键词检索)
    model: str | None = None
    dropped: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None


def vocabulary(db: Session) -> dict[str, Any]:
    """从库里取当前可用的取值。提示词据此生成 —— 模型看到的是真实存在的选项。"""
    categories = db.execute(select(Category.slug, Category.name).order_by(Category.sort)).all()
    tags = db.execute(select(Tag.slug, Tag.name).order_by(Tag.slug)).all()
    cities = [
        row[0]
        for row in db.execute(
            select(Attraction.city).where(Attraction.city.is_not(None)).distinct()
        ).all()
        if row[0]
    ]
    return {
        "categories": [(str(a), str(b)) for a, b in categories],
        "tags": [(str(a), str(b)) for a, b in tags],
        "cities": sorted(str(c) for c in cities),
    }


def build_system_prompt(vocab: dict[str, Any]) -> str:
    categories = "、".join("%s(%s)" % (slug, name) for slug, name in vocab["categories"]) or "(无)"
    tags = "、".join("%s(%s)" % (slug, name) for slug, name in vocab["tags"]) or "(无)"
    cities = "、".join(vocab["cities"]) or "(无)"
    return SYSTEM_PROMPT + "\n分类: " + categories + "\n标签: " + tags + "\n城市: " + cities


def _normalize_city(value: str, cities: list[str]) -> str | None:
    """模型常写「杭州」而库里是「杭州市」。只在能唯一对上时才认。"""
    value = value.strip()
    if not value:
        return None
    if value in cities:
        return value
    hits = [c for c in cities if value in c or c in value]
    return hits[0] if len(hits) == 1 else None


def split_values(value: str) -> list[str]:
    """把写成一整串的多个取值拆开, 去掉空段。"""
    return [part.strip() for part in VALUE_SEPARATORS.split(value) if part.strip()]


def validate(raw: dict[str, Any], vocab: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """把模型的输出收敛到白名单 + 库里真实存在的取值。返回 (filters, dropped)。"""
    filters: dict[str, Any] = {}
    dropped: list[str] = []

    def written(name: str) -> str | None:
        value = raw.get(name)
        return value.strip() if isinstance(value, str) and value.strip() else None

    # 枚举字段: 多值先按分隔符拆开, 取**第一个**能在白名单里对上的。
    # dropped 里报的是模型写的原值(不拆开) —— 拆开后的碎片报给用户只会更费解。
    for name, allowed in (
        ("category", {slug for slug, _ in vocab["categories"]}),
        ("tag", {slug for slug, _ in vocab["tags"]}),
        ("grade", set(GRADES)),
    ):
        raw_value = written(name)
        if not raw_value:
            continue
        hit = next((item for item in split_values(raw_value) if item in allowed), None)
        if hit:
            filters[name] = hit
        else:
            dropped.append("%s=%s" % (name, raw_value))

    # 城市走的是模糊匹配(模型常写「杭州」而库里是「杭州市」), 所以逐个候选去归一化
    raw_city = written("city")
    if raw_city:
        city = None
        for candidate in split_values(raw_city):
            city = _normalize_city(candidate, vocab["cities"])
            if city:
                break
        if city:
            filters["city"] = city
        else:
            dropped.append("city=%s" % raw_city)

    q = written("q")
    if q:
        filters["q"] = q[:MAX_Q]

    sort = written("sort")
    filters["sort"] = sort if sort in SORTS else "rating"

    # 模型多写的字段(比如 status / lat / 景点名)一律不认, 在这里就被丢掉了
    for key in raw:
        if key not in ALLOWED_FIELDS and key != "note":
            dropped.append(str(key))

    return filters, dropped


def _clean_note(raw: Any, dropped: list[str]) -> str:
    """note 是给用户看的一句解释。模型没给就自己写一句 —— 不能留空。"""
    note = raw.strip() if isinstance(raw, str) else ""
    note = note[:NOTE_MAX]
    if dropped:
        return (note or "已按你的描述筛选。") + "；已忽略不认识的取值: " + "、".join(dropped[:3])
    return note or "已按你的描述筛选。"


def interpret(db: Session, client: LLMClient, query: str) -> Interpretation:
    """解析用户输入。任何模型侧失败都降级为关键词检索, 不抛给调用方。"""
    fallback = {"q": query[:MAX_Q], "sort": "rating"}
    if not client.available:
        # 默认配置(LLM_PROVIDER=none)就走这条。note 不能留空:
        # 前端只看到 degraded=true 而没有一句解释, 用户会以为是自己输错了。
        return Interpretation(
            filters=fallback,
            note="未配置模型, 已退回关键词检索。",
            interpreted=False,
            degraded=True,
        )

    vocab = vocabulary(db)
    try:
        raw = client.chat_json(build_system_prompt(vocab), query)
    except LLMError as exc:
        return Interpretation(
            filters=fallback,
            note="模型调用失败(%s), 已退回关键词检索。" % exc,
            interpreted=False,
            degraded=True,
            model=client.model,
        )

    filters, dropped = validate(raw, vocab)
    # 一个条件都没解析出来时, 返回全量景点没有意义 —— 退回关键词检索, 结果更贴用户那句话
    if not filters.get("q") and len(filters) <= 1:
        return Interpretation(
            filters=fallback,
            note=_clean_note(raw.get("note"), dropped) + " 已退回关键词检索。",
            interpreted=True,
            degraded=True,
            model=client.model,
            dropped=dropped,
            raw=raw,
        )
    return Interpretation(
        filters=filters,
        note=_clean_note(raw.get("note"), dropped),
        interpreted=True,
        degraded=False,
        model=client.model,
        dropped=dropped,
        raw=raw,
    )