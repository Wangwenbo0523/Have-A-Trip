"""动态区: 发帖、筛选、删除、限额。

断言只打在 HTTP 结果与库里的计数器上, 不碰实现细节 —— 接口是唯一的裁判。
"""
from __future__ import annotations

import pytest

from app import quota
from app.config import Settings, get_settings
from app.main import app
from app.models import AppUser, Post, TripQuota

API = "/api/v1"


# ------------------------------------------------------------------ 夹具


@pytest.fixture()
def settings_default():
    """没被用例改过的配置。断言默认值时用它, 而不是把数字抄一遍。"""
    return Settings()


@pytest.fixture()
def override_settings():
    """临时改配置(例如把 post_daily_limit 调小)。用完就摘, 不给别的用例留串味。"""

    def install(**overrides):
        configured = Settings(**overrides)
        app.dependency_overrides[get_settings] = lambda: configured
        return configured

    yield install
    app.dependency_overrides.pop(get_settings, None)


def payload(**extra):
    data = {"device_id": "device-a", "body": "西湖边上的落日很好看。"}
    data.update(extra)
    return data


def post(client, **extra):
    return client.post(f"{API}/posts", json=payload(**extra))


def listing(client, **params):
    return client.get(f"{API}/posts", params=params)


# ------------------------------------------------------------------ 发帖


def test_create_post_with_attraction_and_nickname(client, seeded):
    response = post(client, attraction_slug="west-lake", nickname="小北")
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["author"]["name"] == "小北"
    assert item["body"] == "西湖边上的落日很好看。"
    assert item["attraction"]["slug"] == "west-lake"
    assert item["attraction"]["name"] == "西湖"
    assert item["attraction"]["name_en"] == "West Lake"
    assert item["created_at"]
    assert item["mine"] is True


def test_nickname_is_remembered_for_next_post(client, seeded):
    post(client, nickname="小北")
    again = post(client, body="第二天又来了")
    assert again.json()["author"]["name"] == "小北"


def test_post_without_nickname_falls_back_to_guest(client, seeded):
    assert post(client).json()["author"]["name"] == "游客"


def test_post_without_attraction_has_no_attraction(client, seeded):
    assert post(client).json()["attraction"] is None


def test_body_is_stripped(client, seeded):
    assert post(client, body="  两边有空格  ").json()["body"] == "两边有空格"


def test_blank_body_is_rejected(client, seeded):
    assert post(client, body="").status_code == 422
    assert post(client, body="   ").status_code == 422
    assert post(client, body="\n\t ").status_code == 422


def test_body_over_limit_is_rejected(client, seeded):
    assert post(client, body="好" * 501).status_code == 422
    assert post(client, body="好" * 500).status_code == 201


def test_two_owner_ids_are_rejected(client, seeded, user):
    assert post(client, user_id=user.id).status_code == 422


def test_unknown_attraction_is_404(client, seeded):
    assert post(client, attraction_slug="no-such-spot").status_code == 404


def test_draft_attraction_is_404(client, seeded):
    assert post(client, attraction_slug=seeded["draft"].slug).status_code == 404


def test_unknown_user_id_is_404(client, seeded):
    assert post(client, device_id=None, user_id=999999).status_code == 404


def test_user_id_owner_is_accepted(client, seeded, user):
    assert post(client, device_id=None, user_id=user.id).status_code == 201


def test_long_nickname_is_rejected(client, seeded):
    assert post(client, nickname="名" * 25).status_code == 422


# ------------------------------------------------------------------ 列表


def test_list_is_newest_first_and_paginates(client, seeded, settings_default):
    for index in range(3):
        assert post(client, body="第 %d 条" % index).status_code == 201
    first = listing(client, size=2).json()
    assert first["total"] == 3 and first["size"] == 2
    assert [item["body"] for item in first["items"]] == ["第 2 条", "第 1 条"]
    second = listing(client, size=2, page=2).json()
    assert [item["body"] for item in second["items"]] == ["第 0 条"]


def test_size_is_clamped_to_max_page_size(client, seeded, settings_default):
    post(client)
    assert listing(client, size=9999).json()["size"] == settings_default.max_page_size


def test_list_only_returns_visible(client, seeded, user, db_session):
    post(client, body="看得见的")
    db_session.add(
        Post(user_id=user.id, author_name="游客", body="被下架的", status="hidden")
    )
    db_session.commit()
    page = listing(client).json()
    assert [item["body"] for item in page["items"]] == ["看得见的"]
    assert page["total"] == 1


def test_filter_by_attraction(client, seeded):
    post(client, body="西湖的", attraction_slug="west-lake")
    post(client, body="故宫的", attraction_slug="palace-museum")
    page = listing(client, attraction="west-lake").json()
    assert page["total"] == 1
    assert [item["body"] for item in page["items"]] == ["西湖的"]


def test_unknown_attraction_slug_gives_an_empty_page(client, seeded):
    post(client)
    page = listing(client, attraction="no-such-spot").json()
    assert page["items"] == [] and page["total"] == 0


