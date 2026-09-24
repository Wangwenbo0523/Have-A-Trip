"""推荐接口: 离线结果 / 内容相似度 / 热门兜底 三级降级。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

API = "/api/v1"


def rec(client, **params):
    response = client.get(f"{API}/recommendations", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def view(client, attraction_id, device_id="device-a", **extra):
    payload = {"device_id": device_id, "attraction_id": attraction_id, "event_type": "view"}
    payload.update(extra)
    response = client.post(f"{API}/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_unknown_device_falls_back_to_cold_start(client, seeded):
    """没见过的设备不是错误 —— 返回一份可用的推荐, 而不是 404 或空数组。"""
    items = rec(client, device_id="brand-new-device")
    assert items, "新用户也必须拿到非空推荐"
    assert {i["algo"] for i in items} == {"popular-fallback"}
    assert all(i["reason"] for i in items)
    assert [i["rank"] for i in items] == list(range(1, len(items) + 1))


def test_anonymous_request_is_not_empty(client, seeded):
    assert rec(client) != []


def test_cold_start_excludes_unpublished(client, seeded):
    slugs = {i["attraction"]["slug"] for i in rec(client, device_id="fresh")}
    assert "draft-spot" not in slugs


def test_limit_is_honoured_and_capped(client, seeded):
    assert len(rec(client, device_id="fresh", limit=2)) == 2
    capped = rec(client, device_id="fresh", limit=999)
    assert len(capped) == 5  # 只有 5 个已发布景点, 上限 rec_max_limit=50 不构成约束


def test_user_id_and_device_id_together_is_400(client, seeded):
    response = client.get(f"{API}/recommendations", params={"user_id": 1, "device_id": "x"})
    assert response.status_code == 400


def test_unknown_user_id_is_404(client, seeded):
    assert client.get(f"{API}/recommendations", params={"user_id": 999999}).status_code == 404


def test_viewing_switches_to_content_based(client, seeded):
    view(client, seeded["west_lake"].id)
    items = rec(client, device_id="device-a")

    assert items[0]["algo"] == "content-based"
    slugs = [i["attraction"]["slug"] for i in items]
    # 同城 + 共享 free 标签的灵隐寺最像, 其次才是共享 world-heritage 的两个
    assert slugs[0] == "lingyin-temple"
    assert "west-lake" not in slugs, "看过的不该再推"
    assert "浏览过" in items[0]["reason"] and "西湖" in items[0]["reason"]


def test_favoriting_reason_uses_the_right_verb(client, seeded):
    view(client, seeded["palace"].id, device_id="device-b", event_type="favorite")
    items = rec(client, device_id="device-b")
    assert "收藏过" in items[0]["reason"]


def test_content_based_pads_with_popular_to_reach_limit(client, seeded):
    """西湖的相似候选只有 3 个(灵隐寺/故宫/兵马俑), 要 4 条就得靠热门补齐。

    海洋世界跟谁都不像, 内容相似度永远算不到它, 只能从兜底里进来。
    """
    view(client, seeded["west_lake"].id)
    items = rec(client, device_id="device-a", limit=4)
    algos = [i["algo"] for i in items]
    assert algos[0] == "content-based"
    assert "popular-fallback" in algos, "相似候选不够时应当用热门补齐"
    assert "ocean-world" in [i["attraction"]["slug"] for i in items]
    assert len({i["attraction"]["slug"] for i in items}) == len(items), "不能重复推荐同一个景点"
    assert [i["rank"] for i in items] == [1, 2, 3, 4]


def test_offline_results_take_precedence(client, seeded, db_session):
    from app.models import AppUser, RecResult

    user = AppUser(device_id="device-offline")
    db_session.add(user)
    db_session.commit()

    now = datetime.now(timezone.utc)
    db_session.add_all([
        RecResult(user_id=user.id, attraction_id=seeded["palace"].id, score=0.91, rank=1,
                  algo="bpr", reason="离线模型: 你偏好博物馆", batch_id="batch-old",
                  generated_at=now - timedelta(hours=1)),
        RecResult(user_id=user.id, attraction_id=seeded["terracotta"].id, score=0.88, rank=1,
                  algo="bpr", reason="离线模型: 你对历史古迹感兴趣", batch_id="batch-new",
                  generated_at=now),
        RecResult(user_id=user.id, attraction_id=seeded["lingyin"].id, score=0.42, rank=2,
                  algo="bpr", reason="离线模型: 同城", batch_id="batch-new", generated_at=now),
    ])
    db_session.commit()

    # 同时给这个用户一点行为, 证明离线结果优先于内容相似度
    view(client, seeded["west_lake"].id, device_id="device-offline")

    items = rec(client, device_id="device-offline")
    assert {i["algo"] for i in items} == {"bpr"}
    # 只有最新一批(batch-new)会被采用, batch-old 那一行不该出现
    assert "离线模型: 你偏好博物馆" not in [i["reason"] for i in items]
    assert [i["attraction"]["slug"] for i in items] == ["terracotta-army", "lingyin-temple"]
    assert [i["rank"] for i in items] == [1, 2]
    assert items[0]["score"] == 0.88


def test_offline_result_pointing_at_draft_is_filtered_out(client, seeded, db_session):
    """训练之后景点被下架, 结果表里的死链不能再推出去。"""
    from app.models import AppUser, RecResult

    user = AppUser(device_id="device-stale")
    db_session.add(user)
    db_session.commit()
    db_session.add(
        RecResult(user_id=user.id, attraction_id=seeded["draft"].id, score=0.99, rank=1,
                  algo="bpr", reason="离线模型: 已下架", batch_id="batch-1",
                  generated_at=datetime.now(timezone.utc))
    )
    db_session.commit()

    items = rec(client, device_id="device-stale")
    assert "draft-spot" not in [i["attraction"]["slug"] for i in items]
    assert items, "过滤掉死链之后仍然要给得出东西"


def test_result_is_cached_and_event_invalidates_it(client, seeded):
    """同一请求重复调用结果一致; 一旦上报行为, 缓存立刻作废。"""
    first = rec(client, device_id="device-c")
    second = rec(client, device_id="device-c")
    assert first == second
    assert {i["algo"] for i in first} == {"popular-fallback"}

    view(client, seeded["west_lake"].id, device_id="device-c")
    after = rec(client, device_id="device-c")
    assert after != first
    assert after[0]["algo"] == "content-based"


def test_different_users_do_not_share_cache(client, seeded):
    view(client, seeded["west_lake"].id, device_id="user-x")
    view(client, seeded["terracotta"].id, device_id="user-y")

    items_x = rec(client, device_id="user-x")
    items_y = rec(client, device_id="user-y")
    # 缓存键必须带上 user_id: 否则第二个用户会拿到第一个用户的推荐
    assert "西湖" in items_x[0]["reason"]
    assert "西湖" not in items_y[0]["reason"]
    assert "秦始皇兵马俑" in items_y[0]["reason"]
