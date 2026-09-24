"""景点列表 / 详情 / 相似推荐。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import Attraction, Category, Tag, attraction_tag
from ..recommend.content_based import popular_attractions
from ..search import semantic
from ..schemas import AttractionDetail, AttractionListItem, GradeFilter, Page, SortKey

router = APIRouter(prefix="/attractions", tags=["attractions"])

PUBLISHED = "published"

ORDER_BY: dict[str, tuple] = {
    # 都带上 id 作为最后的排序键, 保证分页稳定、结果可测
    "rating": (Attraction.rating_avg.desc(), Attraction.rating_count.desc(), Attraction.id.asc()),
    "newest": (Attraction.created_at.desc(), Attraction.id.asc()),
    "name": (func.lower(Attraction.name).asc(), Attraction.id.asc()),
}


def published() -> Select:
    """只有 published 的景点才对外。draft / archived 不出现在任何接口里。"""
    return select(Attraction).where(Attraction.status == PUBLISHED)

def build_query(
    *,
    category: str | None = None,
    city: str | None = None,
    tag: str | None = None,
    grade: str | None = None,
    q: str | None = None,
) -> Select:
    """列表筛选的唯一实现。

    /attractions 与 /ai/search 都走这里 —— AI 解析出来的条件与用户手点的筛选
    走的是同一条路径, 不存在「AI 专用」的另一套宽松查询。
    """
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
    return statement


def count_of(db: Session, statement: Select) -> int:
    return db.scalar(select(func.count()).select_from(statement.subquery())) or 0


def page_of(db: Session, statement: Select, *, page: int, limit: int, sort: str):
    """按排序键取一页。排序键只从 ORDER_BY 里取, 不接受任意表达式。"""
    order = ORDER_BY.get(sort) or ORDER_BY["rating"]
    return list(
        db.scalars(statement.order_by(*order).offset((page - 1) * limit).limit(limit)).all()
    )

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
    statement = build_query(category=category, city=city, tag=tag, grade=grade, q=q)
    total = count_of(db, statement)
    items = page_of(db, statement, page=page, limit=limit, sort=sort)

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
    summary="相似景点(向量与结构化字段混合, 不需要用户行为)",
)
def get_similar(
    id_or_slug: str,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[AttractionListItem]:
    """向量可用时用「向量 + 标签/分类/同城」混合排序, 否则退回纯结构化。

    两条路都会返回非空结果, 最后还有热度兜底 —— 详情页的这一块塌掉会很难看,
    而"相似景点"本来就是个锦上添花的位置, 宁可给几个热门也不能空着。
    """
    attraction = find_attraction(db, id_or_slug)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")

    model = semantic.active_model(db)
    if model and semantic.model_dim(db, model) is None:
        # 维度混了就是个坏数据, 别拿它参与排序
        model = None
    rows = semantic.similar_attractions(
        db, attraction, limit=limit, model=model, settings=settings
    )
    if not rows:
        rows = popular_attractions(db, limit)
    return [AttractionListItem.model_validate(a) for a in rows]
