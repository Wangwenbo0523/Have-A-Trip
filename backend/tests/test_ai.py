"""一句话检索的护栏测试。

全部走打桩客户端: CI 不需要任何 key, 也不会去打真接口。
这里真正要证明的是「模型不能越权」——
编造的取值一律被丢掉, 未发布的景点无论如何都捞不出来, 模型挂了也不能变成 500。
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.llm import LLMError, get_llm_client
from app.llm.client import LLMClient, extract_json
from app.main import app

API = "/api/v1"


class FakeClient:
    """打桩客户端。刻意不继承真 LLMClient —— 否则打桩会把真实行为一起继承进来。"""

    def __init__(self, payload=None, error=None, available=True, model="fake-model"):
        self.payload = payload
        self.error = error
        self._available = available
        self.model = model
        self.calls: list[tuple[str, str]] = []

    @property
    def available(self) -> bool:
        return self._available

    def chat_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return dict(self.payload or {})


@pytest.fixture()
def use_client():
    """把打桩客户端装进依赖。用完就摘, 不给别的用例留串味。"""

    def install(fake):
        app.dependency_overrides[get_llm_client] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_llm_client, None)


def get_json(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def search(client, query, **extra):
    response = client.post(f"{API}/ai/search", json={"query": query, **extra})
    assert response.status_code == 200, response.text
    return response.json()

# ------------------------------------------------------------------ 可用性

def test_status_is_unavailable_when_unconfigured(client, use_client):
    """默认 LLM_PROVIDER=none。AI 入口是关的, 这是默认值, 不是故障。"""
    use_client(LLMClient(Settings(llm_provider="none", llm_api_key=None)))
    body = get_json(client, f"{API}/ai/status")
    assert body["available"] is False
    assert body["provider"] == "none"
    assert body["model"] is None
    assert body["disclaimer"]


def test_status_reports_cloud_provider_from_preset(client, use_client):
    """配了 provider 与 key 就算可用; base_url / model 走预设值。"""
    use_client(LLMClient(Settings(llm_provider="deepseek", llm_api_key="sk-test")))
    body = get_json(client, f"{API}/ai/status")
    assert body["available"] is True
    assert body["provider"] == "deepseek"
    assert body["model"] == "deepseek-chat"


def test_cloud_provider_without_key_is_not_available(client, use_client):
    use_client(LLMClient(Settings(llm_provider="openai", llm_api_key=None)))
    assert get_json(client, f"{API}/ai/status")["available"] is False


# ------------------------------------------------------------------ 降级

def test_search_degrades_to_keyword_when_model_off(client, seeded, use_client):
    use_client(LLMClient(Settings(llm_provider="none")))
    body = search(client, "西湖")
    assert body["interpreted"] is False
    assert body["degraded"] is True
    assert body["filters"]["q"] == "西湖"
    assert {i["slug"] for i in body["items"]} == {"west-lake"}
    # 默认配置是最常见的情况, note 必须有解释 —— 只给 degraded=true 用户会以为是自己输错了
    assert "未配置模型" in body["note"]
    assert body["disclaimer"]


def test_model_failure_degrades_instead_of_500(client, seeded, use_client):
    use_client(FakeClient(error=LLMError("连不上模型: timed out")))
    body = search(client, "西湖")
    assert body["degraded"] is True
    assert body["interpreted"] is False
    assert "模型调用失败" in body["note"]
    assert {i["slug"] for i in body["items"]} == {"west-lake"}


def test_no_useful_filter_falls_back_to_keyword(client, seeded, use_client):
    """模型什么都没解析出来时, 返回全量没有意义, 退回关键词检索更贴用户那句话。"""
    use_client(FakeClient(payload={"note": "我不确定"}))
    body = search(client, "西湖")
    assert body["degraded"] is True
    assert body["filters"]["q"] == "西湖"
    assert "已退回关键词检索" in body["note"]


def test_long_query_is_truncated_to_60(client, seeded, use_client):
    use_client(LLMClient(Settings(llm_provider="none")))
    body = search(client, "西" * 200)
    assert len(body["filters"]["q"]) == 60

# ------------------------------------------------------------------ 越权与编造防护

def test_model_filters_are_applied(client, seeded, use_client):
    use_client(FakeClient(payload={"category": "nature", "sort": "name", "note": "按自然风光筛选"}))
    body = search(client, "想看点自然的")
    assert body["interpreted"] is True and body["degraded"] is False
    assert body["filters"]["category"] == "nature"
    assert body["filters"]["sort"] == "name"
    assert body["note"] == "按自然风光筛选"
    assert {i["slug"] for i in body["items"]} == {"west-lake"}


def test_model_cannot_invent_values_or_pick_attractions(client, seeded, use_client):
    """模型给的取值必须能在库里对上; 对不上就丢, 并如实告诉用户丢了什么。"""
    use_client(FakeClient(payload={
        "category": "雪山",     # 库里没有这个分类
        "status": "draft",      # 不在白名单
        "name": "西湖",         # 模型想直接点名景点 —— 不认, 景点只能由数据库检索
        "city": "杭州",         # 库里是「杭州市」, 唯一匹配才认
        "note": "找杭州的雪山",
    }))
    body = search(client, "杭州的雪山")
    assert body["filters"]["category"] is None
    assert body["filters"]["city"] == "杭州市"
    assert body["filters"]["sort"] == "rating"
    assert "已忽略不认识的取值" in body["note"]


def test_draft_attraction_never_leaks(client, seeded, use_client):
    """无论模型怎么要, 未发布的景点都不会出现在结果里。"""
    use_client(FakeClient(payload={
        "city": "杭州市", "status": "draft",
        "note": "只看杭州",
    }))
    body = search(client, "杭州有什么景点")
    slugs = {i["slug"] for i in body["items"]}
    assert slugs == {"west-lake", "lingyin-temple"}
    assert "draft-spot" not in slugs
    # status 不在白名单, 直接被丢掉, 不可能变成一次「把 draft 也查出来」的请求
    assert "已忽略不认识的取值" in body["note"]
    assert "status" in body["note"]


def test_prompt_carries_vocabulary_not_attractions(client, seeded, use_client):
    """提示词里给的是可选值清单, 不是景点条目 —— 模型看不到结果集, 也就无从编造。"""
    fake = use_client(FakeClient(payload={"tag": "world-heritage", "note": "世界遗产"}))
    body = search(client, "世界遗产")
    system, user = fake.calls[0]
    assert "world-heritage" in system       # 真实取值
    assert "杭州市" in system
    assert "西湖" not in system              # 景点名不进提示词
    assert user == "世界遗产"
    assert {i["slug"] for i in body["items"]} == {"west-lake", "palace-museum", "terracotta-army"}


def test_unknown_grade_is_dropped(client, seeded, use_client):
    """等级是白名单枚举, 库外的取值直接丢 —— 不会变成一次偷偷放宽的查询。"""
    use_client(FakeClient(payload={"grade": "SSS", "note": "顶级"}))
    body = search(client, "顶级景点")
    assert body["filters"]["grade"] is None
    assert body["degraded"] is True          # 只剩 sort, 退回关键词检索


# ------------------------------------------------------------------ 输出解析

def test_extract_json_tolerates_code_fence_and_prose():
    """小模型爱把 JSON 裹在代码块里或前后带一句话, 这两种都要能读出来。"""
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('好的, 结果如下: {"a": 1} 以上。') == {"a": 1}


def test_extract_json_rejects_non_json():
    with pytest.raises(LLMError):
        extract_json("我不知道该怎么答")