def test_filter_by_device_id_and_mine_flag(client, seeded):
    post(client, device_id="device-a", body="A 的")
    post(client, device_id="device-b", body="B 的")

    mine = listing(client, device_id="device-a", viewer="device-a").json()
    assert [item["body"] for item in mine["items"]] == ["A 的"]
    assert mine["items"][0]["mine"] is True
    assert mine["used_today"] == 1

    others = listing(client, viewer="device-b").json()
    assert [item["body"] for item in others["items"]] == ["B 的", "A 的"]
    assert [item["mine"] for item in others["items"]] == [True, False], "只看自己那几条算 mine"


def test_missing_device_id_gives_an_empty_page(client, seeded):
    post(client)
    page = listing(client, device_id="device-nobody").json()
    assert page["items"] == [] and page["total"] == 0
    assert page["used_today"] == 0, "没发过 = 还没用掉名额"

    # 一个身份都不给: 谈不上"当天还剩几条", 就不报
    assert listing(client).json()["used_today"] is None


def test_unpublished_attraction_keeps_the_name_without_a_link(client, seeded, db_session):
    post(client, attraction_slug="west-lake")
    seeded["west_lake"].status = "draft"
    db_session.commit()
    attraction = listing(client).json()["items"][0]["attraction"]
    assert attraction["name"] == "西湖"
    assert attraction["slug"] is None, "下架的景点不给链接, 点了会 404"


def test_daily_limit_is_reported_in_the_page(client, seeded):
    page = listing(client).json()
    assert page["daily_limit"] == Settings().post_daily_limit
    assert page["disclaimer"]


# ------------------------------------------------------------------ 限额


def test_daily_limit_returns_structured_429(client, seeded, override_settings):
    override_settings(post_daily_limit=2)
    assert post(client).status_code == 201
    assert post(client).status_code == 201

    blocked = post(client)
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert detail["status"] == "rejected"
    assert detail["reason"] == "daily_limit_exceeded"
    assert detail["limit"] == 2
    assert detail["retry_after"], "要告诉前端什么时候能再来"


def test_rejected_request_does_not_spend_a_slot(client, seeded, override_settings):
    override_settings(post_daily_limit=1)
    assert post(client).status_code == 201
    for _ in range(3):
        assert post(client).status_code == 429
    assert listing(client, viewer="device-a").json()["used_today"] == 1


def test_limit_is_per_device(client, seeded):
    for index in range(Settings().post_daily_limit):
        assert post(client, device_id="device-a", body="第 %d 条" % index).status_code == 201
    assert post(client, device_id="device-a").status_code == 429
    assert post(client, device_id="device-b").status_code == 201, "换个人不该被连坐"


def test_posts_do_not_eat_trip_quota(client, seeded, db_session):
    """两个能力各算各的名额: 计数器带 post: 前缀, 发动态不会吃掉生成行程的次数。"""
    for index in range(3):
        assert post(client, body="第 %d 条" % index).status_code == 201
    author_id = db_session.query(AppUser.id).filter(AppUser.device_id == "device-a").scalar()
    keys = {row.owner_key for row in db_session.query(TripQuota).all()}
    # 只有 post: 那一个桶; 行程的 d:device-a 一格都没动
    assert keys == {"post:u:%d" % author_id}


def test_counter_day_is_beijing_today(client, seeded, db_session):
    post(client)
    days = {row.day for row in db_session.query(TripQuota).all()}
    assert days == {quota.today()}


# ------------------------------------------------------------------ 删除


def test_author_can_delete_and_the_slot_comes_back(client, seeded):
    created = post(client, device_id="device-a").json()
    assert listing(client, device_id="device-a").json()["used_today"] == 1

    deleted = client.delete(f"{API}/posts/{created['id']}", params={"device_id": "device-a"})
    assert deleted.status_code == 204, deleted.text
    page = listing(client, device_id="device-a").json()
    assert page["total"] == 0
    assert page["used_today"] == 0, "删掉的那条不该继续占着当天的名额"


def test_other_device_cannot_delete(client, seeded):
    created = post(client, device_id="device-a").json()
    response = client.delete(f"{API}/posts/{created['id']}", params={"device_id": "device-b"})
    assert response.status_code == 404, "不是作者要按不存在处理, 免得试出谁发过什么"
    assert listing(client).json()["total"] == 1


def test_delete_without_an_identity_is_404(client, seeded):
    created = post(client).json()
    assert client.delete(f"{API}/posts/{created['id']}").status_code == 404
    assert listing(client).json()["total"] == 1


def test_delete_unknown_post_is_404(client, seeded):
    assert client.delete(f"{API}/posts/999999", params={"device_id": "device-a"}).status_code == 404


def test_delete_by_user_id(client, seeded, user):
    created = post(client, device_id=None, user_id=user.id).json()
    assert client.delete(f"{API}/posts/{created['id']}", params={"user_id": user.id}).status_code == 204
    assert listing(client).json()["total"] == 0


def test_deleting_reports_the_page_as_mine(client, seeded):
    created = post(client, device_id="device-a").json()
    assert listing(client, device_id="device-a", viewer="device-a").json()["items"][0]["id"] == created["id"]
