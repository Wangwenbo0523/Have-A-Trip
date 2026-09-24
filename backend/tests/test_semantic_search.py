"""语义检索的测试。

全部走打桩向量: CI 不需要 key, 也不会去调真接口。这里要证明的不是「模型准不准」,
而是几件工程上的事:
  * 指纹把模型算进去了 —— 换模型必须让旧向量整体失效
  * 向量不可用 / 没有向量 / 维度不一致, 都退回关键词检索而不是报错或返回空
  * 未发布的景点无论如何都不会冒出来
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from llm_stubs import FakeEmbeddingClient

from app.config import Settings
from app.llm.embedding import EmbeddingClient, EmbeddingError
from app.models import Attraction, AttractionEmbedding
from app.search import canonical, semantic
from app.search.vectors import cosine, decode, encode

API = '/api/v1'
MODEL = 'fake-embedding'
# 维度取大一点: 打桩向量是字符袋哈希, 维度太小会让不相干的文本撞进同一个桶,
# 排序就变成随机噪声, 断言也就失去意义。
DIM = 64


def _store_vectors(db_session, *, model=MODEL, dim=DIM, only=None):
    """给已发布景点灌打桩向量。only 限定范围(用来造维度不一致的场景)。"""
    fake = FakeEmbeddingClient(dim=dim, model=model)
    rows = db_session.scalars(
        select(Attraction).where(Attraction.status == 'published')
    ).all()
    vectors = {}
    for attraction in rows:
        if only is not None and attraction.slug not in only:
            continue
        text = canonical.canonical_text(attraction)
        vector = fake.vector_of(text)
        vectors[attraction.slug] = vector
        db_session.add(
            AttractionEmbedding(
                attraction_id=attraction.id,
                model=model,
                dim=dim,
                pipeline_version=canonical.PIPELINE_VERSION,
                content_hash=canonical.content_hash(text, model),
                embedding=encode(vector),
            )
        )
    db_session.commit()
    return vectors


def _published_count(db_session):
    return db_session.scalar(
        select(func.count()).select_from(Attraction).where(Attraction.status == 'published')
    )


def semantic_search(client, query, **extra):
    response = client.post(f'{API}/search/semantic', json={'query': query, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def slugs(body):
    return [hit['attraction']['slug'] for hit in body['items']]


# ------------------------------------------------------------------ 文本与指纹

def test_canonical_text_is_byte_stable(db_session, seeded):
    """同一份档案必须拼出逐字节相同的文本, 否则 hash 漂, 全量重算变成日常。"""
    attraction = seeded['west_lake']
    assert canonical.canonical_text(attraction) == canonical.canonical_text(attraction)
    # 标签按名称排序, 不依赖数据库返回顺序
    assert '标签: 世界遗产 免票' in canonical.canonical_text(attraction)


def test_content_hash_includes_the_model(seeded):
    """**换向量模型必须让指纹失效。**

    指纹里不含模型的话, 换模型后所有 content_hash 依然对得上, 增量更新一条都不重建,
    而新模型的查询向量与旧模型的库存向量根本不可比 —— 表现是语义搜索整体返回空,
    界面上却看不出异常。这是最难查的一类故障。
    """
    text = canonical.canonical_text(seeded['west_lake'])
    assert canonical.content_hash(text, 'model-a') != canonical.content_hash(text, 'model-b')


def test_content_hash_leaves_text_changes_visible():
    assert canonical.content_hash('a', 'm') != canonical.content_hash('b', 'm')


# ------------------------------------------------------------------ 向量工具

def test_encode_decode_roundtrip():
    vector = [0.5, -1.25, 3.0]
    assert decode(encode(vector)) == vector


def test_cosine_of_identical_vectors_is_one():
    vector = [1.0, 2.0, 3.0]
    assert cosine(vector, vector) == pytest.approx(1.0)


def test_cosine_of_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_of_mismatched_lengths_is_zero():
    """长度不等不抛异常也不截断 —— 返回 0 让它必然排到最后。"""
    assert cosine([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0
    assert cosine([], []) == 0.0


# ------------------------------------------------------------------ 可用性

def test_embedding_unavailable_without_provider(seeded):
    """默认 EMBEDDING_PROVIDER=inherit 跟随 LLM_PROVIDER=none, 两边都没配。"""
    assert EmbeddingClient(Settings(llm_provider='none')).available is False


def test_embedding_follows_llm_provider_with_key():
    """inherit 的语义: 配了云端 LLM 与 key, 向量客户端也算配好了。"""
    embedding = EmbeddingClient(Settings(llm_provider='openai', llm_api_key='sk-test'))
    assert embedding.available is True
    assert embedding.model == 'text-embedding-3-small'
    assert embedding.signature == 'openai:text-embedding-3-small:auto'


def test_embedding_without_model_is_not_available():
    """deepseek 预设没有向量模型 —— 没配 EMBEDDING_MODEL 时不该假装可用。"""
    embedding = EmbeddingClient(Settings(llm_provider='deepseek', llm_api_key='sk-test'))
    assert embedding.available is False


def test_owner_scopes_are_distinguishable():
    """id=7 的用户与 device_id='7' 的设备不能共享一份缓存, 否则会读到对方的行程。"""
    from app.trip.service import owner_key_for

    assert owner_key_for(7, None) != owner_key_for(None, '7')


# ------------------------------------------------------------------ 检索

def test_semantic_search_ranks_by_vector_similarity(client, db_session, seeded, use_embedding):
    _store_vectors(db_session)
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    body = semantic_search(client, '三面环山的淡水湖 西湖 春秋')
    assert body['degraded'] is False
    assert body['model'] == MODEL
    assert body['items'][0]['attraction']['slug'] == 'west-lake'
    assert body['items'][0]['match'] == 'semantic'
    assert body['items'][0]['score'] > 0


def test_semantic_search_reports_coverage(client, db_session, seeded, use_embedding):
    _store_vectors(db_session)
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    body = semantic_search(client, '西湖')
    total = _published_count(db_session)
    assert body['embedded'] == total
    assert body['published'] == total


def test_semantic_search_never_returns_draft(client, db_session, seeded, use_embedding):
    """draft 景点即使有向量也不能出现在结果里。"""
    _store_vectors(db_session)
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    body = semantic_search(client, '未发布景点 不该出现在任何接口里', limit=20)
    assert 'draft-spot' not in slugs(body)


def test_semantic_search_degrades_when_vector_service_fails(client, db_session, seeded, use_embedding):
    _store_vectors(db_session)
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL, error=EmbeddingError('连不上')))
    body = semantic_search(client, '西湖')
    assert body['degraded'] is True
    assert 'west-lake' in slugs(body), '向量服务挂了要退回关键词检索'


def test_semantic_search_degrades_without_any_vector(client, seeded, use_embedding):
    """库内还没有向量: 退回关键词检索, 而不是给一屏空结果。"""
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    body = semantic_search(client, '西湖')
    assert body['degraded'] is True
    assert 'west-lake' in slugs(body)


def test_mixed_dimensions_are_refused(client, db_session, seeded, use_embedding):
    """同一模型下混了两种维度: 算出来的相似度是垃圾, 必须整体退回关键词。"""
    _store_vectors(db_session, dim=8, only=('west-lake', 'palace-museum', 'terracotta-army'))
    _store_vectors(db_session, dim=16, only=('lingyin-temple', 'ocean-world'))
    use_embedding(FakeEmbeddingClient(dim=8, model=MODEL))
    assert semantic.model_dim(db_session, MODEL) is None
    body = semantic_search(client, '西湖')
    assert body['degraded'] is True
    assert 'west-lake' in slugs(body)


# ------------------------------------------------------------------ 相似景点

def test_similar_returns_non_empty_without_vectors(client, seeded):
    """升级前的行为: 没有向量时与原来一致, 仍然非空。"""
    response = client.get(f'{API}/attractions/west-lake/similar')
    assert response.status_code == 200, response.text
    assert [row['slug'] for row in response.json()]


def test_similar_never_returns_empty_even_for_isolated_attraction(client, seeded):
    """海洋世界与谁都不像(无标签/异分类/异城市), 但页面不能空着 —— 热度兜底。"""
    response = client.get(f'{API}/attractions/ocean-world/similar')
    assert response.status_code == 200, response.text
    assert response.json(), '相似景点塌掉会很难看, 必须有兜底'


def test_similar_uses_vectors_when_available(client, db_session, seeded, use_embedding):
    _store_vectors(db_session)
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    response = client.get(f'{API}/attractions/west-lake/similar')
    assert response.status_code == 200, response.text
    found = [row['slug'] for row in response.json()]
    assert found
    assert 'west-lake' not in found, '自己不该出现在自己的相似列表里'
    assert 'draft-spot' not in found


def test_similar_ignores_corrupted_model_dimension(client, db_session, seeded, use_embedding):
    """维度混了就不参与排序, 退回结构化 —— 不能让坏数据污染结果。"""
    _store_vectors(db_session, dim=8, only=('west-lake', 'palace-museum', 'terracotta-army'))
    _store_vectors(db_session, dim=16, only=('lingyin-temple', 'ocean-world'))
    use_embedding(FakeEmbeddingClient(dim=8, model=MODEL))
    response = client.get(f'{API}/attractions/west-lake/similar')
    assert response.status_code == 200, response.text
    assert response.json()


def test_ai_status_reports_embedding_coverage(client, db_session, seeded, use_embedding):
    use_embedding(FakeEmbeddingClient(dim=DIM, model=MODEL))
    before = client.get(f'{API}/ai/status').json()
    assert before['embedding_available'] is False
    assert before['embedded'] == 0

    _store_vectors(db_session)
    after = client.get(f'{API}/ai/status').json()
    assert after['embedding_available'] is True
    assert after['embedded'] == after['published']
