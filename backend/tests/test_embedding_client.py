"""EmbeddingClient 的 HTTP 行为测试。

与 test_llm_client.py 同一套思路: 起一个**本机** HTTP 服务, 不打外网、不需要 key,
但请求真的走一遍 httpx —— URL 拼接、请求体形状、批次切分、维度校验、缓存、错误映射
全都是真路径。
"""
from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import Settings
from app.llm.embedding import EmbeddingClient, EmbeddingError, cache_clear


@contextlib.contextmanager
def running_server(responder):
    """起一个本机向量服务。responder(请求体) -> (状态码, 响应体)。"""
    calls: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            request = json.loads(self.rfile.read(length).decode('utf-8'))
            calls.append(
                {
                    'path': self.path,
                    'body': request,
                    'auth': self.headers.get('Authorization'),
                }
            )
            status, payload = responder(request)
            raw = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass  # 别把请求日志打到测试输出里

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        host, port = server.server_address
        yield 'http://%s:%d/v1' % (host, port), calls
    finally:
        server.shutdown()
        server.server_close()


def vectors(count: int, dim: int = 3, *, reverse: bool = False) -> dict:
    """OpenAI 兼容的 /embeddings 响应。reverse 用来验「按 index 还原顺序」。"""
    data = [
        {'index': index, 'embedding': [float(index + 1)] * dim}
        for index in range(count)
    ]
    if reverse:
        data.reverse()
    return {'data': data, 'model': 'test-embedding'}


@contextlib.contextmanager
def client_for(base_url, **overrides):
    # 全部显式给值: 本机若真有一份 .env, 也不能影响这里的断言
    config = {
        'embedding_provider': 'custom',
        'embedding_base_url': base_url,
        'embedding_model': 'test-embedding',
        'embedding_api_key': None,
        'embedding_dim': 0,
        'embedding_cache_ttl_seconds': 0,
        'llm_provider': 'none',
        'llm_api_key': None,
    }
    config.update(overrides)
    cache_clear()
    try:
        yield EmbeddingClient(Settings(**config))
    finally:
        cache_clear()


def text_of(request) -> list[str]:
    return request['input']


# ------------------------------------------------------------------ 请求形状

def test_embed_posts_to_the_embeddings_endpoint():
    def responder(request):
        return 200, vectors(len(text_of(request)))

    with running_server(responder) as (base_url, calls), client_for(base_url) as client:
        client.embed(['西湖', '故宫'])

    assert calls[0]['path'] == '/v1/embeddings'
    assert calls[0]['body']['model'] == 'test-embedding'
    assert calls[0]['body']['input'] == ['西湖', '故宫']
    assert calls[0]['auth'] is None


def test_api_key_is_sent_as_bearer():
    def responder(request):
        return 200, vectors(len(text_of(request)))

    with running_server(responder) as (base_url, calls), client_for(
        base_url, embedding_api_key='sk-secret'
    ) as client:
        client.embed(['西湖'])

    assert calls[0]['auth'] == 'Bearer sk-secret'


def test_embed_restores_input_order_from_index():
    """服务商可以不按顺序回, 但返回给调用方必须与入参一一对应。"""

    def responder(request):
        return 200, vectors(len(text_of(request)), reverse=True)

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        got = client.embed(['a', 'b', 'c'])

    assert got == [[1.0] * 3, [2.0] * 3, [3.0] * 3]


def test_batching_splits_into_several_requests():
    def responder(request):
        return 200, vectors(len(text_of(request)))

    with running_server(responder) as (base_url, calls), client_for(
        base_url, embedding_batch_size=2
    ) as client:
        got = client.embed(['a', 'b', 'c', 'd', 'e'])

    assert len(calls) == 3, '批次大小 2 时 5 条文本要拆成 3 次'
    assert [len(call['body']['input']) for call in calls] == [2, 2, 1]
    assert len(got) == 5


def test_embed_of_empty_input_makes_no_request():
    def responder(request):
        raise AssertionError('不该发请求')

    with running_server(responder) as (base_url, calls), client_for(base_url) as client:
        assert client.embed([]) == []
    assert calls == []


# ------------------------------------------------------------------ 维度

def test_dim_mismatch_is_refused():
    """配置锁了维度就不能容忍别的维度 —— 静默写进库要到检索时才会暴露。"""

    def responder(request):
        return 200, vectors(len(text_of(request)), dim=5)

    with running_server(responder) as (base_url, _), client_for(
        base_url, embedding_dim=8
    ) as client:
        with pytest.raises(EmbeddingError, match='维度不符'):
            client.embed(['西湖'])


