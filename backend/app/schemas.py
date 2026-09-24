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


# ---------------------------------------------------------------- 看板


class StatSlice(BaseModel):
    """分布里的一档。

    key 是机器可读的取值(country_code / 5A / cultural / 分类 slug), label 是展示名
    —— 分类的 label 是库里的分类名(内容, 不翻译), 其余取值的 label 与 key 相同。
    前端按 key 决定怎么显示。**没填的取值归到 key='unknown'**, 不丢, 见 api/stats.py。
    """

    key: str
    label: str
    count: int


class StatsOut(BaseModel):
    """景点库总览。只统计已发布景点, 与 /sources 同一口径。"""

    attraction_total: int
    image_total: int
    plan_total: int
    # 覆盖的省级行政区数。省份为空的景点不计入(COUNT 天然忽略 NULL)
    province_total: int
    # 境内/境外由 country_code 分, 前端按 key == "CN" 判断, 后端不预设国别清单
    by_country: list[StatSlice]
    by_category: list[StatSlice]
    by_a_level: list[StatSlice]
    by_heritage: list[StatSlice]
    # 与 /sources 同一份聚合, 直接复用, 见 api/stats.py
    sources: list[SourceRecord]
    needs_attention: bool


# ---------------------------------------------------------------- AI 检索
#
# 契约真身同样在这里, 前端类型按它写。
# AI 只负责把一句话解析成查询条件(见 app/llm/interpret.py), 结果永远来自库内档案。

SortKey = Literal["rating", "newest", "name"]


class AIFilters(BaseModel):
    """模型解析出来的查询条件。字段与 /attractions 的查询参数一一对应。"""

    category: str | None = None
    tag: str | None = None
    grade: GradeFilter | None = None
    city: str | None = None
    q: str | None = None
    sort: SortKey = "rating"


class AISearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    page: int = Field(default=1, ge=1)
    size: int | None = Field(default=None, ge=1)


class AISearchOut(BaseModel):
    """一句话检索的结果。

    filters 是实际生效的条件, 前端可以把它渲染成可编辑的筛选条;
    interpreted=false 或 degraded=true 表示这次没走成模型, 已退回关键词检索。
    """

    query: str
    interpreted: bool
    degraded: bool
    model: str | None = None
    note: str
    filters: AIFilters
    items: list[AttractionListItem]
    page: int
    size: int
    total: int
    # 空结果放宽时被摘掉的条件(字段名)。留着它是为了能如实说明
    # 「这条结果不是原本那几个条件查出来的」—— 放宽过而不说, 等于骗人。
    relaxed: list[str] = Field(default_factory=list)
    # 结构化条件一条都没有时, 结果是向量近邻。与 relaxed 是两种不同的兜底, 分开标。
    semantic_fallback: bool = False
    # 页面上必须显示这句: 结果全部来自库内档案, AI 只参与理解需求
    disclaimer: str


class AIStatusOut(BaseModel):
    """AI 入口的可用性。前端据此决定要不要显示「用一句话找景点」。"""

    available: bool
    provider: str
    model: str | None = None
    # 语义检索单独报可用性。只配了向量模型、没配对话模型时, 「用一句话找景点」不可用,
    # 但语义检索可用 —— 合成一个状态位会让前端把本来能用的入口一起藏起来。
    embedding_available: bool = False
    embedding_model: str | None = None
    # 已向量化的已发布景点数 / 已发布景点总数。前端据此说明检索覆盖范围。
    embedded: int = 0
    published: int = 0
    disclaimer: str


class AIAskIn(BaseModel):
    """就某个景点追问一句。用 slug 而不是 id —— 对外标识符一直是 slug。"""

    slug: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=200)


class AIAskOut(BaseModel):
    """追问的回答。

    grounded=false 表示这段答案**没有**用上模型(降级时后端拼的档案摘录),
    这时答案仍然有档案依据, 只是不是模型写的; degraded=true 表示这次没走成模型。
    """

    slug: str
    question: str
    grounded: bool
    degraded: bool
    model: str | None = None
    answer: str
    note: str = ""
    # 模型自报引用了哪些档案字段; dropped 是它报了但档案里不存在的
    cited: list[str] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)
    disclaimer: str


