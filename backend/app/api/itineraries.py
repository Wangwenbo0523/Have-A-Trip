"""LLM 行程生成接口: 提交 -> 轮询 -> 取结果。

为什么是异步三接口而不是一个同步 POST
-------------------------------------
生成要 10~30 秒。同步等着会把连接占满, 而且用户中途刷新页面就丢了任务。
所以提交只落一行 pending 并立刻返回 token, 生成在后台跑, 前端拿 token 轮询。

为什么对外只用 token 不用 id
-----------------------------
主键是自增 BIGINT。用 id 取行程的话, 从 1 开始递增就能遍历**所有人**的需求原文
—— 这类越权不需要任何技巧。token 是 24 字节随机串, 猜不出来。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from .. import quota
from ..db import get_db, get_session_factory
from ..models import AppUser, Itinerary
from ..schemas import (
    ItineraryAccepted,
    ItineraryIn,
    ItineraryItemOut,
    ItineraryOut,
    ItineraryUsageOut,
)
from ..trip import service as trip_service

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

DISCLAIMER = "行程由 AI 按本站景点档案编排, 出行前请核实开放时间与票价。"

# 拒绝原因用固定取值而不是自由文本: 前端要按它决定提示语与是否给"明天再来"的入口
REASON_DAILY_LIMIT = "daily_limit_exceeded"
REASON_BUDGET = "global_budget_exhausted"


def _rejected(reason: str, *, limit: int | None = None) -> HTTPException:
    detail: dict = {"status": "rejected", "reason": reason, "retry_after": quota.retry_after()}
    if limit is not None:
        detail["limit"] = limit
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def _to_out(row: Itinerary, settings: Settings) -> ItineraryOut:
    usage = None
    if row.status == "succeeded":
        usage = ItineraryUsageOut(
            prompt_tokens=row.prompt_tokens or 0,
            completion_tokens=row.completion_tokens or 0,
        )
    return ItineraryOut(
        token=row.public_token,
        status=row.status,
        days=row.days,
        items=[
            ItineraryItemOut(
                day_index=item.day_index,
                seq=item.seq,
                attraction_id=item.attraction_id,
                name=item.attraction_name,
                note=item.note,
                reason=item.reason,
            )
            for item in row.items
        ],
        error=row.error,
        note=row.note,
        model=row.model,
        usage=usage,
        generated_at=row.generated_at,
        created_at=row.created_at,
        max_poll_seconds=settings.trip_poll_max_seconds,
        disclaimer=DISCLAIMER,
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ItineraryAccepted,
    responses={200: {"description": "命中已有行程(同一 owner 的同一份需求)"}},
    summary="提交一次行程生成",
)
def create_itinerary(
    payload: ItineraryIn,
    response: Response,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
) -> ItineraryAccepted:
    """202 = 已受理, 拿 token 去轮询; 200 = 直接复用了已有行程, 不用再等。

    命中缓存**不占用当日名额**, 也不重复计费: 用户刷新页面重发一次不该扣一次配额。
    """
    if payload.user_id is not None and db.get(AppUser, payload.user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    try:
        row, outcome = trip_service.create(
            db,
            user_id=payload.user_id,
            device_id=payload.device_id,
            request_text=payload.request_text,
            days=payload.days,
            settings=settings,
        )
    except trip_service.BudgetExhausted as exc:
        raise _rejected(REASON_BUDGET) from exc
    except trip_service.DailyLimitExceeded as exc:
        raise _rejected(REASON_DAILY_LIMIT, limit=settings.trip_daily_limit) from exc

    if outcome == "created":
        background.add_task(
            trip_service.run_generation,
            session_factory,
            itinerary_id=row.id,
            settings=settings,
            request_text=payload.request_text,
        )
    else:
        # 复用已有行程: 不再生成, 状态就是它当前的状态
        response.status_code = status.HTTP_200_OK
    return ItineraryAccepted(token=row.public_token, status=row.status)


@router.get("/{token}", response_model=ItineraryOut, summary="按 token 取行程")
def get_itinerary(
    token: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ItineraryOut:
    """token 不匹配一律 404 —— 不区分"不存在"与"不是你的", 免得泄漏存在性。"""
    row = db.scalar(select(Itinerary).where(Itinerary.public_token == token))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="行程不存在")
    # 轮到一个已经死掉的 generating 就地置失败, 免得前端一直转圈
    row = trip_service.reclaim_one(db, row, settings=settings)
    return _to_out(row, settings)
