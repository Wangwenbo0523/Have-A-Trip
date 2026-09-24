"""LLMClient 的 HTTP 行为测试。

起一个**本机** HTTP 服务: 不打外网、不需要 key, 但请求真的走一遍 httpx ——
URL 拼接、请求体形状、400 重试、缓存、错误映射, 全都是真路径。
"""
from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import Settings
from app.llm import LLMError
from app.llm.client import LLMClient, cache_clear


def reply(content: str) -> dict:
    """OpenAI 兼容的响应外壳。"""
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@contextlib.contextmanager
def running_server(responder):
    """起一个本机模型服务。responder(第几次调用) -> (状态码, 响应体)。"""
    calls: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            calls.append({
                "path": self.path,
                "body": json.loads(self.rfile.read(length).decode("utf-8")),
                "auth": self.headers.get("Authorization"),
            })
            status, payload = responder(len(calls))
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass  # 别把请求日志打到测试输出里

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield "http://%s:%d/v1" % (host, port), calls
    finally:
        server.shutdown()
        server.server_close()


@contextlib.contextmanager
def client_for(base_url, **overrides):
    # 全部显式给值: 本机若真有一份 .env, 也不能影响这里的断言
    config = {
        "llm_provider": "custom",
        "llm_base_url": base_url,
        "llm_model": "test-model",
        "llm_api_key": None,
        "llm_cache_ttl_seconds": 0,
    }
    config.update(overrides)
    settings = Settings(**config)
    cache_clear()
    try:
        yield LLMClient(settings)
    finally:
        cache_clear()


def test_request_shape_is_openai_compatible():
    with running_server(lambda n: (200, reply('{"a": 1}'))) as (base_url, calls):
        with client_for(base_url, llm_api_key="sk-test") as client:
            assert client.chat_json("你是解析器", "找杭州的古迹") == {"a": 1}

    assert len(calls) == 1
    assert calls[0]["path"] == "/v1/chat/completions"
    assert calls[0]["auth"] == "Bearer sk-test"
    body = calls[0]["body"]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0            # 要的是稳定的结构化输出, 不是创作
    assert body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "你是解析器"}
    assert body["messages"][1] == {"role": "user", "content": "找杭州的古迹"}
    assert body["response_format"] == {"type": "json_object"}


def test_ollama_sends_no_authorization_header():
    """本地 Ollama 不校验密钥, 也就没有密钥可发。"""
    with running_server(lambda n: (200, reply('{"a": 1}'))) as (base_url, calls):
        with client_for(base_url, llm_provider="ollama") as client:
            assert client.available is True
            client.chat_json("s", "u")
    assert calls[0]["auth"] is None


def test_retries_without_response_format_on_400():
    """有的网关不认 response_format。只对这一种情况重试一次, 且要去掉该字段。"""
    def responder(n):
        if n == 1:
            return 400, {"error": {"message": "unknown field response_format"}}
        return 200, reply('{"b": 2}')

    with running_server(responder) as (base_url, calls):
        with client_for(base_url) as client:
            assert client.chat_json("s", "u") == {"b": 2}

    assert len(calls) == 2
    assert "response_format" in calls[0]["body"]
    assert "response_format" not in calls[1]["body"]


def test_other_http_errors_do_not_retry():
    """500 不是 400: 立刻降级, 不做无谓重试(模型调用有用户可感知的延迟)。"""
    with running_server(lambda n: (500, {"error": "boom"})) as (base_url, calls):
        with client_for(base_url) as client:
            with pytest.raises(LLMError, match="HTTP 500"):
                client.chat_json("s", "u")
    assert len(calls) == 1


def test_malformed_response_raises_llm_error():
    with running_server(lambda n: (200, {"unexpected": True})) as (base_url, _):
        with client_for(base_url) as client:
            with pytest.raises(LLMError, match="响应结构不对"):
                client.chat_json("s", "u")


def test_unreachable_endpoint_raises_llm_error():
    """连不上是降级信号, 不是崩溃 —— 端口 1 上不会有服务在听。"""
    with client_for("http://127.0.0.1:1/v1") as client:
        with pytest.raises(LLMError, match="连不上模型"):
            client.chat_json("s", "u")


def test_result_is_cached_within_ttl():
    """同一句话不重复打模型。"""
    with running_server(lambda n: (200, reply('{"a": 1}'))) as (base_url, calls):
        with client_for(base_url, llm_cache_ttl_seconds=300) as client:
            assert client.chat_json("s", "u") == {"a": 1}
            assert client.chat_json("s", "u") == {"a": 1}
    assert len(calls) == 1


def test_unconfigured_client_is_not_available_and_never_calls_out():
    client = LLMClient(Settings(llm_provider="none"))
    assert client.available is False
    with pytest.raises(LLMError, match="未配置模型"):
        client.chat_json("s", "u")