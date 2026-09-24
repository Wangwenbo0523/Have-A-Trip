"""离线草稿生成的护栏测试。

这一刀的要害不是「草稿写得好不好」, 而是三条边界:
  1. 编造的数字进不了草稿(机械校验);
  2. 渲染出来的 SQL 只动 summary 一个字段;
  3. 没有任何路由会调到这个模块 —— 产物不许进运行时。
"""
from __future__ import annotations

from llm_stubs import FakeClient

from app.config import Settings
from app.llm import LLMError
from app.llm.client import LLMClient
from app.llm.draft import DRAFT_MAX, PROMPT_VERSION, draft_one, drafts, needs_draft, render_sql
from app.main import app

GOOD = "三面环山的淡水湖, 十景沿湖分布"
STAMP = "2026-09-25T00:00:00"


def _draft(attraction, payload=None, **kwargs):
    return draft_one(FakeClient(payload=payload, **kwargs), attraction)


# ---------------------------------------------------------------- 挑选

def test_needs_draft_only_for_short_or_empty_summaries(seeded):
    west = seeded["west_lake"]
    west.summary = ""
    assert needs_draft(west) is True
    west.summary = "短"
    assert needs_draft(west) is True
    west.summary = "长" * 40
    assert needs_draft(west) is False


# ---------------------------------------------------------------- 提示词

def test_prompt_only_carries_this_attraction(seeded):
    from app.llm.draft import build_system_prompt

    prompt = build_system_prompt(seeded["west_lake"])
    assert "西湖" in prompt
    assert "灵隐寺" not in prompt
    assert "故宫" not in prompt


def test_prompt_keeps_unpublished_metadata_out(seeded):
    """来源 / 许可这类字段不给模型 —— 给了它就有机会念出来。"""
    from app.llm.draft import build_system_prompt

    west = seeded["west_lake"]
    prompt = build_system_prompt(west)
    assert west.source not in prompt
    assert "license" not in prompt
    assert "status" not in prompt


# ---------------------------------------------------------------- 单条草稿

def test_accepts_grounded_draft(seeded):
    item = _draft(seeded["west_lake"], {"summary": GOOD})
    assert item.grounded is True
    assert item.degraded is False
    assert item.text == GOOD
    assert item.slug == "west-lake"


def test_keeps_previous_summary_for_review(seeded):
    item = _draft(seeded["west_lake"], {"summary": GOOD})
    assert item.before == "三面环山的淡水湖"


def test_rejects_invented_number(seeded):
    """草稿里出现档案里没有的数字, 整条作废 —— 这是最容易被当成事实的那种编造。"""
    item = _draft(seeded["west_lake"], {"summary": "西湖水面面积 6.38 平方公里"})
    assert item.grounded is False
    assert item.text == ""
    assert "6.38" in item.note


def test_rejects_overlong_draft(seeded):
    item = _draft(seeded["west_lake"], {"summary": "长" * (DRAFT_MAX + 1)})
    assert item.grounded is False
    assert str(DRAFT_MAX) in item.note


def test_rejects_draft_with_unsupported_topic(seeded):
    """档案里没有交通信息, 草稿就不许提。"""
    item = _draft(seeded["west_lake"], {"summary": "坐地铁 1 号线到龙翔桥站出来"})
    assert item.grounded is False


def test_rejects_empty_answer(seeded):
    item = _draft(seeded["west_lake"], {"summary": "   "})
    assert item.grounded is False
    assert "模型没有给出简介" in item.note


def test_without_model_nothing_is_generated(seeded):
    """离线生成必须真的用模型: 没配模型时这条跳过, 而不是拿档案硬拼一句话。"""
    item = draft_one(LLMClient(Settings(llm_provider="none")), seeded["west_lake"])
    assert item.grounded is False
    assert item.degraded is True
    assert item.text == ""
    assert "未配置模型" in item.note


def test_model_error_skips_that_attraction(seeded):
    item = _draft(seeded["west_lake"], error=LLMError("连不上模型"))
    assert item.grounded is False
    assert "模型调用失败" in item.note


def test_batch_returns_one_entry_per_attraction(seeded):
    targets = [seeded["west_lake"], seeded["palace"], seeded["terracotta"]]
    results = drafts(FakeClient(payload={"summary": GOOD}), targets)
    assert [item.slug for item in results] == ["west-lake", "palace-museum", "terracotta-army"]
    assert all(item.grounded for item in results)


# ---------------------------------------------------------------- 待审 SQL

def _statements(sql: str) -> list[str]:
    return [line for line in sql.split("\n") if line.strip() and not line.startswith("--")]


def test_render_sql_only_updates_summary(seeded):
    item = _draft(seeded["west_lake"], {"summary": GOOD})
    sql = render_sql([item], "stub-model", STAMP)
    body = [line for line in _statements(sql) if line not in ("BEGIN;", "COMMIT;")]
    assert body == ["UPDATE attraction SET summary = '%s' WHERE slug = 'west-lake';" % GOOD]
    for forbidden in ("INSERT", "DELETE", "DROP", "ALTER", "license", "status ="):
        assert forbidden not in sql


def test_render_sql_skips_ungrounded(seeded):
    bad = _draft(seeded["west_lake"], {"summary": "面积 6.38 平方公里"})
    sql = render_sql([bad], "stub-model", STAMP)
    assert "UPDATE" not in sql
    assert "未生成任何语句" in sql


def test_render_sql_escapes_single_quotes(seeded):
    item = _draft(seeded["west_lake"], {"summary": GOOD})
    item.text = "西湖又名 西子湖"
    item.text = "西湖的别称是" + chr(39) + "西子湖" + chr(39)
    sql = render_sql([item], "stub-model", STAMP)
    quoted = chr(39) * 2
    assert "西湖的别称是" + quoted + "西子湖" + quoted in sql


def test_render_sql_header_asks_for_review(seeded):
    item = _draft(seeded["west_lake"], {"summary": GOOD})
    sql = render_sql([item], "stub-model", STAMP)
    assert "请勿直接执行" in sql
    assert PROMPT_VERSION in sql
    assert "stub-model" in sql
    assert "-- 原: 三面环山的淡水湖" in sql


# ---------------------------------------------------------------- 不进运行时

def test_no_route_reaches_the_draft_module():
    """遍历真实暴露的 API 面(OpenAPI 路径), 确认没有一条通往草稿生成。"""
    paths = list(app.openapi()["paths"])
    assert not [path for path in paths if "draft" in path.lower()]
    assert "/api/v1/ai/status" in paths
