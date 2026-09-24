"""测试夹具。

默认跑在 SQLite 内存库上, 本地不需要装 PostgreSQL。
与生产 PostgreSQL 的一致性由 test_schema_parity.py 在 CI 里对拍(需要 TEST_DATABASE_URL)。
"""
from __future__ import annotations

import pathlib
import sys
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppUser, Attraction, BehaviorLog, Category, Tag  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db_session):
    """4 个已发布景点 + 1 个 draft。

    这里的 rating_avg 是测试夹具**刻意写死的**, 只为让排序可断言;
    db/seed/seed.sql 里不存在这种做法, 那边的评分一律为 0。
    """
    nature = Category(slug="nature", name="自然风光", sort=10)
    museum = Category(slug="museum", name="博物馆", sort=20)
    history = Category(slug="history", name="历史古迹", sort=30)
    db_session.add_all([nature, museum, history])
    db_session.flush()

    free = Tag(slug="free", name="免票")
    family = Tag(slug="family", name="亲子")
    heritage = Tag(slug="world-heritage", name="世界遗产")
    db_session.add_all([free, family, heritage])
    db_session.flush()

    west_lake = Attraction(
        slug="west-lake", name="西湖", name_en="West Lake",
        summary="三面环山的淡水湖", description="位于杭州城西。",
        category_id=nature.id, province="浙江省", city="杭州市",
        lat=30.2489, lon=120.1417, best_season="春秋", suggested_hours=Decimal("4.0"),
        ticket_price=Decimal("0.00"), rating_avg=Decimal("4.70"), rating_count=100,
        status="published", source="测试夹具", license="MIT",
        tags=[free, heritage],
    )
    palace = Attraction(
        slug="palace-museum", name="故宫博物院", name_en="Palace Museum",
        summary="明清两代皇宫", description="又称紫禁城。",
        category_id=museum.id, province="北京市", city="北京市",
        rating_avg=Decimal("4.90"), rating_count=200,
        status="published", source="测试夹具", license="MIT",
        tags=[family, heritage],
    )
    terracotta = Attraction(
        slug="terracotta-army", name="秦始皇兵马俑", name_en="Terracotta Army",
        summary="秦始皇陵的陪葬坑", description="1974 年发现。",
        category_id=history.id, province="陕西省", city="西安市",
        rating_avg=Decimal("4.50"), rating_count=50,
        status="published", source="测试夹具", license="MIT",
        tags=[family, heritage],
    )
    lingyin = Attraction(
        slug="lingyin-temple", name="灵隐寺", name_en="Lingyin Temple",
        summary="杭州最早的佛教寺院之一", description="始建于东晋。",
        category_id=history.id, province="浙江省", city="杭州市",
        rating_avg=Decimal("0.00"), rating_count=0,
        status="published", source="测试夹具", license="MIT",
        tags=[free],
    )
    draft = Attraction(
        slug="draft-spot", name="未发布景点", summary="不该出现在任何接口里",
        category_id=nature.id, city="杭州市",
        status="draft", source="测试夹具", license="MIT",
    )
    db_session.add_all([west_lake, palace, terracotta, lingyin, draft])
    db_session.commit()
    return {
        "nature": nature, "museum": museum, "history": history,
        "west_lake": west_lake, "palace": palace, "terracotta": terracotta,
        "lingyin": lingyin, "draft": draft,
    }


@pytest.fixture()
def user(db_session):
    person = AppUser(device_id="test-device-1")
    db_session.add(person)
    db_session.commit()
    return person
