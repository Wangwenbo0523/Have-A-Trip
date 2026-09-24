"""行程生成的服务层: 去重、限额、候选召回、调模型、落库、失败处理。

一次生成的完整路径:

    提交 -> 预算检查 -> 去重(命中则直接复用) -> 抢当日名额 -> 落 pending 行
         -> 后台: 认领(条件更新 pending->generating)
                  -> 候选召回(向量优先, 热度兜底)
                  -> 调模型 -> validator 校验
                  -> 一个事务里写条目 + 推到 succeeded
         -> 失败: 回滚后另起一个事务写 failed(绝不能把 failed 一起回滚掉)

认领用了条件更新 `WHERE status='pending'`, 所以同一个行程不会被生成两次 ——
这不只是防重复扣费, 也是防止两份条目撞 uq_itinerary_item_order 唯一键。
"""
from __future__ import annotations

import hashlib
import os
import secrets
import socket
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..llm.client import LLMClient, LLMError
from ..llm.embedding import EmbeddingClient, EmbeddingError
from ..models import Attraction, Itinerary, ItineraryItem
from ..recommend import content_based
from ..search import semantic
from . import quota
from .prompt import build_prompt
from .validator import ValidationError, validate

# 提示词口径。改了 system prompt 或输出格式就必须 +1 —— 它进缓存键,
# 否则新旧两种格式的行程会被当成同一份复用。
PROMPT_VERSION = "1"

# error 字段的落库长度。异常信息可能很长, 而这一列是给人看的。
ERROR_MAX = 500


class DailyLimitExceeded(RuntimeError):
    """该 owner 当天的名额用完了。API 层转成 429 + status=rejected。"""


class BudgetExhausted(RuntimeError):
    """全站当日 token 预算用尽。API 层转成 429 + status=rejected。"""


def new_token() -> str:
    """对外标识。用随机串而不是自增 id: 自增 id 递增就能读到别人的需求原文。"""
    return "itn_" + secrets.token_urlsafe(18)


def build_llm(settings: Settings) -> LLMClient:
    """行程生成用的对话客户端。

    单独一个函数是为了**测试能替换它**: 生成跑在后台任务里, 不走 FastAPI 的依赖注入,
    不这样留一个口子就只能靠打真接口来测。
    超时放宽到 trip_timeout_seconds —— 输出是一整份结构化长文本, 比解析意图慢。
    """
    return LLMClient(
        settings.model_copy(update={"llm_timeout_seconds": settings.trip_timeout_seconds})
    )


def build_embedding(settings: Settings) -> EmbeddingClient:
    """候选召回用的向量客户端。同样是为了测试可替换。"""
    return EmbeddingClient(settings)


def owner_key_for(user_id: int | None, device_id: str | None) -> str:
    """缓存与限额的作用域。登录用户按用户, 匿名按设备。

    两种作用域必须能区分开: 否则 id=7 的用户与 device_id="7" 的设备会共享一份缓存,
    互相读到对方的行程。
    """
    if user_id is not None:
        return "u:%d" % user_id
    return "d:%s" % (device_id or "anonymous")


def request_hash_of(request_text: str) -> str:
    """规范化后取 hash。压空白: 「杭州 三天」与「杭州  三天」是同一个需求。"""
    return hashlib.sha256(" ".join(request_text.split()).encode("utf-8")).hexdigest()


def _candidate_version(db: Session, model: str | None) -> str:
    """候选集版本: 向量模型 + 已发布景点数。

    候选集变了, 同一份需求应该能重新生成 —— 比如新上了几个景点。把它放进缓存键,
    新的一天/新的目录自然就是一次新的生成, 而不是永远复用第一天的结果。
    """
    total = db.scalar(
        select(func.count()).select_from(Attraction).where(Attraction.status == "published")
    ) or 0
    return "%s|%d" % (model or "-", int(total))


