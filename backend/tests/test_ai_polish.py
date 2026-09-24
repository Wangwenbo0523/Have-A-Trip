"""推荐理由润色的护栏测试。

这一刀的要害不是「文案好不好」, 而是**模型有没有可能碰到推荐结果**。
所以测试的重点是: 输入几条就只能输出几条, 塞不进新景点, 也改不动顺序。
"""
from __future__ import annotations

from llm_stubs import FakeClient

from app.config import Settings
from app.llm import LLMError
from app.llm.client import LLMClient
from app.llm.polish import NOTE_MAX, polish
from app.recommend.service import POPULAR_REASON

API = "/api/v1"

ENTRIES = [
    ("west-lake", "西湖", "因为它和你收藏过的「灵隐寺」相似"),
    ("palace-museum", "故宫博物院", POPULAR_REASON),
]


def notes(client, **payload):
    response = client.post(f"{API}/ai/recommend-notes", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ 纯函数

def test_polish_keeps_original_when_model_is_off():
    result = polish(LLMClient(Settings(llm_provider="none")), ENTRIES)
    assert result.polished is False
    assert result.degraded is True
    assert result.notes == {slug: reason for slug, _, reason in ENTRIES}


def test_polish_keeps_original_on_llm_error():
    result = polish(FakeClient(error=LLMError("连不上模型")), ENTRIES)
    assert result.degraded is True
    assert "模型调用失败" in result.note
    assert result.notes["west-lake"] == ENTRIES[0][2]


def test_polish_rejects_slug_that_was_not_in_the_input():
    """模型塞不进新景点 —— 输出集合只能是输入集合的子集。"""
    result = polish(
        FakeClient(payload={"notes": [
            {"slug": "west-lake", "note": "和你收藏过的灵隐寺有点像"},
            {"slug": "hacked-attraction", "note": "也看看这个"},
        ]}),
        ENTRIES,
    )
    assert set(result.notes) == {"west-lake", "palace-museum"}
    assert "hacked-attraction" in result.dropped
    assert "hacked-attraction" not in result.notes


def test_polish_fills_missing_slugs_with_original_reason():
    result = polish(
        FakeClient(payload={"notes": [{"slug": "west-lake", "note": "和你收藏过的灵隐寺有点像"}]}),
        ENTRIES,
    )
    assert result.notes["west-lake"] == "和你收藏过的灵隐寺有点像"
    # 模型没给的那条用原理由兜底, 页面不会出现空理由
    assert result.notes["palace-museum"] == POPULAR_REASON


def test_polish_rejects_note_with_unsourced_number():
    """理由里不许出现原文没有的数字 —— 那是编造。"""
    result = polish(
        FakeClient(payload={"notes": [
            {"slug": "west-lake", "note": "评分 4.9 的西湖, 和你收藏过的灵隐寺相似"},
        ]}),
        ENTRIES,
    )
    assert result.notes["west-lake"] == ENTRIES[0][2]
    assert any("west-lake" in item for item in result.dropped)


def test_polish_rejects_overlong_note():
    long_text = "这段话" * 40
    result = polish(FakeClient(payload={"notes": [{"slug": "west-lake", "note": long_text}]}), ENTRIES)
    assert len(result.notes["west-lake"]) <= NOTE_MAX
    assert result.notes["west-lake"] == ENTRIES[0][2]


def test_polish_handles_non_list_notes():
    result = polish(FakeClient(payload={"notes": "不是列表"}), ENTRIES)
    assert result.polished is False
    assert result.notes == {slug: reason for slug, _, reason in ENTRIES}


# ------------------------------------------------------------------ 接口

def test_recommend_notes_degrades_without_model(client, seeded, use_client):
    use_client(LLMClient(Settings(llm_provider="none")))
    body = notes(client, device_id="test-device-1", limit=3)
    assert body["polished"] is False
    assert body["degraded"] is True
    assert "未配置模型" in body["note"]
    assert body["reasons"]
    assert all(item["note"] == POPULAR_REASON for item in body["reasons"])
    assert body["disclaimer"]


def test_recommend_notes_polishes_and_cannot_add_entries(client, seeded, use_client):
    """模型多返回一条新景点: 它进不了结果, 其余照常润色。"""
    use_client(FakeClient(payload={"notes": [
        {"slug": "palace-museum", "note": "还没有足够的行为数据, 先给你看评分高的"},
        {"slug": "no-such-slug", "note": "凭空多出来的"},
    ]}))
    body = notes(client, device_id="test-device-1", limit=3)
    slugs = {item["slug"] for item in body["reasons"]}
    assert body["polished"] is True
    assert "no-such-slug" not in slugs
    assert "no-such-slug" in body["dropped"]
    # 输入是 3 条推荐, 输出就只能是这 3 条
    assert len(body["reasons"]) == 3


def test_recommend_notes_cover_every_recommendation(client, seeded, use_client):
    """没被改写的条目用原理由补齐 —— 推荐位不会出现空理由。"""
    use_client(FakeClient(payload={"notes": [
        {"slug": "palace-museum", "note": "还没有足够的行为数据, 先给你看评分高的"},
    ]}))
    body = notes(client, device_id="test-device-1", limit=3)
    assert len(body["reasons"]) == 3
    assert all(item["note"] for item in body["reasons"])


def test_recommend_notes_404_for_unknown_user(client, seeded, use_client):
    use_client(FakeClient(payload={"notes": []}))
    response = client.post(f"{API}/ai/recommend-notes", json={"user_id": 99999})
    assert response.status_code == 404


def test_recommend_notes_400_when_both_ids_given(client, seeded, user, use_client):
    use_client(FakeClient(payload={"notes": []}))
    response = client.post(
        f"{API}/ai/recommend-notes",
        json={"user_id": user.id, "device_id": "test-device-1"},
    )
    assert response.status_code == 400


def test_recommend_notes_treats_unknown_device_as_new_user(client, seeded, use_client):
    """没见过的设备不是错误, 与 /recommendations 同口径。"""
    use_client(FakeClient(payload={"notes": []}))
    response = client.post(f"{API}/ai/recommend-notes", json={"device_id": "brand-new-device"})
    assert response.status_code == 200
    assert response.json()["reasons"]