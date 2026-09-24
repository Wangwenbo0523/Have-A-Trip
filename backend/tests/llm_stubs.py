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