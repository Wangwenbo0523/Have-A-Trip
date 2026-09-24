"""测试用的模型打桩。

刻意**不继承**真的 LLMClient —— 否则打桩会把真实行为(超时、HTTP、缓存)一起继承进来,
测试就不再是在测我们想测的那一层了。
"""
from __future__ import annotations


class FakeClient:
    """按调用返回固定的解析结果; 也可以让它直接报错。"""

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

    def chat_json_usage(self, system: str, user: str, *, max_tokens=None):
        """行程生成走这个 —— 它要 token 用量, 而 chat_json 不返回。"""
        return self.chat_json(system, user), {"prompt_tokens": 100, "completion_tokens": 50}


class ScriptedClient:
    """按调用次序吐不同结果。用来测「第一次不合法 -> 重试 -> 第二次修好了」。

    payloads 里可以混 Exception, 那条会被抛出来(测「重试只针对校验失败, 连不上直接失败」)。
    次数用完就重复最后一个 —— 免得写用例时还要数清模型会被调几次。
    """

    def __init__(self, payloads, usage=None, model="fake-model", available=True):
        self.payloads = list(payloads)
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 50}
        self.model = model
        self._available = available
        self.calls: list[tuple[str, str]] = []

    @property
    def available(self) -> bool:
        return self._available

    def chat_json(self, system: str, user: str) -> dict:
        return self.chat_json_usage(system, user)[0]

    def chat_json_usage(self, system: str, user: str, *, max_tokens=None):
        self.calls.append((system, user))
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        payload = self.payloads[index]
        if isinstance(payload, Exception):
            raise payload
        return dict(payload), dict(self.usage)

class FakeEmbeddingClient:
    """确定性的打桩向量: 同一段文本永远得到同一根向量, 文本越像向量越近。

    用字符袋哈希而不是真模型: 测试要断言的是「排序、阈值、降级」, 不是模型效果,
    而真模型既慢又不可复现。共享字符越多的两段文本余弦越高, 这个性质足够驱动
    相似度排序的用例。
    """

    def __init__(self, dim: int = 8, error=None, available: bool = True, model: str = "fake-embedding"):
        self.dim = dim
        self.error = error
        self._available = available
        self.model = model
        self.calls: list[list[str]] = []

    @property
    def available(self) -> bool:
        return self._available

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        return [self.vector_of(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def vector_of(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for char in text:
            vector[ord(char) % self.dim] += 1.0
        if not any(vector):
            vector[0] = 1.0
        return vector
