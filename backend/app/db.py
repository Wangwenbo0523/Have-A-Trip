"""数据库连接与会话。

schema 的权威定义在 db/schema.sql; 这里的 ORM 模型与它一一对应,
两者的一致性由 CI 里的 PostgreSQL 对拍测试保证(见 tests/test_schema_parity.py)。
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str | None = None):
    settings = get_settings()
    target = url or settings.database_url
    kwargs: dict = {"pool_pre_ping": True}
    if target.startswith("sqlite"):
        # SQLite 只在测试里用。内存库必须用 StaticPool, 否则每个连接都是一个新的空库。
        kwargs = {}
        if ":memory:" in target:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(target, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖: 每个请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