def cache_key_for(
    *, request_hash: str, days: int, constraints: str | None, candidate_version: str
) -> str:
    parts = [request_hash, str(days), constraints or "", PROMPT_VERSION, candidate_version]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def create(
    db: Session,
    *,
    user_id: int | None,
    device_id: str | None,
    request_text: str,
    days: int,
    settings: Settings,
) -> tuple[Itinerary, str]:
    """建行并抢名额。返回 (行, "created" | "reused")。"""
    owner_key = owner_key_for(user_id, device_id)
    day = quota.today()
    if quota.budget_exhausted(db, day=day, budget=settings.trip_global_daily_token_budget):
        raise BudgetExhausted("全站当日预算已用尽")

    request_hash = request_hash_of(request_text)
    model = semantic.active_model(db)
    cache_key = cache_key_for(
        request_hash=request_hash,
        days=days,
        constraints=None,
        candidate_version=_candidate_version(db, model),
    )

    # 先查有没有现成的: 命中的话一个 token 都不用花, 也不占名额
    existing = db.scalar(
        select(Itinerary).where(Itinerary.owner_key == owner_key, Itinerary.cache_key == cache_key)
    )
    if existing is not None:
        return existing, "reused"

    if not quota.consume_slot(db, owner_key=owner_key, day=day, limit=settings.trip_daily_limit):
        raise DailyLimitExceeded("今日生成次数已用完")

    row = Itinerary(
        public_token=new_token(),
        owner_key=owner_key,
        days=days,
        request_hash=request_hash,
        status="pending",
        cache_key=cache_key,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # 竞态: 两个一样的请求同时走到这里, 另一个先落了行。复用它的, 并把名额还回去。
        db.rollback()
        quota.release_slot(db, owner_key=owner_key, day=day)
        found = db.scalar(
            select(Itinerary).where(
                Itinerary.owner_key == owner_key, Itinerary.cache_key == cache_key
            )
        )
        if found is None:
            raise
        return found, "reused"
    db.refresh(row)
    return row, "created"


def candidates_for(
    db: Session, *, request_text: str, settings: Settings
) -> list[Attraction]:
    """候选召回: 向量近邻优先, 不可用时退回热度。

    退回热度不是"降级到不能看": 候选只是给模型的挑选范围, 排不出好看的结果
    也比一条都不给强。没有候选才真的没法生成。
    """
    limit = settings.trip_candidate_limit
    model = semantic.active_model(db)
    if model:
        try:
            vector = build_embedding(settings).embed_one(request_text)
        except EmbeddingError:
            vector = None
        if vector:
            hits = semantic.semantic_search(db, vector, model=model, limit=limit)
            if hits:
                return [attraction for attraction, _ in hits]
    return content_based.popular_attractions(db, limit)


def _fail(db: Session, itinerary_id: int, message: str) -> None:
    """把行程置为失败。

    必须先 rollback: 调用点时可能正好处于一个已经失败/半截的事务里,
    不先清掉的话这条 UPDATE 会跟着那个事务一起被回滚 —— 结果就是永久 generating。
    """
    db.rollback()
    db.execute(
        update(Itinerary)
        .where(Itinerary.id == itinerary_id)
        .values(status="failed", error=message[:ERROR_MAX], heartbeat_at=func.now())
    )
    db.commit()


def _claim(db: Session, itinerary_id: int, worker_id: str) -> bool:
    result = db.execute(
        update(Itinerary)
        .where(Itinerary.id == itinerary_id, Itinerary.status == "pending")
        .values(
            status="generating",
            worker_id=worker_id,
            started_at=func.now(),
            heartbeat_at=func.now(),
        )
    )
    db.commit()
    return result.rowcount == 1


def _generate(
    db: Session, *, itinerary_id: int, settings: Settings, request_text: str, worker_id: str
) -> None:
    row = db.get(Itinerary, itinerary_id)
    if row is None or row.status != "pending":
        return
    if not _claim(db, itinerary_id, worker_id):
        return

    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    try:
        candidates = candidates_for(db, request_text=request_text, settings=settings)
        if not candidates:
            raise ValidationError("库内没有可编排的已发布景点")

        system, user = build_prompt(
            request_text=request_text,
            days=row.days,
            max_per_day=settings.trip_max_items_per_day,
            candidates=candidates,
        )
        client = build_llm(settings)
        raw, usage = client.chat_json_usage(system, user, max_tokens=settings.trip_max_tokens)

        candidate_ids = {attraction.id for attraction in candidates}
        items, degraded_note = validate(
            raw,
            candidate_ids=candidate_ids,
            days=row.days,
            max_per_day=settings.trip_max_items_per_day,
            candidates_sufficient=len(candidate_ids) >= row.days,
        )
        note = degraded_note
        raw_note = raw.get("note")
        if isinstance(raw_note, str) and raw_note.strip():
            note = " ".join(raw_note.split())[:200]

        # 条目与终态在**同一个事务**里提交: 要么"成功的行程有全部条目", 要么什么都不留。
        # 分两个事务反而会造出"有条目但状态还是 generating"的中间态, 只能靠回收器收拾。
        names = {attraction.id: attraction.name for attraction in candidates}
        db.add_all(
            [
                ItineraryItem(
                    itinerary_id=itinerary_id,
                    attraction_id=item.attraction_id,
                    attraction_name=names[item.attraction_id],
                    day_index=item.day_index,
                    seq=item.seq,
                    note=item.note,
                    reason=item.reason,
                )
                for item in items
            ]
        )
        db.execute(
            update(Itinerary)
            .where(Itinerary.id == itinerary_id, Itinerary.status == "generating")
            .values(
                status="succeeded",
                error=None,
                note=note,
                model=client.model,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                generated_at=func.now(),
                heartbeat_at=func.now(),
            )
        )
        db.commit()
    except (LLMError, EmbeddingError, ValidationError) as exc:
        _fail(db, itinerary_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 —— 任何意外都不能留下永久 generating
        _fail(db, itinerary_id, "生成失败: %s" % exc)
        return

    # 记账放在成功之后, 失败不计 token(上游可能压根没回 usage)
    quota.add_tokens(
        db,
        owner_key=row.owner_key,
        day=quota.today(),
        tokens=usage["prompt_tokens"] + usage["completion_tokens"],
    )


def _worker_id() -> str:
    """认领记录用的进程标识。只为排查"这条是谁在跑", 不参与判死。"""
    return "%s:%d" % (socket.gethostname(), os.getpid())


def run_generation(
    session_factory: Callable[[], Session],
    *,
    itinerary_id: int,
    settings: Settings,
    request_text: str,
) -> None:
    """后台任务入口。自带会话 —— 请求那个会话在响应发出时就已经关了。"""
    db = session_factory()
    try:
        _generate(
            db,
            itinerary_id=itinerary_id,
            settings=settings,
            request_text=request_text,
            worker_id=_worker_id(),
        )
    finally:
        db.close()


def _is_stale(row: Itinerary, settings: Settings) -> bool:
    """generating 且心跳过期。判据只认心跳时间, 不认"跑了多久" ——
    多 worker 下按耗时一刀切会误杀别人正在跑的任务。
    """
    if row.status != "generating":
        return False
    last = row.heartbeat_at or row.started_at
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.trip_stale_after_seconds)
    return last < cutoff


def reclaim_one(db: Session, row: Itinerary, *, settings: Settings) -> Itinerary:
    """读取路径上的自愈: 轮询到一个已经死掉的 generating, 就地置为 failed。

    一期不另起心跳线程: 生成是一次 60 秒内的同步调用, started_at 判死足够,
    阈值 180 秒远大于调用超时。要跑批量清理用 scripts/reclaim_itineraries.py。
    """
    if not _is_stale(row, settings):
        return row
    _fail(db, row.id, "生成中断(进程退出或超时), 请重试。")
    db.refresh(row)
    return row
