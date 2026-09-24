"""向量化客户端: 与 client.py 同构的一层薄封装, 走 OpenAI 兼容的 /embeddings。

为什么不引 sentence-transformers
--------------------------------
torch 的依赖链巨大, 与 docs/BASES.md 里「API 环境不装训练/推理栈」的环境隔离原则直接冲突。
而云端服务与本地 Ollama 都提供 OpenAI 兼容的 /embeddings, 一个 httpx 客户端就够 ——
这也让离线批量向量化可以跑在 backend 同一个 venv 里, 不必再维护第二套环境。

默认 EMBEDDING_PROVIDER=inherit: 跟随 LLM_PROVIDER。两者都没配时 available 为假,
语义检索退回关键词检索, 与 AI 入口的降级口径一致(见 app/llm/interpret.py)。
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from ..config import Settings, get_settings
from .client import PRESETS, PRESETS_REQUIRING_KEY

# 进程内 TTL 缓存: 同一句话在一次请求里可能被向量化多次(检索 + 相似), 不值得重复打网络。
_CACHE: dict[str, tuple[float, list[float]]] = {}

# 单条文本的长度上限。超长的正文对向量没有额外信息量, 只会推高成本。
MAX_INPUT_CHARS = 2000


def cache_clear() -> None:
    """清缓存。测试夹具会调, 避免用例之间互相污染。"""
    _CACHE.clear()


class EmbeddingError(RuntimeError):
    """向量化不可用 / 超时 / 返回结构不对 / 维度与配置不符。

    一律当成可降级错误: 调用方回落到关键词检索, 不往用户面前抛 500。
    """


class EmbeddingClient:
    """OpenAI 兼容的 embedding 客户端。provider 解析为 none 时 available 为假。"""

    def __init__(self, settings: Settings) -> None:
        configured = (settings.embedding_provider or "inherit").strip().lower()
        # inherit 是默认值: 大部分部署只有一家供应商, 不该逼用户把 LLM_* 抄成两份
        self.provider = (settings.llm_provider or "none").strip().lower() if configured == "inherit" else configured
        preset = PRESETS.get(self.provider, {})
        self.base_url = (settings.embedding_base_url or preset.get("base_url", "")).rstrip("/")
        self.model = settings.embedding_model or preset.get("embedding_model", "")
        # 密钥优先用 embedding 自己的; 没给就退回 LLM 的 —— 同一家供应商时只配一个就够
        self.api_key = settings.embedding_api_key or settings.llm_api_key or ""
        self.timeout = settings.embedding_timeout_seconds
        self.configured_dim = settings.embedding_dim
        self.batch_size = max(1, settings.embedding_batch_size)
        self.cache_ttl = settings.embedding_cache_ttl_seconds

    @property
    def available(self) -> bool:
        if self.provider == "none" or not self.base_url or not self.model:
            return False
        # 云端服务没给密钥等于没配。ollama / custom 可能不带鉴权, 不拦。
        if self.provider in PRESETS_REQUIRING_KEY:
            return bool(self.api_key)
        return True

    @property
    def signature(self) -> str:
        """写进 attraction_embedding.model 的标识。

        带上维度: 同一模型换了维度(比如服务商改了默认)必须算两套向量, 不能混在一张表里
        比较 —— 长度不同的向量做余弦是纯粹的垃圾结果, 而且不会报错。
        """
        dim = str(self.configured_dim) if self.configured_dim else "auto"
        return "%s:%s:%s" % (self.provider, self.model, dim)

    def _payload(self, texts: list[str]) -> dict[str, Any]:
        return {"model": self.model, "input": [t[:MAX_INPUT_CHARS] for t in texts]}

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。返回顺序与入参严格一一对应。

        维度与配置不符时抛 EmbeddingError 而不是截断/补齐 —— 静默写进库里的脏向量
        要到检索时才会暴露, 那时已经很难查了。
        """
        if not self.available:
            raise EmbeddingError("未配置向量模型(EMBEDDING_PROVIDER)")
        if not texts:
            return []

        vectors: list[list[float] | None] = [None] * len(texts)
        pending: list[tuple[int, str]] = []
        now = time.time()
        for index, text in enumerate(texts):
            digest = hashlib.sha256(
                ("%s|%s" % (self.model, text)).encode("utf-8")
            ).hexdigest()
            hit = _CACHE.get(digest)
            if hit and (self.cache_ttl <= 0 or now - hit[0] < self.cache_ttl):
                vectors[index] = hit[1]
            else:
                pending.append((index, text))

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key

        for start in range(0, len(pending), self.batch_size):
            chunk = pending[start : start + self.batch_size]
            returned = self._post([text for _, text in chunk], headers)
            for (index, text), vector in zip(chunk, returned):
                vectors[index] = vector
                if self.cache_ttl != 0:
                    digest = hashlib.sha256(
                        ("%s|%s" % (self.model, text)).encode("utf-8")
                    ).hexdigest()
                    _CACHE[digest] = (time.time(), vector)

        return [vector for vector in vectors if vector is not None]

    def _post(self, texts: list[str], headers: dict[str, str]) -> list[list[float]]:
        try:
            with httpx.Client(timeout=self.timeout) as http:
                response = http.post(
                    self.base_url + "/embeddings",
                    json=self._payload(texts),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise EmbeddingError("连不上向量服务: %s" % exc) from exc

        if response.status_code >= 400:
            raise EmbeddingError("向量服务返回 HTTP %s" % response.status_code)

        try:
            body = response.json()
            rows = sorted(body["data"], key=lambda row: row.get("index", 0))
            vectors = [[float(value) for value in row["embedding"]] for row in rows]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise EmbeddingError("向量服务响应结构不对: %s" % exc) from exc

        if len(vectors) != len(texts):
            raise EmbeddingError(
                "向量条数不对: 请求 %d 条, 返回 %d 条" % (len(texts), len(vectors))
            )
        for vector in vectors:
            if not vector:
                raise EmbeddingError("向量服务返回了空向量")
            if self.configured_dim and len(vector) != self.configured_dim:
                raise EmbeddingError(
                    "向量维度不符: 配置 EMBEDDING_DIM=%d, 服务商返回 %d"
                    % (self.configured_dim, len(vector))
                )
        return vectors

    def embed_one(self, text: str) -> list[float]:
        """单条。失败时抛 EmbeddingError, 由调用方决定降级。"""
        vectors = self.embed([text])
        if not vectors:
            raise EmbeddingError("向量服务没有返回结果")
        return vectors[0]


def get_embedding_client() -> EmbeddingClient:
    """FastAPI 依赖。测试里用 app.dependency_overrides 换成打桩客户端。"""
    return EmbeddingClient(get_settings())