def test_auto_dim_accepts_whatever_the_provider_returns():
    """embedding_dim=0 是自动: 以服务商为准, 维度由写入方记进 attraction_embedding.dim。"""

    def responder(request):
        return 200, vectors(len(text_of(request)), dim=5)

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        assert len(client.embed(['西湖'])[0]) == 5


def test_configured_dim_matching_passes():
    def responder(request):
        return 200, vectors(len(text_of(request)), dim=5)

    with running_server(responder) as (base_url, _), client_for(
        base_url, embedding_dim=5
    ) as client:
        assert len(client.embed(['西湖'])[0]) == 5


def test_empty_vector_is_refused():
    def responder(request):
        return 200, {'data': [{'index': 0, 'embedding': []}]}

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        with pytest.raises(EmbeddingError, match='空向量'):
            client.embed(['西湖'])


# ------------------------------------------------------------------ 失败与降级

def test_http_error_becomes_embedding_error():
    def responder(request):
        return 500, {'error': 'boom'}

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        with pytest.raises(EmbeddingError, match='HTTP 500'):
            client.embed(['西湖'])


def test_bad_structure_becomes_embedding_error():
    def responder(request):
        return 200, {'unexpected': True}

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        with pytest.raises(EmbeddingError, match='结构不对'):
            client.embed(['西湖'])


def test_count_mismatch_is_refused():
    def responder(request):
        return 200, vectors(1)

    with running_server(responder) as (base_url, _), client_for(base_url) as client:
        with pytest.raises(EmbeddingError, match='条数不对'):
            client.embed(['西湖', '故宫'])


def test_connection_failure_becomes_embedding_error():
    # 指向一个关掉的端口
    with client_for('http://127.0.0.1:9/v1') as client:
        with pytest.raises(EmbeddingError, match='连不上'):
            client.embed(['西湖'])


def test_unavailable_client_refuses_to_call():
    """两个 provider 都没配: 直接报错, 不要发出一个必然失败的请求。"""
    client = EmbeddingClient(Settings(llm_provider='none', embedding_provider='inherit'))
    assert client.available is False
    with pytest.raises(EmbeddingError, match='未配置'):
        client.embed(['西湖'])


# ------------------------------------------------------------------ 缓存

def test_cache_avoids_the_second_network_call():
    def responder(request):
        return 200, vectors(len(text_of(request)))

    with running_server(responder) as (base_url, calls), client_for(
        base_url, embedding_cache_ttl_seconds=300
    ) as client:
        first = client.embed(['西湖'])
        second = client.embed(['西湖'])

    assert first == second
    assert len(calls) == 1, '同一段文本在 TTL 内不该重复打网络'


def test_cache_can_be_switched_off():
    def responder(request):
        return 200, vectors(len(text_of(request)))

    with running_server(responder) as (base_url, calls), client_for(
        base_url, embedding_cache_ttl_seconds=0
    ) as client:
        client.embed(['西湖'])
        client.embed(['西湖'])

    assert len(calls) == 2


# ------------------------------------------------------------------ 配置解析

def test_signature_pins_the_dimension():
    """签名带维度: 同一模型换了维度必须算两套向量, 不能混在一张表里比。"""
    auto = EmbeddingClient(Settings(embedding_provider='ollama', embedding_dim=0))
    pinned = EmbeddingClient(Settings(embedding_provider='ollama', embedding_dim=768))
    assert auto.signature == 'ollama:nomic-embed-text:auto'
    assert pinned.signature == 'ollama:nomic-embed-text:768'
    assert auto.signature != pinned.signature


def test_embedding_key_falls_back_to_the_llm_key():
    """同一家供应商时只配一个 key 就够。"""
    client = EmbeddingClient(
        Settings(embedding_provider='openai', llm_api_key='sk-shared', embedding_api_key=None)
    )
    assert client.api_key == 'sk-shared'


def test_embedding_key_can_be_its_own():
    """向量模型换到另一家时, 两个 key 必须能分开配。"""
    client = EmbeddingClient(
        Settings(
            embedding_provider='custom',
            embedding_base_url='https://embed.example.com/v1',
            embedding_model='embed-x',
            embedding_api_key='sk-embed',
            llm_api_key='sk-chat',
        )
    )
    assert client.api_key == 'sk-embed'
    assert client.base_url == 'https://embed.example.com/v1'
    assert client.available is True
