"""FastAPI 应用入口。

本进程绝不 import recbole: RecBole 的依赖把 Python 上限锁在 3.11, 与这里的 3.13
不可能共存(见 docs/BASES.md)。推荐结果由离线任务写进 db/rec_result, API 只读。
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, web
from .api import (
    ai,
    attractions,
    categories,
    events,
    health,
    itineraries,
    posts,
    recommendations,
    search,
    sources,
    stats,
)
from .config import Settings, get_settings

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
    # DELETE 是动态区的作者删除要用的; 少一项浏览器会直接拦掉预检
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ai 放在最前: 新路由统一排在具体资源路由之前, 避免将来前缀交叠时被通配路径抢走
for module in (
    ai,
    itineraries,
    posts,
    search,
    health,
    attractions,
    categories,
    events,
    recommendations,
    sources,
    stats,
):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root(settings: Settings = Depends(get_settings)):
    """整站首页。

    开了静态层(SERVE_FRONTEND=true)且前端 build 过时给应用首页; 否则给 API 自述 ——
    没 build 就返回一个空白 404, 会让人以为应用坏了。
    """
    page = web.index_response(settings)
    if page is not None:
        return page
    return {
        "name": "Have-A-Trip · 景点大全 API",
        "version": __version__,
        "docs": "/docs",
        "api": settings.api_prefix,
    }


# 通配路由必须注册在**最后**, 而且必须在 "/" 之后: Starlette 按注册顺序取第一个匹配,
# /{path:path} 连 "/" 也匹配, 排在前面会把整站首页抢走。放这里之后, /api/** 与 /docs
# 先被接走, "/" 有自己的路由, 静态层只收剩下的。
app.include_router(web.router)
