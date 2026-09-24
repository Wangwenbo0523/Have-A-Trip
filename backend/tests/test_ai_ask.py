"""详情页追问的护栏测试。

这一刀比检索更危险: 模型要**写字**, 写字就有编造空间。
所以测试的重点全在「答案能不能够到档案」——
数字溯源、主题词、cited 白名单, 以及三条降级路径。
"""
from __future__ import annotations

from llm_stubs import FakeClient

from app.config import Settings
from app.llm import LLMError
from app.llm.ask import fallback_answer, facts, verify
from app.llm.client import LLMClient

API = "/api/v1"


def ask(client, slug, question):
    response = client.post(f"{API}/ai/ask", json={"slug": slug, "question": question})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ verify: 机械校验

def test_archive_keeps_only_non_empty_fields(seeded):
    """空字段不进提示词 —— 免得模型拿一个空字段编出内容来。"""
    sheet = facts(seeded["west_lake"])
    assert "address" not in sheet          # 夹具里没填
    assert "a_level" not in sheet
    assert "heritage" not in sheet
    assert "plans" not in sheet            # 夹具里没有方案
    assert "suggested_hours" in sheet
    assert "最佳季节" in sheet["best_season"]


def test_verify_accepts_numbers_that_exist_in_the_archive(seeded):
    sheet = facts(seeded["west_lake"])
    ok, why = verify("建议游览 4 小时, 目前免费。", sheet)
    assert ok, why


def test_verify_rejects_numbers_that_do_not_exist_in_the_archive(seeded):
    """最容易被编造的就是价格、时长、年份 —— 这条是机械校验, 不靠模型自觉。"""
    sheet = facts(seeded["west_lake"])
    ok, why = verify("门票 60 元, 建议游览 4 小时。", sheet)
    assert not ok
    assert "60" in why


def test_verify_rejects_topic_without_any_support(seeded):
    sheet = facts(seeded["west_lake"])
    ok, why = verify("可以坐地铁过去。", sheet)
    assert not ok
    assert "地铁" in why


def test_verify_allows_topic_that_our_own_data_mentions():
    """档案自己写了「排队」, 那照着说就是有依据的 —— 不该被拦。"""
    sheet = {"plans": "旅游方案: 吴哥寺(1 天): 登顶层有人数限制, 排队通常在上午。"}
    ok, why = verify("方案里写了排队通常在上午。", sheet)
    assert ok, why


def test_verify_allows_negated_mention():
    """「档案里没有开放时间」这种否定式提及是在如实说明, 不该被当成承诺。"""
    sheet = {"name": "景点名称: 西湖"}
    ok, why = verify("档案里没有开放时间的信息。", sheet)
    assert ok, why


def test_verify_rejects_positive_mention_of_absent_topic():
    sheet = {"name": "景点名称: 西湖"}
    ok, why = verify("开放时间是早上八点。", sheet)
    assert not ok


def test_fallback_answer_is_built_from_archive_only(seeded):
    text = fallback_answer(seeded["west_lake"])
    assert "档案里没有能直接回答这个问题的内容" in text
    assert "春秋" in text          # best_season
    assert "4 小时" in text
    assert "免费" in text          # ticket_price = 0
    assert "杭州市" in text

# ------------------------------------------------------------------ 降级

def test_ask_degrades_when_model_is_off(client, seeded, use_client):
    use_client(LLMClient(Settings(llm_provider="none")))
    body = ask(client, "west-lake", "适合带小孩吗?")
    assert body["degraded"] is True
    assert body["grounded"] is False
    assert "未配置模型" in body["note"]
    assert "档案里没有能直接回答这个问题的内容" in body["answer"]
    assert body["disclaimer"]


def test_ask_degrades_on_llm_error(client, seeded, use_client):
    use_client(FakeClient(error=LLMError("连不上模型: timed out")))
    body = ask(client, "west-lake", "适合带小孩吗?")
    assert body["degraded"] is True
    assert "模型调用失败" in body["note"]


