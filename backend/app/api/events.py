"""行为埋点。

只记录 view / favorite / rate / share 四类行为, 用于推荐。
不接收、也不存储任何定位或轨迹信息 —— 这是本项目的硬约束。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..aggregates import recount_attraction_rating
from ..db import get_db
from ..models import AppUser, Attraction, BehaviorLog
from ..schemas import EventIn, EventOut

router = APIRouter(tags=["events"])


@router.post(
    "/events",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="上报一条行为",
)
def create_event(payload: EventIn, db: Session = Depends(get_db)) -> EventOut:
    attraction = db.get(Attraction, payload.attraction_id)
    if attraction is None or attraction.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")

    user = db.scalar(select(AppUser).where(AppUser.device_id == payload.device_id))
    if user is None:
        user = AppUser(device_id=payload.device_id)
        db.add(user)
        db.flush()
    user.last_seen_at = datetime.now(timezone.utc)

    log = BehaviorLog(
        user_id=user.id,
        attraction_id=attraction.id,
        event_type=payload.event_type,
        rating=payload.rating,
        dwell_ms=payload.dwell_ms,
    )
    db.add(log)
    db.flush()

    if payload.event_type == "rate":
        recount_attraction_rating(db, attraction.id)

    db.commit()
    db.refresh(log)
    return EventOut.model_validate(log)
