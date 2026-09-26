"""ORM 模型, 与 db/schema.sql 一一对应。

刻意只用可移植的类型(Integer/Text/Numeric/DateTime/Float), 不用 JSONB/ARRAY 等
PostgreSQL 专有类型, 这样测试可以跑在 SQLite 内存库上, 本地无需装 PostgreSQL。
生产仍然跑 PostgreSQL, schema 的真身是 db/schema.sql。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# PostgreSQL 里这几张表的 id 是 BIGINT。但 SQLite 只把精确的 `INTEGER PRIMARY KEY`
# 当 rowid 别名, 声明成 BIGINT 会让自增失效(插入时不带 id 直接 NOT NULL 报错)。
# 所以用类型变体: 生产 PostgreSQL 用 BIGINT, 测试 SQLite 用 INTEGER。
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

STATUSES = ("draft", "published", "archived")
EVENT_TYPES = ("view", "favorite", "rate", "share")
# 行程的状态机。pending/generating 是过程态, 后面三个是终态。
#   rejected  = 没花过钱就被限额挡住, 与 failed(调用了但失败)必须分开 ——
#               前端提示语完全不同, 混在一起用户会以为是自己输入有问题。
ITINERARY_STATUSES = ("pending", "generating", "succeeded", "failed", "rejected")
# 景区质量等级(GB/T 17775), 只适用于中国大陆景区
A_LEVELS = ("5A", "4A", "3A")
# 世界遗产类别
HERITAGE_KINDS = ("cultural", "natural", "mixed")
# 动态的可见性。没有自动审核(一期的取舍见 docs/PLAN.md 的 v4.0), 所以留一个
# 运营侧能一键下架的位置: visible 才对外, hidden 只对写它的那张 SQL 可见。
POST_STATUSES = ("visible", "hidden")

BUDGET_LEVELS = ("free", "low", "mid", "high")

# 景点-标签多对多。用 Table 而不是模型类, 因为这张表只承载关联关系。
attraction_tag = Table(
    "attraction_tag",
    Base.metadata,
    Column("attraction_id", Integer, ForeignKey("attraction.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL")
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Attraction(Base):
    __tablename__ = "attraction"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="attraction_status_check"
        ),
        CheckConstraint(
            "a_level IS NULL OR a_level IN ('5A', '4A', '3A')", name="attraction_a_level_check"
        ),
        CheckConstraint(
            "heritage IS NULL OR heritage IN ('cultural', 'natural', 'mixed')",
            name="attraction_heritage_check",
        ),
        Index("idx_attraction_status", "status"),
        Index("idx_attraction_category", "category_id"),
        Index("idx_attraction_city", "city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id", ondelete="RESTRICT"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(Text, nullable=False, default="CN")
    province: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    # 景区质量等级, 只对中国大陆景区有值。留空 = 未核实, 不是「没有等级」。
    a_level: Mapped[str | None] = mapped_column(Text)
    # 世界遗产类别, 只对列入 UNESCO 名录的景点有值。境外景点的「等级」看这个。
    heritage: Mapped[str | None] = mapped_column(Text)
    # 只用于同城聚合等静态计算。本项目不做地图与定位, 这两个字段不参与渲染。
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    best_season: Mapped[str | None] = mapped_column(Text)
    suggested_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    ticket_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cover_image: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    # 来源与许可必填: S5 的许可声明页由它聚合生成
    source: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    category: Mapped[Category] = relationship(lazy="joined")
    tags: Mapped[list[Tag]] = relationship(secondary=attraction_tag, lazy="selectin")
    images: Mapped[list[AttractionImage]] = relationship(
        back_populates="attraction",
        lazy="selectin",
        order_by="AttractionImage.sort",
        cascade="all, delete-orphan",
    )
    plans: Mapped[list[AttractionPlan]] = relationship(
        back_populates="attraction",
        lazy="selectin",
        order_by="AttractionPlan.id",
        cascade="all, delete-orphan",
    )


class AttractionImage(Base):
    __tablename__ = "attraction_image"
    __table_args__ = (UniqueConstraint("attraction_id", "url", name="uq_attraction_image_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    # 署名与许可必填: 图片比文字更容易踩许可问题
    credit: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(Text, nullable=False)
    # 来源页。实拍照片指向 Wikimedia Commons 的文件页; 自绘图为空(它没有外部来源)
    source_url: Mapped[str | None] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attraction: Mapped[Attraction] = relationship(back_populates="images")


class AttractionPlan(Base):
    """一个景点的游玩方案。步骤在 AttractionPlanStep 里, 按 (day_no, sort) 排序。"""

    __tablename__ = "attraction_plan"
    __table_args__ = (
        CheckConstraint("days >= 1 AND days <= 30", name="plan_days_check"),
        CheckConstraint(
            "budget_level IS NULL OR budget_level IN ('free', 'low', 'mid', 'high')",
            name="plan_budget_check",
        ),
        Index("idx_plan_attraction", "attraction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    budget_level: Mapped[str | None] = mapped_column(Text)
    best_for: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # 与景点一样: 来源与许可必填
    source: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attraction: Mapped[Attraction] = relationship(back_populates="plans")
    steps: Mapped[list[AttractionPlanStep]] = relationship(
        back_populates="plan",
        lazy="selectin",
        order_by="(AttractionPlanStep.day_no, AttractionPlanStep.sort)",
        cascade="all, delete-orphan",
    )


class AttractionPlanStep(Base):
    __tablename__ = "attraction_plan_step"
    __table_args__ = (
        CheckConstraint("day_no >= 1", name="plan_step_day_check"),
        CheckConstraint(
            "duration_hours IS NULL OR duration_hours >= 0", name="plan_step_hours_check"
        ),
        # 同一天里 sort 不能重复, 否则步骤顺序就没有确定含义了
        UniqueConstraint("plan_id", "day_no", "sort", name="uq_plan_step_order"),
        Index("idx_plan_step_plan", "plan_id", "day_no", "sort"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("attraction_plan.id", ondelete="CASCADE"), nullable=False
    )
    day_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    tip: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[AttractionPlan] = relationship(back_populates="steps")


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # 匿名设备标识。不做账号体系, 也不采集定位。
    device_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BehaviorLog(Base):
    __tablename__ = "behavior_log"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('view', 'favorite', 'rate', 'share')",
            name="behavior_event_type_check",
        ),
        # 口径: 只有 rate 事件才应该带 rating
        CheckConstraint(
            "event_type <> 'rate' OR rating IS NOT NULL", name="behavior_rate_needs_rating"
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    dwell_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RecResult(Base):
    __tablename__ = "rec_result"
    __table_args__ = (
        UniqueConstraint("user_id", "attraction_id", "batch_id", name="uq_rec_user_item_batch"),
        CheckConstraint("rank >= 1", name="rec_rank_positive"),
        Index("idx_rec_user_rank", "user_id", "rank"),
        Index("idx_rec_batch", "batch_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float)
    # 从 1 开始。API 按 rank 升序返回, 不按 score —— 不同算法的分数不可比。
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    algo: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------- 语义检索


class AttractionEmbedding(Base):
    """一个景点在一个模型下的一条向量。

    联合主键 (attraction_id, model) —— 同一个景点可以同时存在多套模型的向量(切换期间),
    但同一模型只能有一条。dim 一并存下来: 维度是数据的一部分, 不能只放在配置里,
    否则配置一改, 库里那批旧维度的向量就成了静默的垃圾。
    """

    __tablename__ = "attraction_embedding"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="CASCADE"), nullable=False
    )
    # 形如 "ollama:bge-m3:auto", 见 app/llm/embedding.py 的 signature
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    # 拼串口径版本, 参与指纹。见 app/search/canonical.py
    pipeline_version: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256(model + pipeline_version + 规范化文本), 用于判断要不要重算
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # PostgreSQL 与 SQLite 都存 JSON 数组文本, 见 app/search/vectors.py 的取舍说明
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("dim > 0", name="embedding_dim_check"),
        UniqueConstraint("attraction_id", "model", name="uq_embedding_item_model"),
        Index("idx_embedding_model_item", "model", "attraction_id"),
    )

    attraction: Mapped[Attraction] = relationship()


# ---------------------------------------------------------------- 行程生成


class TripQuota(Base):
    """按 (owner, 天) 的计数器。限额与预算靠它做成原子操作。

    为什么单独一张表而不是 count(itinerary): 「先查条数再写入」在任何隔离级别下
    都不是原子的, 两个并发请求会同时通过检查。这里用一条
    `UPDATE ... WHERE used < :limit` 拿到行锁并自增 —— 单条语句的读-改-写在
    PostgreSQL 与 SQLite 上都是原子的, 靠 rowcount 判断有没有抢到名额。
    owner_key = '__global__' 的那一行是全站 token 预算。
    """

    __tablename__ = "trip_quota"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    owner_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 日期字符串 YYYY-MM-DD。用文本而不是 DATE: 两种数据库的时区处理不一样,
    # 这里要的是「哪个自然日」这个纯粹的分组键, 由应用算好再传进来。
    day: Mapped[str] = mapped_column(Text, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("used >= 0", name="quota_used_check"),
        CheckConstraint("tokens_used >= 0", name="quota_tokens_check"),
        UniqueConstraint("owner_key", "day", name="uq_quota_owner_day"),
        Index("idx_quota_day", "day"),
    )


class Itinerary(Base):
    """一次「自然语言需求 -> 按天行程」的生成任务。

    表名叫 itinerary 而不是 trip_plan: 库里已经有一个 attraction_plan(景点自带的
    静态游玩方案), 两个 plan 并排会让「改哪个」永远要回去查定义。
    """

    __tablename__ = "itinerary"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'generating', 'succeeded', 'failed', 'rejected')",
            name="itinerary_status_check",
        ),
        CheckConstraint("days >= 1 AND days <= 14", name="itinerary_days_check"),
        CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0", name="itinerary_prompt_tokens_check"
        ),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="itinerary_completion_tokens_check",
        ),
        # 并发抢锁点: 同一个 owner 的同一份需求只能有一行。后到的请求撞唯一键失败,
        # 直接复用既有行程 —— 既不重复调模型, 也不重复计费。
        UniqueConstraint("owner_key", "cache_key", name="uq_itinerary_owner_cache"),
        Index("idx_itinerary_owner_time", "owner_key", "created_at"),
        Index("idx_itinerary_status_heartbeat", "status", "heartbeat_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # 对外只用 token。自增 id 可枚举 —— 递增就能读到别人的需求原文, 见 app/api/itineraries.py
    public_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # user_id 有就给 "u:<id>", 否则 "d:<device_id>"。缓存与限额都以它为作用域。
    owner_key: Mapped[str] = mapped_column(Text, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    # 只存 hash, 不存需求原文: 原文里常有同行人、预算这类个人信息,
    # 存下来就要额外背一套保留期与删除机制, 而生成并不需要回读原文。
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # 解析出来的约束(城市/预算/同行人等)的 JSON 文本, 供展示与缓存键使用
    constraints: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    # 单价快照: 服务商调价后, 历史行程的成本仍然按当时的价算
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    cache_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 回收判据。多 worker 下只看「generating 超时」会误杀别人正在跑的任务,
    # 必须认领 + 心跳, 见 app/trip/service.py
    worker_id: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list[ItineraryItem]] = relationship(
        back_populates="itinerary",
        lazy="selectin",
        order_by="(ItineraryItem.day_index, ItineraryItem.seq)",
        cascade="all, delete-orphan",
    )


class ItineraryItem(Base):
    """行程里的一站。attraction_id 一定落在生成时的候选集内, 由 validator 保证。"""

    __tablename__ = "itinerary_item"
    __table_args__ = (
        CheckConstraint("day_index >= 1", name="item_day_check"),
        CheckConstraint("seq >= 1", name="item_seq_check"),
        UniqueConstraint("itinerary_id", "day_index", "seq", name="uq_itinerary_item_order"),
        Index("idx_itinerary_item_order", "itinerary_id", "day_index", "seq"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    itinerary_id: Mapped[int] = mapped_column(
        ForeignKey("itinerary.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT 而不是 CASCADE: 行程是用户产出, 不因为景点被删就悄悄少一站。
    # 景点下架走 status='archived' 软删, 硬删要走显式的数据清理流程。
    attraction_id: Mapped[int] = mapped_column(
        ForeignKey("attraction.id", ondelete="RESTRICT"), nullable=False
    )
    # 名称快照: 景点改名或下架后, 回看历史行程仍然显示当时的那一刻
    attraction_name: Mapped[str] = mapped_column(Text, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    itinerary: Mapped[Itinerary] = relationship(back_populates="items")

# ---------------------------------------------------------------- 用户动态


class Post(Base):
    """一条用户写的动态。可选挂一个景点。

    这是全项目唯一由用户产出**自由文本**的地方, 所以有四条与别处不同的口径:

    1. `status` 只有 visible 才对外。一期不做自动审核, 运营侧下架走
       `update post set status = 'hidden' where id = ...`(见 db/README.md)。
    2. `author_name` 与 `attraction_name` 都是**快照**: 署名只属于发出来的那一条,
       景点改名或下架之后回看旧动态仍然显示当时那一刻(与 itinerary_item 同一个道理)。
    3. 不存任何定位。动态里看起来像位置的字, 只可能是用户自己敲进去的。
    4. 作者删除是**真删**(DELETE), 运营下架是软删(status) —— 前者是用户的意愿,
       后者要留痕, 两件事不能合成一个开关。
    """

    __tablename__ = "post"
    __table_args__ = (
        CheckConstraint("status IN ('visible', 'hidden')", name="post_status_check"),
        # 长度口径: 库这一层只做兜底(非空、别超过 1000 字), 对用户承诺的 500 字在
        # schemas.py 的 POST_BODY_MAX。两个数字合成一个的话, 改产品上限就要动迁移。
        CheckConstraint("length(body) >= 1", name="post_body_not_blank"),
        CheckConstraint("length(body) <= 1000", name="post_body_length_check"),
        CheckConstraint("length(author_name) <= 40", name="post_author_length_check"),
        # 列表按 id 倒序取(与游标同序, 见 api/posts.py), 「我的」也一样:
        # 这两个索引就是给它的 —— 不是 created_at, 改了排序就要跟着改这里
        Index("idx_post_status_id", "status", "id"),
        Index("idx_post_user_id", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    author_name: Mapped[str] = mapped_column(Text, nullable=False, default="游客")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # SET NULL 而不是 CASCADE: 景点被硬删不该连坐删掉别人写的动态, 只是那一行的链接没了
    attraction_id: Mapped[int | None] = mapped_column(
        ForeignKey("attraction.id", ondelete="SET NULL")
    )
    attraction_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="visible")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attraction: Mapped[Attraction | None] = relationship()

