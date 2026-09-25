"""行程生成的测试。

两条主线:
  * validator 的规则表 —— 每一条拒绝都必须真的拒掉。这是幻觉的唯一防线。
  * 接口与限额 —— 202/200/429/404 的语义, 以及「模型挂了不能变成 500」。

模型全程打桩: 生成跑在后台任务里, 不走依赖注入, 所以用 trip_model / trip_embedding
两个夹具替换 service 里的工厂函数(见 app/trip/service.py 的 build_llm / build_embedding)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from llm_stubs import FakeClient, FakeEmbeddingClient, ScriptedClient

from app.llm import LLMError
from app.models import Attraction, Itinerary, TripQuota
from app.trip import quota
from app.trip import service as trip_service
from app.trip.validator import ValidationError, validate

API = '/api/v1'


# ------------------------------------------------------------------ 夹具

@pytest.fixture()
def trip_model(monkeypatch):
    """替换行程生成用的对话客户端。"""

    def install(fake):
        monkeypatch.setattr(trip_service, 'build_llm', lambda settings: fake)
        return fake

    return install


@pytest.fixture()
def trip_embedding(monkeypatch):
    """替换候选召回用的向量客户端。"""

    def install(fake):
        monkeypatch.setattr(trip_service, 'build_embedding', lambda settings: fake)
        return fake

    return install


def _pool(seeded):
    """候选池的顺序由 build 里的热度排序决定: 评分高的在前。"""
    return [
        seeded['palace'].id,
        seeded['west_lake'].id,
        seeded['terracotta'].id,
        seeded['lingyin'].id,
        seeded['ocean_world'].id,
    ]


def reply(seeded, days=1, ids=None):
    """模型的标准回复: 每天一站, 景点在候选池里轮着取。"""
    pool = ids or _pool(seeded)
    return {
        'items': [
            {
                'day_index': day,
                'seq': 1,
                'attraction_id': pool[(day - 1) % len(pool)],
                'note': '第 %d 天' % day,
                'reason': '符合你的需求',
            }
            for day in range(1, days + 1)
        ]
    }


def body(text, days=1, **extra):
    return {'request_text': text, 'days': days, 'device_id': 'test-device-1', **extra}


# ------------------------------------------------------------------ validator 规则表

def _item(**over):
    base = {'day_index': 1, 'seq': 1, 'attraction_id': 1, 'note': '上午出发', 'reason': '不爬山'}
    base.update(over)
    return base


def _validate(raw, *, days=1, max_per_day=6, candidates=None, sufficient=True):
    return validate(
        raw,
        candidate_ids=candidates if candidates is not None else {1, 2, 3},
        days=days,
        max_per_day=max_per_day,
        candidates_sufficient=sufficient,
    )


def test_valid_payload_is_sorted_by_day_and_seq():
    items, note = _validate(
        {
            'items': [
                _item(day_index=2, seq=1, attraction_id=2),
                _item(day_index=1, seq=2, attraction_id=3),
                _item(day_index=1, seq=1),
            ]
        },
        days=2,
    )
    assert [(entry.day_index, entry.seq) for entry in items] == [(1, 1), (1, 2), (2, 1)]
    assert note is None


def test_attraction_outside_candidates_is_refused():
    """**幻觉防线**: 候选集外的 attraction_id 整份拒掉, 不是偷偷丢掉那一条。

    越界说明模型在编景点, 那么它没越界的那几条也没有可信度 —— 只丢单条会让用户
    拿到一份看起来正常、里面一半是编的行程。
    """
    with pytest.raises(ValidationError, match='不在候选集'):
        _validate({'items': [_item(attraction_id=999)]})


def test_empty_items_is_a_failure_not_an_empty_success():
    with pytest.raises(ValidationError, match='0 条'):
        _validate({'items': []})


def test_missing_items_array_is_refused():
    with pytest.raises(ValidationError, match='items'):
        _validate({'plan': []})


def test_day_index_beyond_requested_days_is_refused():
    with pytest.raises(ValidationError, match='day_index'):
        _validate({'items': [_item(day_index=3)]}, days=2)


def test_seq_must_be_continuous_from_one():
    with pytest.raises(ValidationError, match='seq'):
        _validate({'items': [_item(seq=1), _item(seq=3, attraction_id=2)]})


def test_too_many_stops_in_one_day_is_refused():
    """单独测每天上限: 天数给 2, 免得先撞上「总条数」那条规则。"""
    with pytest.raises(ValidationError, match='超过每天'):
        _validate(
            {
                'items': [
                    _item(day_index=1, seq=1),
                    _item(day_index=1, seq=2, attraction_id=2),
                    _item(day_index=1, seq=3, attraction_id=3),
                ]
            },
            days=2,
            max_per_day=2,
        )


def test_total_over_the_global_cap_is_refused():
    with pytest.raises(ValidationError, match='总条数'):
        _validate(
            {
                'items': [
                    _item(day_index=1, seq=1),
                    _item(day_index=1, seq=2, attraction_id=2),
                    _item(day_index=2, seq=1, attraction_id=3),
                ]
            },
            days=2,
            max_per_day=1,
        )


def test_incomplete_day_coverage_is_refused_when_candidates_are_enough():
    with pytest.raises(ValidationError, match='覆盖'):
        _validate({'items': [_item(day_index=1, seq=1)]}, days=3)


def test_missing_days_allowed_only_when_candidates_are_insufficient():
    """候选景点比天数还少时「排不满」是数据问题, 不是模型的问题: 放行并说明。"""
    items, note = _validate(
        {'items': [_item(day_index=1, seq=1), _item(day_index=2, seq=1, attraction_id=2)]},
        days=4,
        sufficient=False,
    )
    assert len(items) == 2
    assert note and '不足' in note


def test_non_contiguous_days_still_refused_when_candidates_insufficient():
    with pytest.raises(ValidationError, match='天数不连续'):
        _validate(
            {'items': [_item(day_index=1, seq=1), _item(day_index=3, seq=1, attraction_id=2)]},
            days=4,
            sufficient=False,
        )


def test_repeating_the_same_attraction_is_refused():
    """同一个景点排两遍要整份拒掉, 不是偷偷去掉后一条。

    真实模型(本机 qwen2.5:7b)在 3 天杭州的实测里把西湖排进第 1、2 天、宋城排进
    第 1、3 天, 而且两条 reason 一字不差 —— 一格一天的行程里这是白白浪费一天,
    但页面看上去完全正常。上层带着这条原因重试一次, 模型通常就能改对。
    """
    with pytest.raises(ValidationError, match='两次'):
        _validate(
            {'items': [_item(day_index=1, seq=1, attraction_id=2), _item(day_index=2, seq=1, attraction_id=2)]},
            days=2,
        )


def test_same_attraction_twice_in_one_day_is_refused():
    with pytest.raises(ValidationError, match='两次'):
        _validate({'items': [_item(seq=1, attraction_id=2), _item(seq=2, attraction_id=2)]})


def test_distinct_attractions_are_not_affected_by_the_repeat_rule():
    """反向对照: 同一景点不重复的规则不能把「两天去两个地方」也拦下来。"""
    items, note = _validate(
        {'items': [_item(day_index=1, seq=1, attraction_id=1), _item(day_index=2, seq=1, attraction_id=2)]},
        days=2,
    )
    assert len(items) == 2
    assert note is None


def test_note_and_reason_are_trimmed_and_defaulted():
    items, _ = _validate({'items': [_item(note='   ', reason='')]})
    assert items[0].note.strip()
    assert items[0].reason.strip()


def test_overlong_text_is_truncated():
    items, _ = _validate({'items': [_item(note='长' * 500)]})
    assert len(items[0].note) <= 120


def test_numeric_strings_are_accepted_but_booleans_are_not():
    items, _ = _validate({'items': [_item(day_index='1', seq='1', attraction_id='2')]})
    assert items[0].attraction_id == 2
    with pytest.raises(ValidationError):
        _validate({'items': [_item(attraction_id=True)]})


# ------------------------------------------------------------------ 接口

def test_create_then_poll_reaches_succeeded(client, seeded, trip_model):
    # 需求里点了杭州, 候选就只从杭州取(见 candidates_for), 所以模型这里必须挑杭州的景点。
    # 原先这句用的是默认候选池, 排在第一位的是北京的故宫 —— 那正是 R5 报的毛病。
    trip_model(FakeClient(payload=reply(seeded, ids=[seeded['west_lake'].id])))
    response = client.post(f'{API}/itineraries', json=body('带小孩去杭州玩一天, 不想爬山', days=1))
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted['status'] == 'pending'
    assert accepted['token'].startswith('itn_')

    polled = client.get(f'{API}/itineraries/{accepted["token"]}')
    assert polled.status_code == 200, polled.text
    result = polled.json()
    assert result['status'] == 'succeeded'
    assert [entry['name'] for entry in result['items']] == ['西湖']
    assert result['usage'] == {'prompt_tokens': 100, 'completion_tokens': 50}
    assert result['max_poll_seconds'] > 0
    assert result['disclaimer']


def test_token_is_not_enumerable(client, db_session, seeded, trip_model):
    """用自增 id 取行程的话, 递增就能读到别人的需求原文。"""
    trip_model(FakeClient(payload=reply(seeded)))
    accepted = client.post(f'{API}/itineraries', json=body('带小孩去杭州玩一天', days=1)).json()
    assert accepted['token'] not in {'1', '2'}
    for probe in ('1', '2', '999999'):
        assert client.get(f'{API}/itineraries/{probe}').status_code == 404


def test_same_request_is_reused_and_calls_the_model_once(client, seeded, trip_model):
    fake = trip_model(FakeClient(payload=reply(seeded)))
    first = client.post(f'{API}/itineraries', json=body('同一个需求', days=1))
    second = client.post(f'{API}/itineraries', json=body('同一个需求', days=1))
    assert first.status_code == 202
    assert second.status_code == 200, '命中已有行程不该再排一次队'
    assert second.json()['token'] == first.json()['token']
    assert len(fake.calls) == 1, '同一份需求只该调一次模型'


def test_whitespace_only_difference_counts_as_the_same_request(client, seeded, trip_model):
    # 这份输出必须是合法的: 不合法会走重试, 那就变成在数重试的次数, 而不是在测
    # 「压掉空白之后还是不是同一份需求」了
    fake = trip_model(FakeClient(payload=reply(seeded, days=1, ids=[seeded['west_lake'].id])))
    client.post(f'{API}/itineraries', json=body('杭州  三天  不爬山', days=1))
    client.post(f'{API}/itineraries', json=body('杭州 三天 不爬山', days=1))
    assert len(fake.calls) == 1


def test_daily_limit_returns_structured_429(client, seeded, trip_model):
    trip_model(FakeClient(payload=reply(seeded)))
    for index in range(5):
        response = client.post(f'{API}/itineraries', json=body('第 %d 个需求' % index, days=1))
        assert response.status_code == 202, response.text

    blocked = client.post(f'{API}/itineraries', json=body('第六个需求', days=1))
    assert blocked.status_code == 429
    detail = blocked.json()['detail']
    assert detail['status'] == 'rejected'
    assert detail['reason'] == 'daily_limit_exceeded'
    assert detail['limit'] == 5
    assert detail['retry_after'], '要给前端一个「什么时候再来」的答案'


def test_rejected_request_does_not_spend_a_slot(client, seeded, trip_model):
    """被限额拦下的请求不该把自己也算进计数器, 否则额度会提前耗尽。"""
    trip_model(FakeClient(payload=reply(seeded)))
    for index in range(5):
        client.post(f'{API}/itineraries', json=body('需求 %d' % index, days=1))
    for _ in range(3):
        assert client.post(f'{API}/itineraries', json=body('再来一次', days=1)).status_code == 429


def test_global_budget_refuses_new_requests(client, db_session, seeded, trip_model):
    trip_model(FakeClient(payload=reply(seeded)))
    quota.ensure_row(db_session, quota.GLOBAL_OWNER, quota.today())
    db_session.execute(
        update(TripQuota)
        .where(TripQuota.owner_key == quota.GLOBAL_OWNER, TripQuota.day == quota.today())
        .values(tokens_used=10 ** 9)
    )
    db_session.commit()

    response = client.post(f'{API}/itineraries', json=body('预算用尽', days=1))
    assert response.status_code == 429
    assert response.json()['detail']['reason'] == 'global_budget_exhausted'


def test_model_failure_becomes_failed_status_not_500(client, seeded, trip_model):
    trip_model(FakeClient(error=LLMError('连不上模型')))
    accepted = client.post(f'{API}/itineraries', json=body('模型挂了', days=1)).json()
    response = client.get(f'{API}/itineraries/{accepted["token"]}')
    assert response.status_code == 200, '生成失败不该让轮询接口 500'
    result = response.json()
    assert result['status'] == 'failed'
    assert '连不上模型' in result['error']
    assert result['items'] == [], '失败时不能留半截条目'


def test_hallucinated_attraction_fails_the_whole_itinerary(client, seeded, trip_model):
    trip_model(FakeClient(payload={'items': [_item(attraction_id=987654)]}))
    accepted = client.post(f'{API}/itineraries', json=body('编一个景点', days=1)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()
    assert result['status'] == 'failed'
    assert '候选集' in result['error']


def _short_reply(seeded, days=2, only_day=1):
    """漏排了其余天数的不合法输出 —— 线上那次「只要 3 天却只给第 3 天」就是这个形态。"""
    return {
        'items': [
            {
                'day_index': only_day,
                'seq': 1,
                'attraction_id': seeded['west_lake'].id,
                'note': '只排了一天',
                'reason': '漏排',
            }
        ]
    }


def test_invalid_output_is_retried_with_the_failure_reason(client, seeded, trip_model):
    """输出不合法先别判失败: 带上失败原因再要一次, 第二次通常就对了。"""
    fake = trip_model(
        ScriptedClient(
            [
                _short_reply(seeded, days=2),
                reply(seeded, days=2, ids=[seeded['west_lake'].id, seeded['lingyin'].id]),
            ]
        )
    )
    accepted = client.post(f'{API}/itineraries', json=body('带小孩去杭州玩两天', days=2)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()

    assert result['status'] == 'succeeded'
    assert [entry['day_index'] for entry in result['items']] == [1, 2]
    assert len(fake.calls) == 2, '第一次不合法必须再要一次'
    assert '上一次的输出不合法' in fake.calls[1][1], '重试要把失败原因回灌给模型'
    assert '覆盖' in fake.calls[1][1], '回灌的必须是真原因, 不是一句「再试一次」'
    # 重试花的 token 也算这一次生成的开销, 否则限额会漏记
    assert result['usage'] == {'prompt_tokens': 200, 'completion_tokens': 100}


def test_retry_gives_up_and_says_how_many_attempts(client, seeded, trip_model):
    """两次都不合法才判失败, 且错误里说清重试过 —— 否则用户看到的报错与第一次毫无区别。"""
    fake = trip_model(ScriptedClient([_short_reply(seeded, days=2), _short_reply(seeded, days=2)]))
    accepted = client.post(f'{API}/itineraries', json=body('带小孩去杭州玩两天', days=2)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()

    assert result['status'] == 'failed'
    assert len(fake.calls) == 2, '重试次数用完就收手, 不无限重发'
    assert '重试' in result['error']
    assert result['items'] == []


def test_zero_retries_keeps_the_single_attempt_behaviour(seeded):
    """trip_generate_retries=0 时就是老行为: 一次不合法即失败, 不重复花钱。"""
    fake = ScriptedClient([_short_reply(seeded, days=2)])
    with pytest.raises(ValidationError, match='覆盖'):
        trip_service._draft(
            fake,
            request_text='杭州两天',
            days=2,
            max_per_day=6,
            max_tokens=200,
            retries=0,
            candidates=[seeded['west_lake'], seeded['lingyin']],
        )
    assert len(fake.calls) == 1

def test_daily_cap_is_tightened_when_candidates_cannot_fill_it(seeded):
    """候选比「天数 x 每天站数」还少时, 提示词里的每天站数要跟着收紧。

    否则 4 个候选、3 天每天 2 站就只能靠重复安排凑数 —— 本机 qwen2.5:7b 实测正是
    这么干的。收紧之后模型被要求「每天 1 到 1 站」, 不重复也排得满。
    """
    pool = [seeded['palace'], seeded['west_lake'], seeded['terracotta'], seeded['lingyin']]
    fake = FakeClient(payload=reply(seeded, days=3, ids=[a.id for a in pool]))
    trip_service._draft(
        fake,
        request_text='杭州三天',
        days=3,
        max_per_day=6,
        max_tokens=200,
        retries=0,
        candidates=pool,
    )
    system, _user = fake.calls[0]
    assert '每天 1 到 1 站' in system, '4 个候选 / 3 天时每天不该还要 6 站'


def test_daily_cap_only_moves_down_never_up(seeded):
    """反向对照: 这条收紧只往下走, 不会把配置里的上限往上抬。"""
    pool = [seeded['palace'], seeded['west_lake'], seeded['terracotta'], seeded['lingyin'], seeded['ocean_world']]
    fake = FakeClient(payload=reply(seeded, days=1, ids=[seeded['west_lake'].id]))
    trip_service._draft(
        fake,
        request_text='想去哪儿都行',
        days=1,
        max_per_day=2,
        max_tokens=200,
        retries=0,
        candidates=pool,
    )
    system, _user = fake.calls[0]
    assert '每天 1 到 2 站' in system, '候选比上限多时该按配置走, 不该被抬到 5'


def test_draft_attraction_is_never_a_candidate(client, seeded, trip_model):
    """未发布景点不可能被模型选中, 因为候选集里压根没有它。"""
    trip_model(FakeClient(payload={'items': [_item(attraction_id=seeded['draft'].id)]}))
    accepted = client.post(f'{API}/itineraries', json=body('未发布景点', days=1)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()
    assert result['status'] == 'failed'


def test_candidates_come_from_vectors_when_available(client, db_session, seeded, trip_model, trip_embedding):
    """有向量时候选由语义召回决定: 只灌灵隐寺的向量, 它就应该是唯一候选。"""
    from app.models import AttractionEmbedding
    from app.search import canonical, semantic
    from app.search.vectors import encode

    fake_embedding = FakeEmbeddingClient(dim=64)
    for slug in ('lingyin', 'palace'):
        attraction = seeded[slug]
        text = canonical.canonical_text(attraction)
        db_session.add(
            AttractionEmbedding(
                attraction_id=attraction.id,
                model='fake-embedding',
                dim=64,
                pipeline_version=canonical.PIPELINE_VERSION,
                content_hash=canonical.content_hash(text, 'fake-embedding'),
                embedding=encode(fake_embedding.vector_of(text)),
            )
        )
    db_session.commit()
    assert semantic.active_model(db_session) == 'fake-embedding'

    trip_embedding(fake_embedding)
    trip_model(FakeClient(payload=reply(seeded, ids=[seeded['lingyin'].id])))
    accepted = client.post(f'{API}/itineraries', json=body('杭州的佛教寺院', days=1)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()
    assert result['status'] == 'succeeded'
    assert [entry['name'] for entry in result['items']] == ['灵隐寺']


def test_stale_generation_is_reclaimed_on_poll(client, db_session, seeded):
    """进程死掉留下的 generating 不能让人一直转圈。"""
    old = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db_session.add(
        Itinerary(
            public_token='itn_stale',
            owner_key='d:test-device-1',
            days=1,
            request_hash='h',
            status='generating',
            cache_key='k',
            started_at=old,
            heartbeat_at=old,
        )
    )
    db_session.commit()

    result = client.get(f'{API}/itineraries/itn_stale').json()
    assert result['status'] == 'failed'
    assert '中断' in result['error']


def test_fresh_generation_is_not_reclaimed(client, db_session, seeded):
    """心跳还很新的任务不能被误杀 —— 多 worker 下按耗时一刀切就会这样。"""
    now = datetime.now(timezone.utc)
    db_session.add(
        Itinerary(
            public_token='itn_alive',
            owner_key='d:test-device-1',
            days=1,
            request_hash='h2',
            status='generating',
            cache_key='k2',
            started_at=now,
            heartbeat_at=now,
        )
    )
    db_session.commit()

    assert client.get(f'{API}/itineraries/itn_alive').json()['status'] == 'generating'


def test_unknown_user_is_rejected(client, seeded, trip_model):
    trip_model(FakeClient(payload=reply(seeded)))
    response = client.post(f'{API}/itineraries', json={'request_text': 'x', 'days': 1, 'user_id': 424242})
    assert response.status_code == 404


def test_both_owners_is_a_validation_error(client, seeded):
    response = client.post(
        f'{API}/itineraries',
        json={'request_text': 'x', 'days': 1, 'user_id': 1, 'device_id': 'd'},
    )
    assert response.status_code == 422


def test_days_out_of_range_is_a_validation_error(client, seeded):
    assert client.post(f'{API}/itineraries', json=body('x', days=0)).status_code == 422
    assert client.post(f'{API}/itineraries', json=body('x', days=99)).status_code == 422


def test_openapi_documents_the_new_endpoints(client):
    paths = client.get('/openapi.json').json()['paths']
    assert '/api/v1/itineraries' in paths
    assert '/api/v1/itineraries/{token}' in paths
    assert '/api/v1/search/semantic' in paths


# ------------------------------------------------- 候选的城市约束 (R5)

def test_city_in_text_reads_the_city_without_calling_the_model(db_session, seeded):
    """认城市名靠扫库里的城市清单, 不为它多调一次模型。"""
    assert trip_service.city_in_text(db_session, '杭州三天') == '杭州市'
    assert trip_service.city_in_text(db_session, '不想爬山') is None
    # 同时提到两个城市: 认不出, 交回给全库召回 —— 硬挑一个只会更糟
    assert trip_service.city_in_text(db_session, '杭州和上海都想去') is None


def test_candidates_are_restricted_to_the_city_in_the_request(db_session, seeded):
    """需求点了城市, 候选就只从那座城市里取。"""
    from app.config import get_settings

    candidates = trip_service.candidates_for(
        db_session, request_text='带小孩去杭州玩两天', settings=get_settings(), days=2
    )
    assert {attraction.slug for attraction in candidates} == {'west-lake', 'lingyin-temple'}


def test_candidates_widen_only_when_the_city_cannot_fill_a_day(db_session, seeded):
    """同城连一天一站都排不满时才放宽, 且同城景点仍然排在最前面。"""
    from app.config import get_settings

    candidates = trip_service.candidates_for(
        db_session, request_text='去上海市玩三天', settings=get_settings(), days=3
    )
    # 上海市只有海洋世界一个, 3 天排不满 -> 放宽到全库, 但它必须还在首位
    assert candidates[0].slug == 'ocean-world'
    assert len(candidates) > 1
    assert len({attraction.id for attraction in candidates}) == len(candidates)


def test_itinerary_never_mixes_cities_when_the_request_names_one(client, seeded, trip_model):
    """整条链路的验收: 「去杭州」排出来的每一站都在杭州。"""
    trip_model(
        FakeClient(payload=reply(seeded, days=2, ids=[seeded['west_lake'].id, seeded['lingyin'].id]))
    )
    accepted = client.post(f'{API}/itineraries', json=body('带小孩去杭州玩两天', days=2)).json()
    result = client.get(f'{API}/itineraries/{accepted["token"]}').json()
    assert result['status'] == 'succeeded'
    assert [entry['name'] for entry in result['items']] == ['西湖', '灵隐寺']
