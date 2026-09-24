"""FastAPI 应用入口。

本进程绝不 import recbole: RecBole 的依赖把 Python 上限锁在 3.11, 与这里的 3.13
不可能共存(见 docs/BASES.md)。推荐结果由离线任务写进 db/rec_result, API 只读。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import attractions, categories, events, health, recommendations, sources
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="Have-A-Trip · 景点大全 API",
    description="景点档案的浏览、搜索与推荐。不做地图与定位。",
    version=__version__,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

for module in (health, attractions, categories, events, recommendations, sources):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": "Have-A-Trip · 景点大全 API",
        "version": __version__,
        "docs": "/docs",
        "api": settings.api_prefix,
    }
