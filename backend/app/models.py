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
# 景区质量等级(GB/T 17775), 只适用于中国大陆景区
A_LEVELS = ("5A", "4A", "3A")
# 世界遗产类别
HERITAGE_KINDS = ("cultural", "natural", "mixed")
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
