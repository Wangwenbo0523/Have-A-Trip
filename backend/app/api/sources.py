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
from ..schemas import ImageAttribution, ImageCredit, ModificationStatus, SourceRecord, SourcesOut

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


# 许可文本 -> 许可全文(deed)地址。CC BY / CC BY-SA 要求「指出许可」并给出链接,
# 所以这一列是署名的一部分, 不是装饰。
#
# 认不出来的许可返回 None, 页面就不给链接 —— 猜一个等于把读者指向别的许可,
# 比没有链接更糟。新增许可写法时在这里补一条, 忘了补也不会撒谎。
LICENSE_URLS = {
    "cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "public domain": "https://commons.wikimedia.org/wiki/Commons:Public_domain",
    "mit": "https://opensource.org/license/mit",
}


def license_url(license_text: str | None) -> str | None:
    lowered = (license_text or "").strip().lower()
    if not lowered:
        return None
    if lowered in LICENSE_URLS:
        return LICENSE_URLS[lowered]
    # "CC BY-SA 4.0" / "CC BY 3.0" / "CC BY-SA 3.0 igo" -> by-sa/4.0/ 这样的路径
    if lowered.startswith("cc "):
        body = lowered[3:].strip()
        igo = body.endswith(" igo")
        if igo:
            body = body[:-4].strip()
        parts = body.split()
        if len(parts) == 2 and parts[1].replace(".", "").isdigit() and parts[0].startswith("by"):
            return "https://creativecommons.org/licenses/%s/%s/%s" % (
                parts[0], parts[1], "igo/" if igo else "")
    return None


# 我们自己的东西没有「改没改」可言 —— 修改状态只有在面对第三方许可时才是要标的事。
OWN_LICENSES = ("mit",)


def image_modification(license_text: str | None) -> ModificationStatus:
    """一张配图的修改状态。

    外部来源的图一律是 modified, 判据不是许可而是管线: 抓图走的是 Commons 重渲染的
    缩略图(尺寸已经变了), 页面上还按版面裁过。CC BY 3.0 起就要求标注修改, CC BY-SA
    还额外要求相同方式共享 —— 把事实写出来比按许可分类猜更可靠。
    将来若有人改成原样下载原始文件, 这一处要跟着改。
    """
    if (license_text or "").strip().lower() in OWN_LICENSES:
        return "not-applicable"
    return "modified"


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

    # 有外部来源的图逐张列出来。按 (作者, 景点) 排序: 同一个作者的作品挨在一起,
    # 核对「这个人署对了没有」时不用来回跳。
    attribution_rows = db.execute(
        select(
            Attraction.slug,
            Attraction.name,
            AttractionImage.url,
            AttractionImage.caption,
            AttractionImage.credit,
            AttractionImage.license,
            AttractionImage.source_url,
        )
        .join(Attraction, Attraction.id == AttractionImage.attraction_id)
        .where(Attraction.status == PUBLISHED, AttractionImage.source_url.is_not(None))
        .order_by(AttractionImage.credit.asc(), Attraction.name.asc())
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
        ImageCredit(
            credit=credit,
            license=license_text,
            license_url=license_url(license_text),
            image_count=count,
        )
        for credit, license_text, count in image_rows
    ]
    attributions = [
        ImageAttribution(
            attraction_slug=slug,
            attraction_name=name,
            url=url,
            caption=caption,
            credit=credit,
            license=license_text,
            license_url=license_url(license_text),
            source_url=source_url,
            modification=image_modification(license_text),
        )
        for slug, name, url, caption, credit, license_text, source_url in attribution_rows
    ]
    return SourcesOut(
        sources=sources,
        images=images,
        attributions=attributions,
        attraction_total=sum(item.attraction_count for item in sources),
        image_total=sum(item.image_count for item in images),
        needs_attention=any(item.modification == "unregistered" for item in sources),
    )
