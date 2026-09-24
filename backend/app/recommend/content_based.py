"""内容相似度。冷启动阶段的推荐主力, 也是详情页「相似景点」的实现。

打分只看静态字段——标签重合、同分类、同城——不需要任何用户行为,
所以在还没有交互数据时也能给出非空且说得通的结果。

权重集中在这里, 便于后续调参:
    tag_overlap * 3 + same_category * 2 + same_city * 1 (+ 评分微调)
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import Attraction, attraction_tag

W_TAG = 3.0
W_CATEGORY = 2.0
W_CITY = 1.0
W_RATING = 0.2

PUBLISHED = "published"


def _candidates(db: Session, target: Attraction, fetch: int) -> list[Attraction]:
    """取一批候选: 同分类 或 同城 或 至少共享一个标签。"""
    tag_ids = [tag.id for tag in target.tags]

    conditions = [Attraction.category_id == target.category_id]
    if target.city:
        conditions.append(Attraction.city == target.city)

    stmt = (
        select(Attraction)
        .where(Attraction.status == PUBLISHED, Attraction.id != target.id, or_(*conditions))
        .options(selectinload(Attraction.tags), selectinload(Attraction.images))
        .order_by(Attraction.rating_avg.desc(), Attraction.id.asc())
        .limit(fetch)
    )
    rows = list(db.scalars(stmt).all())

    if tag_ids:
        # 共享至少一个标签的景点。直接把这个 Select 交给 in_(), 不要先取 .c ——
        # SelectBase.c 在 SQLAlchemy 2.0 已废弃, 它会隐式建子查询。
        shared = select(attraction_tag.c.attraction_id).where(
            attraction_tag.c.tag_id.in_(tag_ids)
        )
        extra = (
            select(Attraction)
            .where(
                Attraction.status == PUBLISHED,
                Attraction.id != target.id,
                Attraction.id.in_(shared),
            )
            .options(selectinload(Attraction.tags), selectinload(Attraction.images))
            .order_by(Attraction.rating_avg.desc(), Attraction.id.asc())
            .limit(fetch)
        )
        seen = {a.id for a in rows}
        rows.extend(a for a in db.scalars(extra).all() if a.id not in seen)

    return rows


def score(target: Attraction, other: Attraction) -> float:
    """target 与 other 的相似度。分数本身无绝对意义, 只用来排序。"""
    target_tags = {t.slug for t in target.tags}
    other_tags = {t.slug for t in other.tags}
    overlap = len(target_tags & other_tags)

    value = W_TAG * overlap
    if other.category_id == target.category_id:
        value += W_CATEGORY
    if target.city and other.city and target.city == other.city:
        value += W_CITY
    value += W_RATING * float(other.rating_avg or 0)
    return value


def similar_attractions(db: Session, target: Attraction, limit: int = 6) -> list[Attraction]:
    """与 target 最像的 limit 个已发布景点, 按相似度降序。"""
    candidates = _candidates(db, target, fetch=max(limit * 10, 50))
    scored = [(score(target, c), c) for c in candidates]
    # 同分时按 id 升序, 保证结果稳定可测
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [c for value, c in scored if value > 0][:limit]


def popular_attractions(db: Session, limit: int = 10) -> list[Attraction]:
    """兜底兜底的兜底: 没有任何相似候选时, 给评分最高的已发布景点。"""
    stmt = (
        select(Attraction)
        .where(Attraction.status == PUBLISHED)
        .options(selectinload(Attraction.tags), selectinload(Attraction.images))
        .order_by(Attraction.rating_avg.desc(), Attraction.rating_count.desc(), Attraction.id.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
