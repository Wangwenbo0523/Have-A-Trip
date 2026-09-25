"""景点列表 / 详情 / 相似推荐。"""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..geo import ip_locate
from ..models import Attraction, Category, Tag, attraction_tag
from ..recommend.content_based import popular_attractions
from ..search import semantic
from ..schemas import (
    AttractionDetail,
    AttractionListItem,
    GradeFilter,
    NearbyResult,
    NearbyScope,
    Page,
    SortKey,
)

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


def _sample_published(
    db: Session,
    limit: int,
    *,
    city: str | None = None,
    region: str | None = None,
    exclude: list[int] | None = None,
) -> list[Attraction]:
    """从已发布景点里随机抽 limit 个互不相同的, 可限定城市/省份并排除指定 id。

    /attractions/random 与 /attractions/nearby 共用这一套抽法: 先数出符合条件的总数 N,
    再随机取互不相同的下标, 按 ORDER BY id + OFFSET 逐个取。不用 ORDER BY random():
    那要对全表排序, 而且 SQLite 与 PostgreSQL 的 random() 语义并不一样(前者返回 64 位
    整数), OFFSET 两边都认。limit 上限 12, 所以最多 12 次走索引的小查询。

    exclude 是必须的: 同省包含同城, 不排掉已选中的 id 就会把同一个景点抽两次。
    """
    statement = published()
    if city is not None:
        statement = statement.where(Attraction.city == city)
    if region is not None:
        statement = statement.where(Attraction.province == region)
    if exclude:
        statement = statement.where(Attraction.id.not_in(exclude))
    total = count_of(db, statement)
    if total <= 0 or limit <= 0:
        return []
    ordered = statement.order_by(Attraction.id.asc())
    picked: list[Attraction] = []
    for offset in random.sample(range(total), min(limit, total)):
        found = db.scalars(ordered.offset(offset).limit(1)).first()
        if found is not None:
            picked.append(found)
    return picked


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


@router.get(
    "/random",
    response_model=list[AttractionListItem],
    summary="随机抽几个已发布景点",
)
def random_attractions(
    response: Response,
    limit: int = Query(3, ge=1, le=12, description="抽几个, 默认 3"),
    db: Session = Depends(get_db),
) -> list[AttractionListItem]:
    """完全随机, 不问你在哪儿。

    与 /recommendations 的分工: 那边按 (用户, 条数) 缓存, 为的是同一个人的推荐稳定;
    这一块恰恰相反, 每次打开首页都该是新的三个, 所以**不缓存**, 并在响应上显式写
    Cache-Control: no-store —— 否则浏览器或中间层一按, 随机就成了固定。

    与 /nearby 的分工: 这条一个外部请求都不发、也不看归属地, 就是「随便看看」。
    抽法见 _sample_published。
    """
    picked = _sample_published(db, limit)
    response.headers["Cache-Control"] = "no-store"
    return [AttractionListItem.model_validate(attraction) for attraction in picked]


@router.get(
    "/nearby",
    response_model=NearbyResult,
    summary="按 IP 猜的归属地就近抽几个已发布景点",
)
def nearby_attractions(
    request: Request,
    response: Response,
    limit: int = Query(3, ge=1, le=12, description="抽几个, 默认 3"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> NearbyResult:
    """首页那块「出去走走」用这个。

    与 /attractions/random 只差一点: 尽量抽**近**的。远近分三级算 —— 同城 -> 同省 ->
    全国, 因为库里的 lat/lon 全是 NULL(见 db/README.md 的数据口径), 算不出公里数。
    每一级内部仍然是随机抽取, 仍然不缓存(响应写 no-store)。同城/同省抽出来的**必须排
    在前面**: 三个里前两个在杭州、第三个在北京, 那前两个才是「近的」, 所以结果是按
    「先近后远」拼起来的, 不再二次排序。

    这不是定位: 归属地只到城市级(直辖市常常只到区), 只在这一次请求里用一下, 不落库、
    不写 cookie、不返回坐标。认不出来时照常返回全国随机并如实标 scope=nation —— 首页
    最先看到的那一块不该空着, 也不该假装自己是就近的。
    """
    city: str | None = None
    region: str | None = None
    location = ip_locate.locate(ip_locate.client_ip(request, settings), settings)
    if location is not None:
        city, region = ip_locate.match_place(db, city=location.city, region=location.region)

    levels: list[tuple[NearbyScope, list[Attraction]]] = []
    if city:
        levels.append(("city", _sample_published(db, limit, city=city)))
    taken = [attraction.id for _, row in levels for attraction in row]
    if region and len(taken) < limit:
        levels.append(
            ("region", _sample_published(db, limit - len(taken), region=region, exclude=taken))
        )
    taken = [attraction.id for _, row in levels for attraction in row]
    if len(taken) < limit:
        levels.append(("nation", _sample_published(db, limit - len(taken), exclude=taken)))

    picked = [attraction for _, row in levels for attraction in row]
    # scope 取真正出过货的最远那一层: 只有全在同城凑齐才算 city
    contributed = [name for name, row in levels if row]
    response.headers["Cache-Control"] = "no-store"
    return NearbyResult(
        items=[AttractionListItem.model_validate(attraction) for attraction in picked],
        located=bool(city or region),
        scope=contributed[-1] if contributed else "nation",
        city=city,
        region=region,
    )


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