class AIRecommendNotesIn(BaseModel):
    """润色推荐理由的入参。用户解析规则与 /recommendations 完全一致。"""

    user_id: int | None = None
    device_id: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=6, ge=1)


class AIRefinedReason(BaseModel):
    slug: str
    note: str


class AIRecommendNotesOut(BaseModel):
    """slug -> 润色后的理由。

    条目、顺序、分数都由 /recommendations 决定, 这里只多给一层文案 ——
    模型碰不到推荐结果本身, 只能改写理由的措辞。
    polished=false 表示这次没润色成(未配置模型 / 说法查不到依据), 此时的 note
    就是后端原来的理由, 页面照常显示即可。
    """

    polished: bool
    degraded: bool
    model: str | None = None
    note: str = ""
    reasons: list[AIRefinedReason] = Field(default_factory=list)
    # 被丢掉的条目: 模型报了不存在的 slug, 或改写内容查不到依据
    dropped: list[str] = Field(default_factory=list)
    disclaimer: str


# ---------------------------------------------------------------- 语义检索
#
# 与 AI 检索的区别: 那条路是「模型把一句话解析成筛选条件, 结果来自结构化查询」,
# 这条路是「把一句话向量化, 与景点描述的向量比相似度」。前者靠模型解析,
# 后者完全不需要对话模型 —— 只配了 embedding 也能用。


class SemanticSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int | None = Field(default=None, ge=1)


class SemanticHit(BaseModel):
    attraction: AttractionListItem
    # 余弦相似度, 0..1。只用来排序与展示, 不是「匹配度百分比」; 关键词兜底时为 null
    score: float | None = None
    # semantic = 向量近邻; keyword = 向量不可用时的关键词兜底
    match: Literal["semantic", "keyword"] = "semantic"


class SemanticSearchOut(BaseModel):
    query: str
    # 向量不可用时为真: 已退回关键词检索, 仍然是 200, 不是错误
    degraded: bool
    model: str | None = None
    note: str
    # 已向量化的已发布景点数 / 已发布景点总数。前端据此说明检索覆盖范围
    embedded: int = 0
    published: int = 0
    items: list[SemanticHit] = Field(default_factory=list)
    total: int = 0
    disclaimer: str


# ---------------------------------------------------------------- 行程生成

ItineraryStatus = Literal["pending", "generating", "succeeded", "failed", "rejected"]


class ItineraryIn(BaseModel):
    """提交一次行程生成。user_id 与 device_id 只能给一个, 与 /ai/recommend-notes 同口径。"""

    request_text: str = Field(min_length=1, max_length=300)
    days: int = Field(ge=1, le=14)
    user_id: int | None = None
    device_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _one_owner(self) -> "ItineraryIn":
        if self.user_id is not None and self.device_id is not None:
            raise ValueError("user_id 与 device_id 只能传一个")
        return self


class ItineraryAccepted(BaseModel):
    """202 的响应。之后用 token 轮询, 不再用 id。"""

    token: str
    status: ItineraryStatus


class ItineraryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_index: int
    seq: int
    attraction_id: int
    name: str
    note: str
    reason: str


class ItineraryUsageOut(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ItineraryOut(BaseModel):
    token: str
    status: ItineraryStatus
    days: int
    items: list[ItineraryItemOut] = Field(default_factory=list)
    # 失败时的可读原因; rejected 时说明是被限额拦下的
    error: str | None = None
    # 生成过程中的说明, 比如"库内景点不足, 只排出了 2 天"
    note: str | None = None
    model: str | None = None
    usage: ItineraryUsageOut | None = None
    generated_at: datetime | None = None
    created_at: datetime
    # 轮询上限(秒)。前端据此停轮询, 而不是各写各的超时
    max_poll_seconds: int
    disclaimer: str
