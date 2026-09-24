"""配置。全部可用环境变量覆盖, 见 .env.example。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生产目标是 PostgreSQL; 测试会把它换成 SQLite 内存库
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas"
    )
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    default_page_size: int = 20
    max_page_size: int = 100

    # 推荐结果的短 TTL 内存缓存(S2 用)。先不引 Redis。
    rec_cache_ttl_seconds: int = 60
    rec_default_limit: int = 10
    rec_max_limit: int = 50

    # ---------------------------------------------------------------- AI / 大模型
    #
    # 默认 none: 什么都不配时应用照常跑, AI 入口显示为不可用(见 app/llm/client.py)。
    # provider 取值: none | ollama | deepseek | openai | custom
    #   ollama              本地, 数据不出本机, 不需要 key
    #   deepseek / openai   云端, 需要 llm_api_key
    #   custom              任何 OpenAI 兼容网关, base_url 与 model 自己给
    # base_url 与 model 留空时用 provider 预设值。密钥只从环境变量来, 绝不写进仓库。
    llm_provider: str = "none"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    # 模型调用超时: 宁可降级成关键词检索, 也不让用户在页面上干等
    llm_timeout_seconds: float = 20.0
    # 每次请求的输出上限 —— 我们要的是几个查询条件, 不是文章
    llm_max_tokens: int = 400
    # 同一句话的解析结果缓存(秒), 0 表示不缓存
    llm_cache_ttl_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
