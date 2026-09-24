"""一句话检索: 自然语言 -> 查询条件 -> 库里查景点。

护栏的完整说明在 app/llm/interpret.py 开头, 这里只说这个模块的职责:
1. 解析出来的条件交给 attractions.build_query —— 与用户手点筛选共用同一条查询路径,
   不存在「AI 专用」的另一套宽松查询;
2. 景点条目只从库里取, 模型拿不到结果集, 所以它没有编造景点的机会;
3. 模型不可用 / 超时 / 返回不是 JSON, 一律降级成关键词检索, 不往用户面前抛 500;
4. 从库里的条件一条都查不到时, 先摘条件再找语义近邻(见 _relax / _semantic_hits),
   每一步都在 relaxed / semantic_fallback / note 里说清楚放的是什么宽。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..llm import (
    EmbeddingClient,
    EmbeddingError,
    LLMClient,
    get_embedding_client,
    get_llm_client,
)
from ..llm.ask import DISCLAIMER as ASK_DISCLAIMER
from ..llm.ask import ask
from ..llm.interpret import interpret
from ..llm.polish import DISCLAIMER as POLISH_DISCLAIMER
from ..llm.polish import polish
from ..models import AppUser, Attraction
from ..recommend import service as recommend_service
from ..search import semantic
from ..schemas import (
    AIAskIn,
    AIAskOut,
    AIFilters,
    AIRecommendNotesIn,
    AIRecommendNotesOut,
    AIRefinedReason,
    AISearchIn,
    AISearchOut,
    AIStatusOut,
)
from . import attractions as attractions_api

router = APIRouter(prefix="/ai", tags=["ai"])

# 这句话必须显示在结果上方。口径与 docs/LICENSE-AUDIT.md「AI 与模型条款」一致:
# 模型只做需求理解, 结果集与排序都由本站在库数据决定。
DISCLAIMER = "结果全部来自本站景点档案, AI 只参与理解你这句需求。"

# 空结果时摘条件的候选, 以及摘的顺序。顺序只在"摘掉之后条数一样多"时用来分先后:
# 摘哪个由 _relax 算出来的条数决定, 不由这个元组决定。
RELAX_ORDER = ("grade", "tag", "category", "city")
# 给用户看的字段名 —— 内部字段名(grade / tag)不该出现在界面上
RELAX_LABELS = {"grade": "等级", "tag": "标签", "category": "分类", "city": "城市"}


def _append_note(note: str, text: str) -> str:
    """把一句补充说明接在 note 后面。

    note 自带句号, 直接拼会写成「。；」。把它的收尾句号换成"；"再拼, 读起来是一句话。
    """
    base = note.rstrip()
    if base.endswith("。"):
        base = base[:-1]
    return ("%s；%s" % (base, text)) if base else text


def _statement_for(filters: dict[str, Any]):
    """条件字典 -> 查询语句。与用户手点筛选共用 build_query 这一条路径。"""
    return attractions_api.build_query(
        category=filters.get("category"),
        city=filters.get("city"),
        tag=filters.get("tag"),
        grade=filters.get("grade"),
        q=filters.get("q"),
    )


def _count(db: Session, filters: dict[str, Any]) -> int:
    return attractions_api.count_of(db, _statement_for(filters))


def _relax(db: Session, filters: dict[str, Any]) -> tuple[dict[str, Any], list[str], int]:
    """一条都查不到时逐条摘条件重查。返回 (生效条件, 摘掉的条件, 条数)。

    每次摘掉一个条件, 取"摘完之后剩得最少"的那种摘法。为什么是剩得最少而不是最多:
    放宽是为了让用户看到他想要的那件东西, 不是为了给他一堆东西。
    「下龙 + 5A」摘掉 5A 只剩 1 条(下龙湾), 摘掉下龙剩 32 条(全国的 5A) ——
    前者才是那句话的意思, 后者只是把所有限制都放开了。

    最后一个条件不摘: 摘光了等于把整库倒给用户, 那不是放宽, 是答非所问。
    """
    applied = dict(filters)
    total = _count(db, applied)
    relaxed: list[str] = []
    while total == 0 and len(applied) > 1:
        options: list[tuple[int, int, str, dict[str, Any]]] = []
        for name in RELAX_ORDER:
            if name not in applied:
                continue
            trial = {key: value for key, value in applied.items() if key != name}
            hits = _count(db, trial)
            if hits > 0:
                options.append((hits, RELAX_ORDER.index(name), name, trial))
        if not options:
            break
        # 元组前两项就够定序(name 互不相同), 不会比到 dict 上
        total, _, name, trial = min(options, key=lambda row: row[:3])
        applied = trial
        relaxed.append(name)
    return applied, relaxed, total


def _semantic_hits(
    db: Session, embedding: EmbeddingClient, query: str, limit: int
) -> list[tuple[Attraction, float]]:
    """向量近邻兜底。任何一步不可用都返回空 —— 调用方维持"没找到", 不报错。"""
    model = semantic.active_model(db)
    if not embedding.available or not model or semantic.model_dim(db, model) is None:
        return []
    try:
        vector = embedding.embed_one(query)
    except EmbeddingError:
        return []
    return semantic.semantic_search(db, vector, model=model, limit=limit)


@router.get("/status", response_model=AIStatusOut, summary="AI 入口是否可用")
def ai_status(
    client: LLMClient = Depends(get_llm_client),
    embedding: EmbeddingClient = Depends(get_embedding_client),
    db: Session = Depends(get_db),
) -> AIStatusOut:
    """前端据此决定要不要显示「用一句话找景点」。未配置模型时 available=false。"""
    model = semantic.active_model(db)
    embedded, published = semantic.coverage(db, model)
    return AIStatusOut(
        available=client.available,
        provider=client.provider,
        model=client.model or None,
        embedding_available=embedding.available and embedded > 0,
        embedding_model=embedding.model or None,
        embedded=embedded,
        published=published,
        disclaimer=DISCLAIMER,
    )


@router.post("/search", response_model=AISearchOut, summary="用一句话找景点")
def ai_search(
    payload: AISearchIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: LLMClient = Depends(get_llm_client),
    embedding: EmbeddingClient = Depends(get_embedding_client),
) -> AISearchOut:
    """降级不是错误: 模型不可用时 filters 里只有 q=用户原话, 照常返回 200。

    前端据 degraded 决定要不要提示「已退回关键词检索」。

    一条都查不到时依次试两步兜底, 都是"宁可给个接近的, 也不给一张空页":
    1. 逐条摘条件重查, 在 relaxed 里说明摘掉了什么(见 _relax);
    2. 还空就找语义近邻, 用 semantic_fallback 标出来。
    两步都不成, 就如实返回空 —— 空结果本身也是答案。
    """
    outcome = interpret(db, client, payload.query)
    filters = {key: value for key, value in outcome.filters.items() if key != "sort"}
    sort = outcome.filters.get("sort") or "rating"
    limit = min(payload.size or settings.default_page_size, settings.max_page_size)

    applied, relaxed, total = _relax(db, filters)
    note = outcome.note
    if relaxed:
        labels = "、".join(RELAX_LABELS.get(name, name) for name in relaxed)
        note = _append_note(note, "原来的条件一条都没有, 已去掉「%s」再查。" % labels)

    semantic_fallback = False
    items: list[Any] = []
    if total > 0:
        items = attractions_api.page_of(
            db, _statement_for(applied), page=payload.page, limit=limit, sort=sort
        )
    elif payload.page <= 1:
        # 语义兜底只在第一页做: 它给的是"最接近的这几条", 本身没有第二页可翻
        hits = _semantic_hits(db, embedding, payload.query, limit)
        if hits:
            items = [attraction for attraction, _ in hits]
            total = len(items)
            semantic_fallback = True
            note = _append_note(note, "原来的条件一条都没有, 以下是按意思找的最接近的几条。")

    return AISearchOut(
        query=payload.query,
        interpreted=outcome.interpreted,
        degraded=outcome.degraded,
        model=outcome.model,
        note=note,
        filters=AIFilters(
            category=applied.get("category"),
            tag=applied.get("tag"),
            grade=applied.get("grade"),
            city=applied.get("city"),
            q=applied.get("q"),
            sort=sort,
        ),
        items=items,
        page=payload.page,
        size=limit,
        total=total,
        relaxed=relaxed,
        semantic_fallback=semantic_fallback,
        disclaimer=DISCLAIMER,
    )


@router.post("/ask", response_model=AIAskOut, summary="就某个景点问一句")
def ai_ask(
    payload: AIAskIn,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
) -> AIAskOut:
    """答案只依据这个景点的档案字段, 档案里没有的一律不作答。

    模型不可用 / 说法查不到依据时降级成档案摘录, 仍然是 200 —— 追问失败不该表现为报错页。
    """
    attraction = attractions_api.find_attraction(db, payload.slug)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")

    outcome = ask(client, attraction, payload.question)
    return AIAskOut(
        slug=attraction.slug,
        question=payload.question,
        grounded=outcome.grounded,
        degraded=outcome.degraded,
        model=outcome.model,
        answer=outcome.answer,
        note=outcome.note,
        cited=outcome.cited,
        dropped=outcome.dropped,
        disclaimer=ASK_DISCLAIMER,
    )


@router.post("/recommend-notes", response_model=AIRecommendNotesOut, summary="润色推荐理由")
def ai_recommend_notes(
    payload: AIRecommendNotesIn,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
) -> AIRecommendNotesOut:
    """只改写「为什么推荐它」这句话的措辞。

    **推荐结果本身不交给模型**: 条目、顺序、分数都由 /recommendations 决定,
    这里拿到的只是已定好的那几条, 模型碰不到挑选与排序。模型不可用时沿用原来的理由。
    """
    if payload.user_id is not None and payload.device_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user_id 与 device_id 只能传一个")

    user_id = payload.user_id
    if user_id is None and payload.device_id is not None:
        # 没见过的设备不是错误, 与 /recommendations 同口径: 按新用户处理
        user = db.scalar(select(AppUser).where(AppUser.device_id == payload.device_id))
        user_id = user.id if user else None
    if user_id is not None and db.get(AppUser, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    items = recommend_service.get_recommendations(db, user_id, payload.limit)
    entries = [(item.attraction.slug, item.attraction.name, item.reason) for item in items]
    outcome = polish(client, entries)

    return AIRecommendNotesOut(
        polished=outcome.polished,
        degraded=outcome.degraded,
        model=outcome.model,
        note=outcome.note,
        reasons=[AIRefinedReason(slug=slug, note=text) for slug, text in outcome.notes.items()],
        dropped=outcome.dropped,
        disclaimer=POLISH_DISCLAIMER,
    )
