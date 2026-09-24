"""向量编解码与余弦相似度。

为什么不用 pgvector
-------------------
两条硬理由, 都不是"嫌麻烦":

1. 本仓库的 ORM 刻意只用可移植类型(见 models.py 开头), 测试跑 SQLite 内存库、
   本地不装 PostgreSQL。引 pgvector 就同时引入「建表要超级用户装扩展」「CI 要换镜像」
   「SQLite 与 PG 两套代码路径」三份复杂度, 而收益要目录上万条才体现。
2. 全库 90 个已发布景点, 768 维。一次全量余弦是 7 万次乘加, 纯 Python 几毫秒,
   与 ANN 索引的差距在这个量级上测不出来。

所以向量以 JSON 文本存进 TEXT 列, 在应用层算余弦 —— **SQLite 与 PostgreSQL 走
完全同一条代码路径**, 没有"只在生产才跑得到"的分支。

规模化的升级路径写在 docs/DEPLOY.md: 目录过万条时, 换 pgvector + HNSW,
本模块的接口(canonical_text / content_hash / cosine)不用改, 只换检索实现。
"""
from __future__ import annotations

import json
import math


def encode(vector: list[float]) -> str:
    """存进 TEXT 列。float() 兜一遍: 有的服务商返回的是 int 或字符串。"""
    return json.dumps([float(value) for value in vector], separators=(",", ":"))


def decode(raw: str) -> list[float]:
    """从 TEXT 列读回。数据损坏时抛 ValueError, 由调用方决定是跳过还是报错。"""
    values = json.loads(raw)
    if not isinstance(values, list):
        raise ValueError("向量不是数组")
    return [float(value) for value in values]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度, 取值 -1..1。长度不等返回 0 —— 不做截断, 不抛异常。

    长度不等的两根向量做余弦是纯粹的垃圾结果, 而且不会报错。这里返回 0 让它必然
    排到最后, 同时由 coverage/active_model 把那批数据标成不可用, 不去污染结果。
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for left, right in zip(a, b):
        dot += left * right
        norm_a += left * left
        norm_b += right * right
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
