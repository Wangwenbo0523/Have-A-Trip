"""景点库总览看板的数据源。

看板上的每个数字都必须**从数据库算出来** —— 前端写死一份, 数据一变页面就开始撒谎,
与 /sources 是同一个道理。

口径与 /sources 完全一致: 只统计 status='published'。草稿与下架景点、以及挂在这些
景点上的配图与方案, 一个都不进统计 —— 看板要回答的是「我们对外提供了多少东西」,
把下架内容算进来只会虚高。

三条实现上的约束:
1. 分组与计数**全部交给 SQL**。在 Python 里遍历判断 a_level / heritage 会写出第二套
   口径, 而 test_schema_parity.py 拿 SQLite 与 PostgreSQL 对拍时只对得上 SQL。
2. NULL 归到 unknown 一档, 不直接丢掉。否则各档之和对不上总数, 看板上会凭空少掉
   几十个景点, 而且「未核实」本身就是要给人看的信息。
3. 排序只用 count 与取值本身, 不裸排可能为 NULL 的列 —— 两种数据库把 NULL 排在开头
   还是结尾并不一致。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ..db import get_db
from ..models import Attraction, AttractionImage, AttractionPlan, Category
from ..schemas import StatSlice, StatsOut
from .sources import PUBLISHED, list_sources

router = APIRouter(tags=["meta"])

# 档案里没填的取值统一归到这一档。前端把它显示成「未核实」, 不显示成「无等级」。
UNKNOWN = "unknown"


def _distribution(db: Session, value: ColumnElement) -> list[StatSlice]:
    """按一个档案字段统计已发布景点数, 数量降序; 同数量再按取值升序。"""
    key = func.coalesce(value, UNKNOWN)
    rows = db.execute(
        select(key, func.count(Attraction.id))
        .where(Attraction.status == PUBLISHED)
        .group_by(key)
        .order_by(func.count(Attraction.id).desc(), key.asc())
    ).all()
    # key 与 label 相同: 这些取值不是给人读的, 前端按 key 决定显示什么
    return [StatSlice(key=raw, label=raw, count=count) for raw, count in rows]


def _published_count(db: Session, entity: type, condition) -> int:
    """挂在下架景点上的子行不算数, 所以每条计数都要 join 回 attraction 再筛一遍。"""
    return db.scalar(
        select(func.count(entity.id))
        .join(Attraction, Attraction.id == entity.attraction_id)
        .where(condition)
    ) or 0


@router.get("/stats", response_model=StatsOut, summary="景点库总览(看板用)")
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    """看板数据, 全部现算。

    没有缓存也没有预聚合表: 库的规模是百级, 加一层聚合表只会多一处会过期的东西。
    """
    category_rows = db.execute(
        select(Category.slug, Category.name, func.count(Attraction.id))
        .join(Attraction, Attraction.category_id == Category.id)
        .where(Attraction.status == PUBLISHED)
        .group_by(Category.slug, Category.name)
        .order_by(func.count(Attraction.id).desc(), Category.slug.asc())
    ).all()

    # 声明页那份聚合直接复用, 不另算一套: 两处口径一旦分家, 就没人知道该信哪个
    declaration = list_sources(db)

    return StatsOut(
        attraction_total=db.scalar(
            select(func.count(Attraction.id)).where(Attraction.status == PUBLISHED)
        ) or 0,
        # COUNT 天然忽略 NULL: 省份没填的景点不该被算成一个省级行政区
        province_total=db.scalar(
            select(func.count(distinct(Attraction.province))).where(
                Attraction.status == PUBLISHED
            )
        ) or 0,
        image_total=_published_count(
            db, AttractionImage, Attraction.status == PUBLISHED
        ),
        plan_total=_published_count(db, AttractionPlan, Attraction.status == PUBLISHED),
        by_country=_distribution(db, Attraction.country_code),
        by_category=[
            StatSlice(key=slug, label=name, count=count)
            for slug, name, count in category_rows
        ],
        by_a_level=_distribution(db, Attraction.a_level),
        by_heritage=_distribution(db, Attraction.heritage),
        sources=declaration.sources,
        needs_attention=declaration.needs_attention,
    )
