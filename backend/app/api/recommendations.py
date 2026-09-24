"""推荐接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import AppUser
from ..recommend import service
from ..schemas import AttractionListItem, RecommendationItem

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationItem], summary="为你推荐")
def list_recommendations(
    user_id: int | None = Query(None, description="用户 id。与 device_id 二选一"),
    device_id: str | None = Query(
        None, description="设备号。前端只有设备号时用它, 未注册的设备按新用户处理"
    ),
    limit: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[RecommendationItem]:
    size = min(limit or settings.rec_default_limit, settings.rec_max_limit)

    if user_id is not None and device_id is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="user_id 与 device_id 只能传一个"
        )

    if user_id is None and device_id is not None:
        # 没见过的设备不是错误: 直接按新用户走冷启动, 返回一份可用的推荐
        user = db.scalar(select(AppUser).where(AppUser.device_id == device_id))
        user_id = user.id if user else None

    if user_id is not None and db.get(AppUser, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    cache = service.get_cache(settings)
    key = (user_id, size)
    cached = cache.get(key)
    if cached is not None:
        return cached

    items = [
        RecommendationItem(
            attraction=AttractionListItem.model_validate(item.attraction),
            rank=item.rank,
            score=item.score,
            algo=item.algo,
            reason=item.reason,
        )
        for item in service.get_recommendations(db, user_id, size)
    ]
    if user_id is not None:
        cache.set(key, items)
    return items
