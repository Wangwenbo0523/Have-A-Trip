"""景点列表 / 详情 / 相似推荐。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Attraction, Category, Tag, attraction_tag
from ..recommend.content_based import similar_attractions
from ..schemas import AttractionDetail, AttractionListItem, GradeFilter, Page

router = APIRouter(prefix="/attractions", tags=["attractions"])

PUBLISHED = "published"

SortKey = Literal["rating", "newest", "name"]

ORDER_BY: dict[str, tuple] = {
    # 都带上 id 作为最后的排序键, 保证分页稳定、结果可测
    "rating": (Attraction.rating_avg.desc(), Attraction.rating_count.desc(), Attraction.id.asc()),
    "newest": (Attraction.created_at.desc(), Attraction.id.asc()),
    "name": (func.lower(Attraction.name).asc(), Attraction.id.asc()),
}


def published() -> Select:
    """只有 published 的景点才对外。draft / archived 不出现在任何接口里。"""
    return select(Attraction).where(Attraction.status == PUBLISHED)


def find_attraction(db: Session, id_or_slug: str) -> Attraction | None:
    statement = published().where(Attraction.slug == id_or_slug)
    if id_or_slug.isdigit():
        statement = published().where(
            or_(Attraction.slug == id_or_slug, Attraction.id == int(id_or_slug))
        )
    return db.scalars(statement).first()


@router.get("", response_model=Page[AttractionListItem], summary="景点列表")
def list_attractions(
    page: int = Query(1, ge=1),
    size: int | None = Query(None, ge=1, description="默认取配置值, 上限 max_page_size"),
    category: str | None = Query(None, description="分类 slug"),
    city: str | None = Query(None, description="城市, 精确匹配"),
    tag: str | None = Query(None, description="标签 slug"),
    grade: GradeFilter | None = Query(
        None,
        description="等级: 5A/4A/3A 是中国景区质量等级; heritage 表示已列入世界遗产名录",
    ),
    q: str | None = Query(None, description="关键字, 匹配中英文名称与简介"),
    sort: SortKey = Query("rating"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Page[AttractionListItem]:
    limit = min(size or settings.default_page_size, settings.max_page_size)
    statement = published()

    if category:
        statement = statement.join(
            Category, Attraction.category_id == Category.id
        ).where(Category.slug == category)
    if city:
        statement = statement.where(Attraction.city == city)
    if tag:
        statement = (
            statement.join(attraction_tag, attraction_tag.c.attraction_id == Attraction.id)
            .join(Tag, Tag.id == attraction_tag.c.tag_id)
            .where(Tag.slug == tag)
        )
    if grade == "heritage":
        # 世界遗产没有 A 级, 所以这是一个独立的取值, 不是 a_level 的某个档位
        statement = statement.where(Attraction.heritage.is_not(None))
    elif grade:
        statement = statement.where(Attraction.a_level == grade)
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Attraction.name).like(needle),
                func.lower(func.coalesce(Attraction.name_en, "")).like(needle),
                func.lower(func.coalesce(Attraction.summary, "")).like(needle),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    statement = (
        statement.order_by(*ORDER_BY[sort])
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = list(db.scalars(statement).all())

    return Page[AttractionListItem](items=items, page=page, size=limit, total=total)


@router.get("/{id_or_slug}", response_model=AttractionDetail, summary="景点详情")
def get_attraction(id_or_slug: str, db: Session = Depends(get_db)) -> AttractionDetail:
    attraction = find_attraction(db, id_or_slug)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")
    return AttractionDetail.model_validate(attraction)


@router.get(
    "/{id_or_slug}/similar",
    response_model=list[AttractionListItem],
    summary="相似景点(内容相似度, 不需要用户行为)",
)
def get_similar(
    id_or_slug: str,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[AttractionListItem]:
    attraction = find_attraction(db, id_or_slug)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")
    return [AttractionListItem.model_validate(a) for a in similar_attractions(db, attraction, limit)]
