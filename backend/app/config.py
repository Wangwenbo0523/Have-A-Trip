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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
