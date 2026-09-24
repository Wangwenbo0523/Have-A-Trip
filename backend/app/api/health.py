"""健康检查。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__
from ..db import get_db
from ..schemas import HealthOut

router = APIRouter(tags=["meta"])


@router.get("/healthz", response_model=HealthOut, summary="健康检查")
def healthz(db: Session = Depends(get_db)) -> HealthOut:
    """数据库连不上时返回 degraded 而不是 500 —— 探活接口自己不该挂。"""
    try:
        db.execute(text("select 1"))
        database = "ok"
    except Exception:
        database = "error"
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        database=database,
        version=__version__,
    )
