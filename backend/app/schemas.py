"""API 出参与入参的 Pydantic 模型。

字段名与 db/schema.sql 对齐; 前端 S4 按这里的形状写 types/index.ts。
"""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventType = Literal["view", "favorite", "rate", "share"]

# 列表页的等级筛选。5A/4A/3A 是中国景区的质量等级(GB/T 17775), heritage 表示
# 「列入 UNESCO 世界遗产名录」—— 世界遗产没有 A 级, 所以不能塞进同一个刻度里,
# 只能各占一个取值。
GradeFilter = Literal["5A", "4A", "3A", "heritage"]


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


class PlanStepOut(BaseModel):
    """旅游方案里的一步。day_no 从 1 起, 同一天内按 sort 升序。"""

    model_config = ConfigDict(from_attributes=True)

    day_no: int
    sort: int
    title: str
    detail: str
    duration_hours: float | None = None
    tip: str | None = None


class PlanOut(BaseModel):
    """一个景点的游玩方案。内容是本仓库自采的行程建议, 不是官方线路。"""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    days: int
    # 只给档次不给金额: 具体价格是易变信息, 见 db/README.md 的口径
    budget_level: Literal["free", "low", "mid", "high"] | None = None
    best_for: str | None = None
    summary: str
    steps: list[PlanStepOut] = Field(default_factory=list)


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
    # 卡片要按国别决定票价怎么写(境内是人民币, 境外库里没有币种字段), 所以列表也带上
    country_code: str
    # 景区质量等级(只对中国大陆景区有值)与世界遗产类别。两者都可能为 null ——
    # null 表示「未核实」, 前端不要显示成「无等级」
    a_level: Literal["5A", "4A", "3A"] | None = None
    heritage: Literal["cultural", "natural", "mixed"] | None = None


class AttractionDetail(AttractionListItem):
    description: str | None = None
    address: str | None = None
    # 仅用于同城聚合等静态计算, 前端不渲染地图
    lat: float | None = None
    lon: float | None = None
    best_season: str | None = None
    images: list[ImageOut] = Field(default_factory=list)
    plans: list[PlanOut] = Field(default_factory=list)
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
