"""语义检索: 用向量找「意思相近」的景点, 以及与之混合的相似景点排序。

与 recommend/content_based.py 的关系
------------------------------------
那条链路是**结构化**的: 标签重合、同分类、同城。它不需要任何模型, 冷启动也能出结果,
现在依然是兜底与测试实现。这里加的是**语义**一路: 描述文本的向量近邻, 能捞到
「标签不同但讲的是一类东西」的景点(比如「适合带孩子泡一天」与「亲子」)。

两者都不删。向量不可用时(没配 EMBEDDING_PROVIDER、库还没灌、维度不一致)
本模块整体退化成结构化那一路, 也就是**当前的线上行为** —— 新能力失败不该让旧能力变差。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Attraction, AttractionEmbedding
from ..recommend import content_based
from .vectors import cosine, decode

PUBLISHED = "published"

# 结构化分的归一化尺度。标签数没有上限, 结构化分严格来说没有理论最大值,
# 这里取 10 作为经验尺度 —— 它只影响向量分与结构化分的相对权重,
# 不影响「有没有结果」, 调它不会把结果调没。
STRUCT_SCALE = 10.0


def active_model(db: Session) -> str | None:
    """当前生效的向量模型: 已发布景点里向量行数最多的那个。

    不用配置反推而是查库: 配置与库不一致时(改了 EMBEDDING_MODEL 但还没重灌),
    以库为准才不会让检索整体空掉 —— 那种故障在界面上完全看不出来。
    """
    row = db.execute(
        select(AttractionEmbedding.model, func.count().label("rows"))
        .join(Attraction, Attraction.id == AttractionEmbedding.attraction_id)
        .where(Attraction.status == PUBLISHED)
        .group_by(AttractionEmbedding.model)
        .order_by(func.count().desc(), AttractionEmbedding.model.asc())
    ).first()
    return str(row[0]) if row else None


def model_dim(db: Session, model: str) -> int | None:
    """该模型在库里的维度。同一模型出现两种维度时返回 None(数据不可用)。

    返回 None 而不是"取最多的那个": 混了维度的向量表算出来的相似度是垃圾,
    只是不会报错。宁可降级到关键词检索, 也不给用户一堆看似合理的乱序结果。
    """
    rows = db.execute(
        select(AttractionEmbedding.dim, func.count())
        .where(AttractionEmbedding.model == model)
        .group_by(AttractionEmbedding.dim)
    ).all()
    if len(rows) != 1:
        return None
    return int(rows[0][0])


def accepts_width(db: Session, model: str, width: int) -> bool:
    """库内这份向量能不能拿去跟一根 width 维的查询向量比。

    model_dim 只看库内自身一不一致; 这一条管的是「查询向量与库内向量是不是同一套」。
    两者不等时 cos 会返回 0(见 vectors.cosine), 于是每一条都排不上, 表现成
    「没有找到语义相近的景点」—— 那句提示是错的: 真正的原因是换了向量模型但还没
    重灌, 该做的是重跑 scripts/build_embeddings.py。维度对不上不该被说成搜不到。
    """
    stored = model_dim(db, model)
    return stored is not None and stored == width


def load_vectors(db: Session, model: str) -> dict[int, list[float]]:
    """已发布景点的全部向量。90 条量级一次读完, 见 vectors.py 里的取舍说明。"""
    rows = db.execute(
        select(AttractionEmbedding.attraction_id, AttractionEmbedding.embedding)
        .join(Attraction, Attraction.id == AttractionEmbedding.attraction_id)
        .where(Attraction.status == PUBLISHED, AttractionEmbedding.model == model)
    ).all()
    return {int(attraction_id): decode(raw) for attraction_id, raw in rows}


def coverage(db: Session, model: str | None) -> tuple[int, int]:
    """(已向量化的已发布景点数, 已发布景点总数)。前端据此说明检索是不是全量可用。"""
    total = db.scalar(
        select(func.count()).select_from(Attraction).where(Attraction.status == PUBLISHED)
    ) or 0
    if not model:
        return 0, int(total)
    done = db.scalar(
        select(func.count())
        .select_from(AttractionEmbedding)
        .join(Attraction, Attraction.id == AttractionEmbedding.attraction_id)
        .where(Attraction.status == PUBLISHED, AttractionEmbedding.model == model)
    ) or 0
    return int(done), int(total)


def _fetch(db: Session, ids: list[int]) -> dict[int, Attraction]:
    if not ids:
        return {}
    rows = db.scalars(select(Attraction).where(Attraction.id.in_(ids))).all()
    return {row.id: row for row in rows}


def _neighbours(
    query_vector: list[float], vectors: dict[int, list[float]], *, exclude: int | None, limit: int
) -> list[tuple[int, float]]:
    """向量近邻, 按相似度降序、同分按 id 升序(结果可测)。"""
    scored = [
        (cosine(query_vector, vector), attraction_id)
        for attraction_id, vector in vectors.items()
        if attraction_id != exclude
    ]
    scored = [(value, attraction_id) for value, attraction_id in scored if value > 0]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [(attraction_id, value) for value, attraction_id in scored[:limit]]


def semantic_search(
    db: Session, query_vector: list[float], *, model: str, limit: int
) -> list[tuple[Attraction, float]]:
    """自然语言检索。返回 (景点, 相似度), 相似度降序。"""
    if not query_vector:
        return []
    vectors = load_vectors(db, model)
    if not vectors:
        return []
    top = _neighbours(query_vector, vectors, exclude=None, limit=max(limit * 3, limit))
    found = _fetch(db, [attraction_id for attraction_id, _ in top])
    results: list[tuple[Attraction, float]] = []
    for attraction_id, value in top:
        attraction = found.get(attraction_id)
        if attraction is None or attraction.status != PUBLISHED:
            continue
        results.append((attraction, value))
        if len(results) >= limit:
            break
    return results


def similar_attractions(
    db: Session,
    target: Attraction,
    *,
    limit: int,
    model: str | None,
    settings: Settings,
) -> list[Attraction]:
    """相似景点: 结构化分与向量分加权混合, 回落到纯结构化。

    权重来自配置(semantic_vector_weight / semantic_structured_weight), 见 config.py。
    """
    structured = content_based.scored_candidates(db, target, fetch=max(limit * 10, 50))
    fallback = [attraction for value, attraction in structured if value > 0][:limit]

    vectors = load_vectors(db, model) if model else {}
    target_vector = vectors.get(target.id)
    if not target_vector:
        # 目标景点自己没向量: 混合无从谈起, 直接给出与升级前逐条相同的结果
        return fallback

    strengths = {attraction.id: min(value / STRUCT_SCALE, 1.0) for value, attraction in structured}
    pool: dict[int, Attraction] = {attraction.id: attraction for _, attraction in structured}

    # 向量召回补充结构化池之外的邻居 —— 这正是语义这一路新增的覆盖
    neighbours = _neighbours(target_vector, vectors, exclude=target.id, limit=max(limit * 3, limit))
    missing = [attraction_id for attraction_id, _ in neighbours if attraction_id not in pool]
    pool.update(_fetch(db, missing))

    vector_weight = settings.semantic_vector_weight
    struct_weight = settings.semantic_structured_weight
    ranked: list[tuple[float, int, Attraction]] = []
    for attraction_id, attraction in pool.items():
        if attraction_id == target.id:
            continue
        similarity = cosine(target_vector, vectors.get(attraction_id, []))
        final = vector_weight * similarity + struct_weight * strengths.get(attraction_id, 0.0)
        if final > 0:
            ranked.append((final, attraction_id, attraction))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    merged = [attraction for _, _, attraction in ranked[:limit]]
    # 混合后一条都不剩(候选全无向量且结构化分为 0)时, 仍然退回结构化那一路
    return merged or fallback
