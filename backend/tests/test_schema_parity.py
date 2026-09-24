"""db/schema.sql 与 SQLAlchemy 模型的对拍。

两处 DDL 是天然的双份真相: 改了一边忘了另一边, 查询就会在运行期炸。
这个测试只在有 PostgreSQL 时跑(CI 里由 service container 提供):
把 schema.sql 真正执行一遍, 再用 SQLAlchemy 的 inspector 读出表与列, 与模型逐一对齐。
本地没有 PostgreSQL 时自动 skip, 不会假装通过。
"""
from __future__ import annotations

import os
import pathlib

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db import Base

PG_URL = os.environ.get("TEST_DATABASE_URL")
SCHEMA_SQL = pathlib.Path(__file__).resolve().parents[2] / "db" / "schema.sql"

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="需要 TEST_DATABASE_URL 指向 PostgreSQL(CI 里由 service container 提供)"
)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL.read_text(encoding="utf-8")))
    yield engine
    engine.dispose()


def test_every_model_table_exists_in_schema(pg_engine):
    actual = set(inspect(pg_engine).get_table_names())
    expected = set(Base.metadata.tables)
    assert expected == actual, (
        f"模型与 schema.sql 的表不一致。"
        f"只在模型里: {sorted(expected - actual)}; 只在 schema 里: {sorted(actual - expected)}"
    )


def test_every_column_matches(pg_engine):
    inspector = inspect(pg_engine)
    for name, table in Base.metadata.tables.items():
        actual = {column["name"] for column in inspector.get_columns(name)}
        expected = set(table.columns.keys())
        assert expected <= actual, f"{name}: 模型有但 schema.sql 缺这些列 -> {sorted(expected - actual)}"
        assert actual <= expected, f"{name}: schema.sql 有但模型缺这些列 -> {sorted(actual - expected)}"


def test_view_is_created(pg_engine):
    names = set(inspect(pg_engine).get_view_names())
    assert "v_latest_rec" in names
