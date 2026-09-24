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
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql

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
        # 用 exec_driver_sql 而不是 text(): schema.sql 是整份脚本, 里面有中文注释,
        # 注释里的 `... < :limit` 这类写法会被 text() 当成绑定参数, 整个夹具在 setup 就炸。
        conn.exec_driver_sql(SCHEMA_SQL.read_text(encoding="utf-8"))
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


# 新增表的列类型。名字对得上不代表类型对得上 —— 比如 embedding 在一边写成 BYTEA、
# 另一边写成 TEXT, 名字检查是发现不了的, 要到运行期插入或比较时才炸。
EXPECTED_TYPES = {
    "attraction_embedding": {
        "attraction_id": "INTEGER",
        "model": "TEXT",
        "dim": "INTEGER",
        "pipeline_version": "TEXT",
        "content_hash": "TEXT",
        # 向量与 JSON 都是 TEXT: 两侧同构, 不引 pgvector, 见 app/search/vectors.py
        "embedding": "TEXT",
    },
    "itinerary": {
        "public_token": "TEXT",
        "owner_key": "TEXT",
        "days": "INTEGER",
        "request_hash": "TEXT",
        "constraints": "TEXT",
        "status": "TEXT",
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        # 带精度的类型必须连精度一起写: PG 的 inspector 会把 NUMERIC(10, 6) 原样报出来,
        # 只写 NUMERIC 一定对不上
        "unit_price": "NUMERIC(10, 6)",
        "cache_key": "TEXT",
        "worker_id": "TEXT",
        "started_at": "TIMESTAMP WITH TIME ZONE",
        "heartbeat_at": "TIMESTAMP WITH TIME ZONE",
    },
    "itinerary_item": {
        "itinerary_id": "BIGINT",
        "attraction_id": "INTEGER",
        "attraction_name": "TEXT",
        "day_index": "INTEGER",
        "seq": "INTEGER",
        "note": "TEXT",
        "reason": "TEXT",
    },
    "trip_quota": {
        "owner_key": "TEXT",
        "day": "TEXT",
        "used": "INTEGER",
        "tokens_used": "INTEGER",
    },
}


def _type_name(column) -> str:
    """按 PostgreSQL 的 DDL 语法渲染反射出来的类型。

    不能只用 str(type): 通用 TIMESTAMP 的 str() 是 "TIMESTAMP", 时区信息在 timezone
    属性上(str(NUMERIC(10, 6)) 又恰好把精度带出来), 于是同一套断言时对时错。
    按方言编译一次, 精度与时区都会如实出现, 期望值可以直接照 DDL 写。
    """
    return str(column["type"].compile(dialect=postgresql.dialect())).upper()


@pytest.mark.parametrize("table", sorted(EXPECTED_TYPES))
def test_new_column_types_match(pg_engine, table):
    actual = {
        column["name"]: _type_name(column)
        for column in inspect(pg_engine).get_columns(table)
    }
    for name, expected in EXPECTED_TYPES[table].items():
        assert name in actual, f"{table}.{name} 在 schema.sql 里不存在"
        assert actual[name] == expected, f"{table}.{name}: 期望 {expected}, 实际 {actual[name]}"


def test_vector_tables_keep_their_unique_keys(pg_engine):
    """并发抢锁与幂等重灌都靠这两个唯一键, 掉了会静默退化成重复数据。"""
    embedding = {tuple(item["column_names"]) for item in inspect(pg_engine).get_unique_constraints("attraction_embedding")}
    assert ("attraction_id", "model") in embedding

    itinerary = {tuple(item["column_names"]) for item in inspect(pg_engine).get_unique_constraints("itinerary")}
    assert ("owner_key", "cache_key") in itinerary

    items = {tuple(item["column_names"]) for item in inspect(pg_engine).get_unique_constraints("itinerary_item")}
    assert ("itinerary_id", "day_index", "seq") in items
