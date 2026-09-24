"""数据来源与许可声明页的数据源。

声明页**从数据库聚合**, 不在前端写死一份 —— 否则引入新来源时页面会撒谎。
聚合口径与 db/README.md 的「数据来源清单」一节一致, 边界写在 docs/LICENSE-AUDIT.md 第三节。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Attraction, AttractionImage
from ..schemas import ImageCredit, SourceRecord, SourcesOut

router = APIRouter(tags=["meta"])

PUBLISHED = "published"

# 带相同方式共享义务的许可。用子串匹配而不是精确比对 —— 许可字符串是人写的,
# 写法并不统一(ODbL 1.0 / ODbL-1.0 / CC BY-SA 4.0 / CC-BY-SA-4.0), 见 LICENSE-AUDIT 第三节。
SHARE_ALIKE_MARKERS = ("odbl", "cc by-sa", "cc-by-sa", "ccbysa", "share-alike")

# 引入 share-alike 来源时**必须**在这里登记「是否修改过」。
# ODbL 与 CC BY-SA 都明确要求标注修改状态, 这不是可选项; 没登记的会返回 unregistered,
# 页面上标出来 —— 宁可见红, 也不要含糊过去。
# 目前是空的: 90 条景点全部自采, 一条第三方数据都没进(docs/LICENSE-AUDIT.md 第三节)。
SOURCE_MODIFICATIONS: dict[tuple[str, str], str] = {}


def is_share_alike(license_text: str | None) -> bool:
    lowered = (license_text or "").lower()
    return any(marker in lowered for marker in SHARE_ALIKE_MARKERS)


def modification_of(source: str, license_text: str | None) -> str:
    """不要求标注的许可直接 not-applicable; 要标的必须在 SOURCE_MODIFICATIONS 里登记。"""
    if not is_share_alike(license_text):
        return "not-applicable"
    return SOURCE_MODIFICATIONS.get((source, license_text or ""), "unregistered")


@router.get("/sources", response_model=SourcesOut, summary="数据来源与许可(声明页用)")
def list_sources(db: Session = Depends(get_db)) -> SourcesOut:
    """按 (来源, 许可) 聚合已发布景点。前端不持有这份清单, 所以它不会和数据漂移。"""
    source_rows = db.execute(
        select(
            Attraction.source,
            Attraction.license,
            func.count(Attraction.id),
            func.count(distinct(Attraction.province)),
        )
        .where(Attraction.status == PUBLISHED)
        .group_by(Attraction.source, Attraction.license)
        .order_by(func.count(Attraction.id).desc(), Attraction.source.asc())
    ).all()

    # 挂在下架景点上的图不该出现在声明页 —— 这一页要说的只是「我们用了什么」
    image_rows = db.execute(
        select(AttractionImage.credit, AttractionImage.license, func.count(AttractionImage.id))
        .join(Attraction, Attraction.id == AttractionImage.attraction_id)
        .where(Attraction.status == PUBLISHED)
        .group_by(AttractionImage.credit, AttractionImage.license)
        .order_by(func.count(AttractionImage.id).desc(), AttractionImage.credit.asc())
    ).all()

    sources = [
        SourceRecord(
            source=source,
            license=license_text,
            attraction_count=count,
            province_count=provinces,
            share_alike=is_share_alike(license_text),
            modification=modification_of(source, license_text),
        )
        for source, license_text, count, provinces in source_rows
    ]
    images = [
        ImageCredit(credit=credit, license=license_text, image_count=count)
        for credit, license_text, count in image_rows
    ]
    return SourcesOut(
        sources=sources,
        images=images,
        attraction_total=sum(item.attraction_count for item in sources),
        image_total=sum(item.image_count for item in images),
        needs_attention=any(item.modification == "unregistered" for item in sources),
    )
