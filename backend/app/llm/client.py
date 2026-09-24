"""模型客户端: 一层薄封装, provider 可换。

为什么不用官方 SDK
------------------
1. scripts/license_gate.py 扫的是已安装的包 —— 少一个依赖少一份许可面;
2. 云端服务与本地 Ollama 都提供 OpenAI 兼容的 /chat/completions, 一个 HTTP 客户端就够;
3. 直接用 httpx(BSD-3)打 HTTP, 超时 / JSON 解析 / 降级都握在自己手里。

默认 LLM_PROVIDER=none: 什么都不配时应用照常跑, AI 入口显示为不可用。
详见 docs/LICENSE-AUDIT.md 的「AI 与模型条款」一节。
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from ..config import Settings, get_settings
# provider 预设。base_url 与 model 的默认值, 都可以用环境变量覆盖。
PRESETS: dict[str, dict[str, str]] = {
    # 本地: 数据不出本机, 零成本, 无需 key
    "ollama": {"base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b-instruct"},
    # 云端: 需要 LLM_API_KEY
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    # 任何 OpenAI 兼容网关(自建 / 其他厂商), 全部靠环境变量给
    "custom": {},
}

# 必须给密钥的预设。ollama 跑在本机、custom 是自建网关, 两者都可能不带鉴权,
# 没配 api_key 也算配好了 —— 否则自建网关会被误判成「不可用」。
PRESETS_REQUIRING_KEY = ("deepseek", "openai")

# 进程内 TTL 缓存。与推荐接口的 rec_cache 同一思路: 先不引 Redis。
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def cache_clear() -> None:
    """清缓存。测试夹具会调, 避免用例之间互相污染。"""
    _CACHE.clear()


class LLMError(RuntimeError):
    """模型不可用 / 超时 / 返回不是 JSON。

    一律当成可降级错误: 调用方负责回落到关键词检索, 不往用户面前抛 500。
    """


def extract_json(text: str) -> dict[str, Any]:
    """从模型输出里抠出 JSON 对象。

    本地小模型经常把 JSON 裹在代码块里, 或者在前后加一句解释 —— 所以不能直接
    json.loads。先整体试一次, 失败再取第一个左花括号到最后一个右花括号之间的内容。
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    raise LLMError("模型返回的不是 JSON 对象")


class LLMClient:
    """OpenAI 兼容的 chat 客户端。provider=none 时 available 为假, 调用直接报错。"""

    def __init__(self, settings: Settings) -> None:
        self.provider = (settings.llm_provider or "none").strip().lower()
        preset = PRESETS.get(self.provider, {})
        self.base_url = (settings.llm_base_url or preset.get("base_url", "")).rstrip("/")
        self.model = settings.llm_model or preset.get("model", "")
        self.api_key = settings.llm_api_key or ""
        self.timeout = settings.llm_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        self.cache_ttl = settings.llm_cache_ttl_seconds

    @property
    def available(self) -> bool:
        if self.provider == "none" or not self.base_url or not self.model:
            return False
        # 预设里明确是云端服务的, 没给密钥就等于没配(在 /ai/status 上就能看出来)
        if self.provider in PRESETS_REQUIRING_KEY:
            return bool(self.api_key)
        return True

    def _payload(self, system: str, user: str, json_mode: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # 要的是稳定的结构化输出, 不是创作
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload
    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        """要一段 JSON。任何失败都抛 LLMError, 由调用方决定怎么降级。"""
        if not self.available:
            raise LLMError("未配置模型(LLM_PROVIDER)")

        digest = hashlib.sha256(
            ("%s|%s|%s" % (self.model, system, user)).encode("utf-8")
        ).hexdigest()
        hit = _CACHE.get(digest)
        if hit and (self.cache_ttl <= 0 or time.time() - hit[0] < self.cache_ttl):
            return hit[1]

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        last_error = "未知错误"
        # 先带 response_format 试(JSON 更稳); 有的网关不认这个字段会回 400, 那就去掉再试一次。
        # 只重试这一种情况 —— 模型调用有用户可感知的延迟, 不能无脑重试。
        for json_mode in (True, False):
            try:
                with httpx.Client(timeout=self.timeout) as http:
                    response = http.post(
                        self.base_url + "/chat/completions",
                        json=self._payload(system, user, json_mode),
                        headers=headers,
                    )
            except httpx.HTTPError as exc:
                raise LLMError("连不上模型: %s" % exc) from exc

            if response.status_code == 400 and json_mode:
                last_error = "HTTP 400(可能不支持 response_format)"
                continue
            if response.status_code >= 400:
                raise LLMError("模型返回 HTTP %s" % response.status_code)

            try:
                body = response.json()
                content = body["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise LLMError("模型响应结构不对: %s" % exc) from exc

            parsed = extract_json(content)
            if self.cache_ttl != 0:
                _CACHE[digest] = (time.time(), parsed)
            return parsed

        raise LLMError(last_error)


def get_llm_client() -> LLMClient:
    """FastAPI 依赖。测试里用 app.dependency_overrides 换成打桩客户端。"""
    return LLMClient(get_settings())