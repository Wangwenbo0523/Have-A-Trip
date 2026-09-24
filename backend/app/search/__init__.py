"""向量检索层。对外只暴露规范化文本、向量工具与语义检索。"""
from .canonical import PIPELINE_VERSION, canonical_text, content_hash
from .semantic import (
    active_model,
    coverage,
    load_vectors,
    semantic_search,
    similar_attractions,
)
from .vectors import cosine, decode, encode

__all__ = [
    "PIPELINE_VERSION",
    "active_model",
    "canonical_text",
    "content_hash",
    "coverage",
    "cosine",
    "decode",
    "encode",
    "load_vectors",
    "semantic_search",
    "similar_attractions",
]
