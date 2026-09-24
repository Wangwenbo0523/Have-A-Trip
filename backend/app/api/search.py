"""语义检索: 把一句话向量化, 与景点描述的向量比相似度。

与 /ai/search 的分工
--------------------
/ai/search 要一个对话模型把句子解析成筛选条件, 结果走结构化查询;
这里**完全不需要对话模型** —— 只要配了向量模型就能用。两者互补:
前者能听懂「不要爬山的」这类条件, 后者能听懂「适合发呆一下午的地方」这类没法写成
SQL 的描述。

向量不可用时**不是返回空**, 而是就地退回关键词检索, 并把 degraded 标出来。
用户要的是"找到景点", 不是"看到一条降级提示"; 把兜底做在服务端, 前端只需要
决定要不要提示一句。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..llm import EmbeddingClient, EmbeddingError, get_embedding_client
from ..schemas import AttractionListItem, SemanticHit, SemanticSearchIn, SemanticSearchOut
from ..search import semantic
from . import attractions as attractions_api

router = APIRouter(prefix="/search", tags=["search"])

DISCLAIMER = "语义检索按景点描述的相似度排序, 结果全部来自本站景点档案。"


def _keyword_fallback(
    db: Session, *, query: str, limit: int, note: str, embedded: int, published: int
) -> SemanticSearchOut:
    statement = attractions_api.build_query(q=query)
    rows = attractions_api.page_of(db, statement, page=1, limit=limit, sort="rating")
    return SemanticSearchOut(
        query=query,
        degraded=True,
        model=None,
        note=note,
        embedded=embedded,
        published=published,
        items=[
            SemanticHit(attraction=AttractionListItem.model_validate(row), match="keyword")
            for row in rows
        ],
        total=len(rows),
        disclaimer=DISCLAIMER,
    )


@router.post("/semantic", response_model=SemanticSearchOut, summary="按意思找景点")
def semantic_search(
    payload: SemanticSearchIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    embedding: EmbeddingClient = Depends(get_embedding_client),
) -> SemanticSearchOut:
    """向量不可用 / 库内没有向量 / 维度不一致, 一律退回关键词检索, 仍然是 200。"""
    limit = min(payload.limit or settings.semantic_default_limit, settings.semantic_max_limit)
    model = semantic.active_model(db)
    embedded, published = semantic.coverage(db, model)

    def fallback(note: str) -> SemanticSearchOut:
        return _keyword_fallback(
            db, query=payload.query, limit=limit, note=note, embedded=embedded, published=published
        )

    if not embedding.available:
        return fallback("未配置向量模型, 已退回关键词检索。")
    if not model:
        return fallback("库内还没有景点向量, 请先跑一次向量化任务; 已退回关键词检索。")
    if semantic.model_dim(db, model) is None:
        # 同一个模型下混了两种维度, 算出来的相似度是垃圾。宁可退回关键词。
        return fallback("向量维度不一致(需要重灌), 已退回关键词检索。")

    try:
        vector = embedding.embed_one(payload.query)
    except EmbeddingError as exc:
        return fallback("向量服务不可用(%s), 已退回关键词检索。" % exc)

    hits = semantic.semantic_search(db, vector, model=model, limit=limit)
    if not hits:
        return fallback("没有找到语义相近的景点, 已退回关键词检索。")

    return SemanticSearchOut(
        query=payload.query,
        degraded=False,
        model=model,
        note="按景点描述与你这句话的语义相似度排序。",
        embedded=embedded,
        published=published,
        items=[
            SemanticHit(
                attraction=AttractionListItem.model_validate(attraction),
                score=round(score, 4),
                match="semantic",
            )
            for attraction, score in hits
        ],
        total=len(hits),
        disclaimer=DISCLAIMER,
    )
