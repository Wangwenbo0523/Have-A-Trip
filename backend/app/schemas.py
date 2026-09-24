"""API 出参与入参的 Pydantic 模型。

字段名与 db/schema.sql 对齐; 前端 S4 按这里的形状写 types/index.ts。
"""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventType = Literal["view", "favorite", "rate", "share"]


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class CategoryWithCount(CategoryOut):
    attraction_count: int = 0


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class TagWithCount(TagOut):
    attraction_count: int = 0


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    caption: str | None = None
    credit: str
    license: str


class AttractionListItem(BaseModel):
    """列表/卡片用的字段。刻意不含 description, 列表页不需要那段长文本。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    name_en: str | None = None
    summary: str | None = None
    category: CategoryOut
    city: str | None = None
    province: str | None = None
    tags: list[TagOut] = Field(default_factory=list)
    cover_image: str | None = None
    rating_avg: float = 0
    rating_count: int = 0
    ticket_price: float | None = None
    suggested_hours: float | None = None


class AttractionDetail(AttractionListItem):
    description: str | None = None
    country_code: str
    address: str | None = None
    # 仅用于同城聚合等静态计算, 前端不渲染地图
    lat: float | None = None
    lon: float | None = None
    best_season: str | None = None
    images: list[ImageOut] = Field(default_factory=list)
    source: str
    license: str
    source_url: str | None = None
    updated_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int


class EventIn(BaseModel):
    """行为埋点。只记录浏览/收藏/评分/分享, 不采集任何定位信息。"""

    device_id: str = Field(min_length=1, max_length=200)
    attraction_id: int
    event_type: EventType
    rating: float | None = Field(default=None, ge=1, le=5)
    dwell_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _rating_matches_event_type(self) -> "EventIn":
        # 与 db/schema.sql 的 behavior_rate_needs_rating 同一口径:
        # rating 只属于 rate 事件。数据库只拦「rate 缺 rating」, API 两个方向都拦。
        if self.event_type == "rate" and self.rating is None:
            raise ValueError("event_type=rate 时必须给 rating")
        if self.event_type != "rate" and self.rating is not None:
            raise ValueError(f"event_type={self.event_type} 不允许带 rating")
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    attraction_id: int
    event_type: str
    rating: float | None = None


class RecommendationItem(BaseModel):
    attraction: AttractionListItem
    rank: int
    score: float | None = None
    algo: str
    reason: str


class HealthOut(BaseModel):
    status: str
    database: str
    version: str


# ---------------------------------------------------------------- 数据来源与许可声明

# 「修改状态」只有这几种取值。ODbL 与 CC BY-SA 都明确要求标注「是否修改过」,
# 所以 share-alike 来源的这个字段不是可选信息; not-applicable 只对不要求标注的许可成立。
# unregistered 是一种**告警态**: 库里有 share-alike 来源, 但没人登记过改没改过。
ModificationStatus = Literal["modified", "unmodified", "not-applicable", "unregistered"]


class SourceRecord(BaseModel):
    """一条 (source, license) 聚合。声明页据此渲染, 前端不写死。"""

    source: str
    license: str
    attraction_count: int
    province_count: int
    # 许可是否带相同方式共享义务(ODbL / CC BY-SA)。为真时页面必须显示修改状态。
    share_alike: bool
    modification: ModificationStatus


class ImageCredit(BaseModel):
    """一条 (credit, license) 聚合。图片的署名与许可存在库里, 不是文档里的口头约定。"""

    credit: str
    license: str
    image_count: int


class SourcesOut(BaseModel):
    sources: list[SourceRecord]
    images: list[ImageCredit]
    attraction_total: int
    image_total: int
    # 有 share-alike 来源却没登记修改状态。页面据此显示告警横幅。
    needs_attention: bool