def test_ask_degrades_when_model_returns_no_answer(client, seeded, use_client):
    use_client(FakeClient(payload={"cited": ["summary"]}))
    body = ask(client, "west-lake", "适合带小孩吗?")
    assert body["degraded"] is True
    assert "没有给出答案" in body["note"]


# ------------------------------------------------------------------ 溯源

def test_ask_returns_model_answer_when_it_checks_out(client, seeded, use_client):
    use_client(FakeClient(payload={
        "answer": "建议游览 4 小时, 目前免票。",
        "cited": ["suggested_hours", "ticket_price"],
    }))
    body = ask(client, "west-lake", "要逛多久?")
    assert body["grounded"] is True
    assert body["degraded"] is False
    assert body["answer"] == "建议游览 4 小时, 目前免票。"
    assert body["cited"] == ["suggested_hours", "ticket_price"]
    assert body["note"] == ""


def test_ask_discards_answer_with_unsourced_number(client, seeded, use_client):
    use_client(FakeClient(payload={
        "answer": "门票 60 元, 建议游览 4 小时。",
        "cited": ["ticket_price"],
    }))
    body = ask(client, "west-lake", "门票多少?")
    assert body["grounded"] is False
    assert body["degraded"] is True
    assert "找不到" in body["note"]
    # 换成了有依据的档案摘录, 而不是把编造的内容返回给用户
    assert "60" not in body["answer"]
    assert "档案里没有能直接回答这个问题的内容" in body["answer"]


def test_ask_discards_answer_about_absent_topic(client, seeded, use_client):
    use_client(FakeClient(payload={"answer": "可以坐地铁直达。", "cited": []}))
    body = ask(client, "west-lake", "怎么去?")
    assert body["grounded"] is False
    assert "地铁" in body["note"]


def test_ask_keeps_only_real_field_names_in_cited(client, seeded, use_client):
    """模型可能报一些不存在的字段名, 只有真实存在且非空的才算数。"""
    use_client(FakeClient(payload={
        "answer": "建议游览 4 小时。",
        "cited": ["suggested_hours", "status", "lat", "suggested_hours", "address"],
    }))
    body = ask(client, "west-lake", "要逛多久?")
    assert body["cited"] == ["suggested_hours"]
    assert body["dropped"] == ["status", "lat", "address"]


def test_ask_prompt_carries_only_this_attraction(client, seeded, use_client):
    """模型只看到这一个景点的档案, 不该看到别的景点。"""
    fake = use_client(FakeClient(payload={"answer": "建议游览 4 小时。", "cited": []}))
    ask(client, "west-lake", "要逛多久?")
    system, user = fake.calls[0]
    assert "西湖" in system
    assert "灵隐寺" not in system
    assert "故宫" not in system
    assert user == "要逛多久?"


# ------------------------------------------------------------------ 出入参与 404

def test_ask_404_for_unknown_slug(client, seeded, use_client):
    use_client(FakeClient(payload={"answer": "x", "cited": []}))
    response = client.post(f"{API}/ai/ask", json={"slug": "no-such-spot", "question": "问一句"})
    assert response.status_code == 404


def test_ask_404_for_draft_attraction(client, seeded, use_client):
    """未发布的景点连追问都不该存在 —— 与列表/详情同一口径。"""
    use_client(FakeClient(payload={"answer": "x", "cited": []}))
    response = client.post(f"{API}/ai/ask", json={"slug": "draft-spot", "question": "问一句"})
    assert response.status_code == 404


def test_ask_rejects_empty_question(client, seeded, use_client):
    use_client(FakeClient(payload={"answer": "x", "cited": []}))
    response = client.post(f"{API}/ai/ask", json={"slug": "west-lake", "question": ""})
    assert response.status_code == 422


def test_ask_is_listed_in_ai_status_disclaimer(client, seeded, use_client):
    use_client(LLMClient(Settings(llm_provider="none")))
    body = client.get(f"{API}/ai/status").json()
    assert body["available"] is False
    assert body["disclaimer"]