"""AI 接入层。对外只暴露客户端、向量客户端、解析器、追问、润色与离线草稿。"""
from .ask import Answer, ask
from .client import LLMClient, LLMError, cache_clear, get_llm_client
from .draft import Draft, draft_one, drafts
from .embedding import (
    EmbeddingClient,
    EmbeddingError,
    get_embedding_client,
)
from .embedding import cache_clear as embedding_cache_clear
from .interpret import Interpretation, interpret
from .polish import Polished, polish

__all__ = [
    "Answer",
    "Draft",
    "EmbeddingClient",
    "EmbeddingError",
    "Interpretation",
    "LLMClient",
    "LLMError",
    "Polished",
    "ask",
    "cache_clear",
    "draft_one",
    "drafts",
    "embedding_cache_clear",
    "get_embedding_client",
    "get_llm_client",
    "interpret",
    "polish",
]
