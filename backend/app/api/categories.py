"""分类与标签。只统计已发布景点, 免得前端点进去发现是空的。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Attraction, Category, Tag, attraction_tag
from ..schemas import CategoryWithCount, TagWithCount

router = APIRouter(tags=["taxonomy"])

PUBLISHED = "published"


@router.get("/categories", response_model=list[CategoryWithCount], summary="分类列表")
def list_categories(db: Session = Depends(get_db)) -> list[CategoryWithCount]:
    rows = db.execute(
        select(Category, func.count(Attraction.id))
        .outerjoin(
            Attraction,
            (Attraction.category_id == Category.id) & (Attraction.status == PUBLISHED),
        )
        .group_by(Category.id)
        .order_by(Category.sort.asc(), Category.id.asc())
    ).all()
    return [
        CategoryWithCount(slug=category.slug, name=category.name, attraction_count=count)
        for category, count in rows
    ]


@router.get("/tags", response_model=list[TagWithCount], summary="标签列表(仅含有景点的)")
def list_tags(db: Session = Depends(get_db)) -> list[TagWithCount]:
    rows = db.execute(
        select(Tag, func.count(Attraction.id))
        .join(attraction_tag, attraction_tag.c.tag_id == Tag.id)
        .join(
            Attraction,
            (Attraction.id == attraction_tag.c.attraction_id) & (Attraction.status == PUBLISHED),
        )
        .group_by(Tag.id)
        .order_by(func.count(Attraction.id).desc(), Tag.id.asc())
    ).all()
    return [TagWithCount(slug=tag.slug, name=tag.name, attraction_count=count) for tag, count in rows]
