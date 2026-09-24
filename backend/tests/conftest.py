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

from llm_stubs import FakeClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, get_db, get_session_factory  # noqa: E402
from app.llm import embedding_cache_clear  # noqa: E402
from app.llm import cache_clear as llm_cache_clear  # noqa: E402
from app.llm import get_embedding_client, get_llm_client  # noqa: E402
from app.main import app  # noqa: E402
from app.recommend import service as rec_service  # noqa: E402
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
    # 行程生成在后台任务里跑, 那时请求自己的会话已经关了。不覆盖这个工厂,
    # 后台任务会连到真实的 PostgreSQL, 测试写完的结果就再也读不到。
    app.dependency_overrides[get_session_factory] = lambda: (lambda: db_session)
    # 推荐缓存是进程级的, 而每个用例的库都是全新的(id 会从 1 重新开始),
    # 不清就可能读到上一个用例的结果。
    rec_service.get_cache(get_settings()).clear()
    # 模型解析结果也是进程级缓存, 同样要清 —— 否则用例之间会读到彼此的那句话。
    llm_cache_clear()
    # 向量缓存同理: 打桩向量是按文本算的, 缓存不清会跨用例串。
    embedding_cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    rec_service.get_cache(get_settings()).clear()
    llm_cache_clear()
    embedding_cache_clear()


@pytest.fixture()
def seeded(db_session):
    """4 个已发布景点 + 1 个 draft。

    这里的 rating_avg 是测试夹具**刻意写死的**, 只为让排序可断言;
    db/seed/seed.sql 里不存在这种做法, 那边的评分一律为 0。
    """
    nature = Category(slug="nature", name="自然风光", sort=10)
    museum = Category(slug="museum", name="博物馆", sort=20)
    history = Category(slug="history", name="历史古迹", sort=30)
    theme_park = Category(slug="theme-park", name="主题乐园", sort=70)
    db_session.add_all([nature, museum, history, theme_park])
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
    # 孤立景点: 不同分类、不同城市、没有任何标签, 与谁都不像。
    # 有了它, 才能测到「相似候选不够时用热门补齐」那条分支。
    ocean_world = Attraction(
        slug="ocean-world", name="海洋世界", name_en="Ocean World",
        summary="上海市郊的海洋主题乐园", description="以海洋生物展示为主。",
        category_id=theme_park.id, province="上海市", city="上海市",
        rating_avg=Decimal("0.00"), rating_count=0,
        status="published", source="测试夹具", license="MIT",
        tags=[],
    )
    draft = Attraction(
        slug="draft-spot", name="未发布景点", summary="不该出现在任何接口里",
        category_id=nature.id, city="杭州市",
        status="draft", source="测试夹具", license="MIT",
    )
    db_session.add_all([west_lake, palace, terracotta, lingyin, ocean_world, draft])
    db_session.commit()
    return {
        "nature": nature, "museum": museum, "history": history, "theme_park": theme_park,
        "west_lake": west_lake, "palace": palace, "terracotta": terracotta,
        "lingyin": lingyin, "ocean_world": ocean_world, "draft": draft,
    }


@pytest.fixture()
def user(db_session):
    person = AppUser(device_id="test-device-1")
    db_session.add(person)
    db_session.commit()
    return person


@pytest.fixture()
def use_client():
    """把打桩的模型客户端装进依赖。用完就摘, 不给别的用例留串味。

    用法: `use_client(FakeClient(payload={...}))`, FakeClient 见 tests/llm_stubs.py;
    也可以传真的 LLMClient(Settings(...)) 来验配置分支。
    """

    def install(fake):
        app.dependency_overrides[get_llm_client] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture()
def use_embedding():
    """把打桩的向量客户端装进依赖。用法与 use_client 相同。"""

    def install(fake):
        app.dependency_overrides[get_embedding_client] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_embedding_client, None)
