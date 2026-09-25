"""把前端静态产物挂在 API 进程上 —— 单进程跑整站, 给「本机当应用双击打开」用。

默认关闭(`SERVE_FRONTEND=false`)。生产形态是 nginx 托 `dist`、API 单独跑(见
`docs/DEPLOY.md` 第四节), 这里挂一份只是为了本机不用装 nginx —— 一个进程 = 一个应用。

三条规矩:

1. **动态路由优先**。这个通配路由注册在最后, 而且碰到 `/api/` `/docs` `/openapi.json`
   `/redoc` 一律交给原来的处理(不认识的 API 路径照旧返回 404 JSON)。这一条必须显式写:
   真把 HTML 回给一个 fetch, 前端拿到的是「JSON.parse 报错」, 排查方向会被带偏。
2. **不认字面路径以外的东西**。拼出来的路径必须仍落在 dist 里才算数, 否则 404 ——
   `../../backend/app/config.py` 这种不能读到。
3. **缓存分开对待**。`/assets/**` 是 vite 带内容哈希的产物, 可以 immutable 长缓存;
   `index.html` 必须 `no-store`, 否则改了前端、用户还在旧壳里。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from .config import Settings, get_settings

# 这些前缀永远走 API 与文档, 静态层不许碰
RESERVED_PREFIXES = ("api/", "docs", "openapi.json", "redoc")

# vite 产物带内容哈希, 改了文件名就变了, 可以长缓存
IMMUTABLE_PREFIX = "assets/"

router = APIRouter(include_in_schema=False)


def dist_dir(settings: Settings) -> Path | None:
    """产物目录, 没有 index.html 就当作没 build 过。"""
    candidate = settings.frontend_dist_path
    if (candidate / "index.html").is_file():
        return candidate
    return None


def index_response(settings: Settings) -> FileResponse | None:
    """整站首页。开了静态层且 build 过才给, 否则 None(调用方自己决定拿什么顶)。"""
    if not settings.serve_frontend:
        return None
    dist = dist_dir(settings)
    if dist is None:
        return None
    return _file_response(dist / "index.html", immutable=False)


@router.get("/{path:path}")
def static_or_spa(path: str, settings: Settings = Depends(get_settings)):
    """静态文件; 路径不存在就当单页应用的一条路由, 回 index.html。

    前端是 SPA, `/attraction/west-lake` 这种地址在服务端并不存在对应文件, 把未知路径
    回落到 index.html 才不会一刷新就 404(nginx 那边是 `try_files ... /index.html`)。
    """
    if any(path == p.rstrip("/") or path.startswith(p) for p in RESERVED_PREFIXES):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not settings.serve_frontend:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    dist = dist_dir(settings)
    if dist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="前端产物不存在, 先 npm run build")

    candidate = (dist / path).resolve()
    if path and _inside(candidate, dist) and candidate.is_file():
        return _file_response(candidate, immutable=path.startswith(IMMUTABLE_PREFIX))
    return _file_response(dist / "index.html", immutable=False)


def _inside(candidate: Path, dist: Path) -> bool:
    """候选路径必须真的在 dist 里(挡 ../ 与符号链接指出去)。"""
    try:
        return candidate.is_relative_to(dist.resolve())
    except OSError:
        return False


def _file_response(target: Path, *, immutable: bool) -> FileResponse:
    headers = {
        "Cache-Control": (
            "public, max-age=31536000, immutable" if immutable else "no-store"
        )
    }
    return FileResponse(target, headers=headers)

