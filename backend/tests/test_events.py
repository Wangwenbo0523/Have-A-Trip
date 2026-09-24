"""行为埋点与评分聚合。"""
from __future__ import annotations

API = "/api/v1"


def post_event(client, **payload):
    return client.post(f"{API}/events", json=payload)


def baseline(**overrides):
    payload = {"device_id": "device-a", "attraction_id": None, "event_type": "view"}
    payload.update(overrides)
    return payload


def test_view_event_is_recorded(client, seeded):
    response = post_event(client, **baseline(attraction_id=seeded["west_lake"].id))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["event_type"] == "view" and body["user_id"] > 0


def test_same_device_reuses_one_user(client, seeded, db_session):
    from app.models import AppUser

    post_event(client, **baseline(attraction_id=seeded["west_lake"].id))
    post_event(client, **baseline(attraction_id=seeded["palace"].id, event_type="favorite"))
    count = db_session.query(AppUser).filter(AppUser.device_id == "device-a").count()
    assert count == 1


def test_rate_requires_rating(client, seeded):
    response = post_event(client, **baseline(attraction_id=seeded["west_lake"].id, event_type="rate"))
    assert response.status_code == 422


def test_non_rate_event_rejects_rating(client, seeded):
    response = post_event(
        client, **baseline(attraction_id=seeded["west_lake"].id, event_type="view", rating=4)
    )
    assert response.status_code == 422


def test_rating_out_of_range_is_rejected(client, seeded):
    for bad in (0, 6, -1):
        response = post_event(
            client,
            **baseline(attraction_id=seeded["west_lake"].id, event_type="rate", rating=bad),
        )
        assert response.status_code == 422, bad


def test_unknown_event_type_is_rejected(client, seeded):
    response = post_event(client, **baseline(attraction_id=seeded["west_lake"].id, event_type="click"))
    assert response.status_code == 422


def test_missing_device_id_is_rejected(client, seeded):
    response = client.post(f"{API}/events", json={"attraction_id": seeded["west_lake"].id, "event_type": "view"})
    assert response.status_code == 422


def test_unknown_attraction_is_404(client, seeded):
    response = post_event(client, **baseline(attraction_id=999999))
    assert response.status_code == 404


def test_draft_attraction_is_404(client, seeded):
    response = post_event(client, **baseline(attraction_id=seeded["draft"].id))
    assert response.status_code == 404


def test_rate_updates_rating_aggregate(client, seeded):
    attraction_id = seeded["lingyin"].id
    assert client.get(f"{API}/attractions/{attraction_id}").json()["rating_count"] == 0

    post_event(client, **baseline(attraction_id=attraction_id, event_type="rate", rating=5))
    body = client.get(f"{API}/attractions/{attraction_id}").json()
    assert body["rating_count"] == 1
    assert body["rating_avg"] == 5.0


def test_repeated_rating_counts_only_the_latest(client, seeded):
    """同一设备反复改分, 只算最后一次 —— 否则爱改分的人权重更高。"""
    attraction_id = seeded["lingyin"].id
    post_event(client, **baseline(attraction_id=attraction_id, event_type="rate", rating=1))
    post_event(client, **baseline(attraction_id=attraction_id, event_type="rate", rating=3))

    body = client.get(f"{API}/attractions/{attraction_id}").json()
    assert body["rating_count"] == 1
    assert body["rating_avg"] == 3.0


def test_two_devices_average(client, seeded):
    attraction_id = seeded["lingyin"].id
    post_event(client, **baseline(device_id="device-a", attraction_id=attraction_id, event_type="rate", rating=2))
    post_event(client, **baseline(device_id="device-b", attraction_id=attraction_id, event_type="rate", rating=4))

    body = client.get(f"{API}/attractions/{attraction_id}").json()
    assert body["rating_count"] == 2
    assert body["rating_avg"] == 3.0


def test_non_rate_events_do_not_touch_aggregate(client, seeded):
    attraction_id = seeded["lingyin"].id
    post_event(client, **baseline(attraction_id=attraction_id, event_type="view", dwell_ms=1200))
    post_event(client, **baseline(attraction_id=attraction_id, event_type="favorite"))
    body = client.get(f"{API}/attractions/{attraction_id}").json()
    assert body["rating_count"] == 0 and body["rating_avg"] == 0.0
