"""一句话检索: 自然语言 -> 查询条件 -> 库里查景点。

护栏的完整说明在 app/llm/interpret.py 开头, 这里只说这个模块的职责:
1. 解析出来的条件交给 attractions.build_query —— 与用户手点筛选共用同一条查询路径,
   不存在「AI 专用」的另一套宽松查询;
2. 景点条目只从库里取, 模型拿不到结果集, 所以它没有编造景点的机会;
3. 模型不可用 / 超时 / 返回不是 JSON, 一律降级成关键词检索, 不往用户面前抛 500。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..llm import LLMClient, get_llm_client
from ..llm.ask import DISCLAIMER as ASK_DISCLAIMER
from ..llm.ask import ask
from ..llm.interpret import interpret
from ..llm.polish import DISCLAIMER as POLISH_DISCLAIMER
from ..llm.polish import polish
from ..models import AppUser
from ..recommend import service as recommend_service
from ..schemas import (
    AIAskIn,
    AIAskOut,
    AIFilters,
    AIRecommendNotesIn,
    AIRecommendNotesOut,
    AIRefinedReason,
    AISearchIn,
    AISearchOut,
    AIStatusOut,
)
from . import attractions as attractions_api

router = APIRouter(prefix="/ai", tags=["ai"])

# 这句话必须显示在结果上方。口径与 docs/LICENSE-AUDIT.md「AI 与模型条款」一致:
# 模型只做需求理解, 结果集与排序都由本站在库数据决定。
DISCLAIMER = "结果全部来自本站景点档案, AI 只参与理解你这句需求。"

@router.get("/status", response_model=AIStatusOut, summary="AI 入口是否可用")
def ai_status(client: LLMClient = Depends(get_llm_client)) -> AIStatusOut:
    """前端据此决定要不要显示「用一句话找景点」。未配置模型时 available=false。"""
    return AIStatusOut(
        available=client.available,
        provider=client.provider,
        model=client.model or None,
        disclaimer=DISCLAIMER,
    )


@router.post("/search", response_model=AISearchOut, summary="用一句话找景点")
def ai_search(
    payload: AISearchIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: LLMClient = Depends(get_llm_client),
) -> AISearchOut:
    """降级不是错误: 模型不可用时 filters 里只有 q=用户原话, 照常返回 200。

    前端据 degraded 决定要不要提示「已退回关键词检索」。
    """
    outcome = interpret(db, client, payload.query)
    filters = outcome.filters

    statement = attractions_api.build_query(
        category=filters.get("category"),
        city=filters.get("city"),
        tag=filters.get("tag"),
        grade=filters.get("grade"),
        q=filters.get("q"),
    )
    limit = min(payload.size or settings.default_page_size, settings.max_page_size)
    total = attractions_api.count_of(db, statement)
    items = attractions_api.page_of(
        db,
        statement,
        page=payload.page,
        limit=limit,
        sort=filters.get("sort") or "rating",
    )

    return AISearchOut(
        query=payload.query,
        interpreted=outcome.interpreted,
        degraded=outcome.degraded,
        model=outcome.model,
        note=outcome.note,
        filters=AIFilters(
            category=filters.get("category"),
            tag=filters.get("tag"),
            grade=filters.get("grade"),
            city=filters.get("city"),
            q=filters.get("q"),
            sort=filters.get("sort") or "rating",
        ),
        items=items,
        page=payload.page,
        size=limit,
        total=total,
        disclaimer=DISCLAIMER,
    )

@router.post("/ask", response_model=AIAskOut, summary="就某个景点问一句")
def ai_ask(
    payload: AIAskIn,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
) -> AIAskOut:
    """答案只依据这个景点的档案字段, 档案里没有的一律不作答。

    模型不可用 / 说法查不到依据时降级成档案摘录, 仍然是 200 —— 追问失败不该表现为报错页。
    """
    attraction = attractions_api.find_attraction(db, payload.slug)
    if attraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")

    outcome = ask(client, attraction, payload.question)
    return AIAskOut(
        slug=attraction.slug,
        question=payload.question,
        grounded=outcome.grounded,
        degraded=outcome.degraded,
        model=outcome.model,
        answer=outcome.answer,
        note=outcome.note,
        cited=outcome.cited,
        dropped=outcome.dropped,
        disclaimer=ASK_DISCLAIMER,
    )


@router.post("/recommend-notes", response_model=AIRecommendNotesOut, summary="润色推荐理由")
def ai_recommend_notes(
    payload: AIRecommendNotesIn,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
) -> AIRecommendNotesOut:
    """只改写「为什么推荐它」这句话的措辞。

    **推荐结果本身不交给模型**: 条目、顺序、分数都由 /recommendations 决定,
    这里拿到的只是已定好的那几条, 模型碰不到挑选与排序。模型不可用时沿用原来的理由。
    """
    if payload.user_id is not None and payload.device_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user_id 与 device_id 只能传一个")

    user_id = payload.user_id
    if user_id is None and payload.device_id is not None:
        # 没见过的设备不是错误, 与 /recommendations 同口径: 按新用户处理
        user = db.scalar(select(AppUser).where(AppUser.device_id == payload.device_id))
        user_id = user.id if user else None
    if user_id is not None and db.get(AppUser, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")

    items = recommend_service.get_recommendations(db, user_id, payload.limit)
    entries = [(item.attraction.slug, item.attraction.name, item.reason) for item in items]
    outcome = polish(client, entries)

    return AIRecommendNotesOut(
        polished=outcome.polished,
        degraded=outcome.degraded,
        model=outcome.model,
        note=outcome.note,
        reasons=[AIRefinedReason(slug=slug, note=text) for slug, text in outcome.notes.items()],
        dropped=outcome.dropped,
        disclaimer=POLISH_DISCLAIMER,
    )