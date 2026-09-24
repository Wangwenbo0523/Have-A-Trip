"""推荐服务: 先读离线结果, 再退化到内容相似度, 最后兜底热门。

三级降级链, 目的是**任何情况下都不返回空列表**:
  1. rec_result 里有该用户的最新一批 -> 直接用(离线训练产物, algo 来自表)
  2. 没有 -> 拿用户最近互动过的景点做种子, 内容相似度算(不需要额外数据)
  3. 连种子都没有(新用户) -> 评分最高的已发布景点兜底

第 2、3 级是一期体验的关键: 冷启动阶段必然没有交互数据, 纯协同过滤一定给出空结果。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import Attraction, BehaviorLog, RecResult
from .content_based import PUBLISHED, popular_attractions, score, similar_attractions

ALGO_CONTENT = "content-based"
ALGO_POPULAR = "popular-fallback"

# 用最近几次互动当种子。只用一次容易被单次误点带偏。
MAX_SEEDS = 3
# 推荐结果里不该出现用户已经互动过的景点
SEEN_VERB = {"view": "浏览过", "favorite": "收藏过", "rate": "评过分", "share": "分享过"}
POPULAR_REASON = "暂时没有足够的行为数据, 先推荐评分较高的景点"


@dataclass
class Recommendation:
    attraction: Attraction
    rank: int
    score: float | None
    algo: str
    reason: str


class _TTLCache:
    """推荐结果的短 TTL 内存缓存。

    先不引 Redis: 单实例部署下, 这点缓存就够挡住列表页的重复请求。
    多实例部署时这里要换成 Redis, 否则各实例结果会短暂不一致。
    """

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._entries: dict[tuple, tuple[float, list]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple) -> list | None:
        if self.ttl <= 0:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._entries.pop(key, None)
                return None
            return value

    def set(self, key: tuple, value: list) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            self._entries[key] = (time.monotonic() + self.ttl, value)

    def invalidate_user(self, user_id: int) -> None:
        """用户刚上报了行为, 旧推荐立刻作废, 不然他要等 TTL 到期才看到变化。"""
        with self._lock:
            for key in [k for k in self._entries if k[0] == user_id]:
                self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_cache: _TTLCache | None = None
_cache_lock = threading.Lock()


def get_cache(settings) -> _TTLCache:
    """进程内共享的推荐缓存。TTL 配置变了就重建。"""
    global _cache
    with _cache_lock:
        if _cache is None or _cache.ttl != settings.rec_cache_ttl_seconds:
            _cache = _TTLCache(settings.rec_cache_ttl_seconds)
        return _cache


def _offline_results(db: Session, user_id: int, limit: int) -> list[Recommendation]:
    """读 rec_result 里该用户最新一批的结果。

    刻意不用 db/schema.sql 里的 v_latest_rec 视图: 视图只在 PostgreSQL 里存在,
    SQLite 上的测试跑不了。这里的子查询与视图语义完全一致。
    """
    latest = (
        select(func.max(RecResult.generated_at))
        .where(RecResult.user_id == user_id)
        .scalar_subquery()
    )
    rows = db.execute(
        select(RecResult, Attraction)
        .join(Attraction, Attraction.id == RecResult.attraction_id)
        .options(selectinload(Attraction.tags), selectinload(Attraction.images))
        .where(
            RecResult.user_id == user_id,
            RecResult.generated_at == latest,
            # 训练之后景点可能被下架, 结果表里的死链不能再推荐出去
            Attraction.status == PUBLISHED,
        )
        .order_by(RecResult.rank.asc())
        .limit(limit)
    ).all()

    return [
        Recommendation(
            attraction=attraction,
            rank=index,
            score=result.score,
            algo=result.algo,
            reason=result.reason,
        )
        for index, (result, attraction) in enumerate(rows, start=1)
    ]


def _recent_seeds(db: Session, user_id: int) -> list[tuple[Attraction, str]]:
    """用户最近互动过的景点(每个景点取最新一次事件), 新的在前。"""
    ranked = (
        select(
            BehaviorLog.attraction_id.label("attraction_id"),
            BehaviorLog.event_type.label("event_type"),
            BehaviorLog.created_at.label("created_at"),
            func.row_number()
            .over(
                partition_by=BehaviorLog.attraction_id,
                order_by=(BehaviorLog.created_at.desc(), BehaviorLog.id.desc()),
            )
            .label("rn"),
        )
        .where(BehaviorLog.user_id == user_id)
        .subquery()
    )
    rows = db.execute(
        select(Attraction, ranked.c.event_type)
        .join(ranked, ranked.c.attraction_id == Attraction.id)
        .options(selectinload(Attraction.tags), selectinload(Attraction.images))
        .where(ranked.c.rn == 1, Attraction.status == PUBLISHED)
        .order_by(ranked.c.created_at.desc(), Attraction.id.desc())
        .limit(MAX_SEEDS)
    ).all()
    return [(attraction, event_type) for attraction, event_type in rows]


def _seen_ids(db: Session, user_id: int) -> set[int]:
    return set(
        db.scalars(select(BehaviorLog.attraction_id).where(BehaviorLog.user_id == user_id).distinct())
    )


def _content_based(db: Session, user_id: int, limit: int) -> list[Recommendation]:
    seeds = _recent_seeds(db, user_id)
    if not seeds:
        return []

    seen = _seen_ids(db, user_id)
    best: dict[int, tuple[float, str, Attraction]] = {}

    for seed, event_type in seeds:
        verb = SEEN_VERB.get(event_type, "关注过")
        for candidate in similar_attractions(db, seed, limit=max(limit * 3, 12)):
            if candidate.id in seen:
                continue
            value = score(seed, candidate)
            # 同一候选可能被多个种子命中, 取最高分, 理由用最像的那个种子
            if value > best.get(candidate.id, (-1.0, "", None))[0]:
                best[candidate.id] = (value, f"因为它和你{verb}的「{seed.name}」相似", candidate)

    ordered = sorted(best.items(), key=lambda item: (-item[1][0], item[0]))
    return [
        Recommendation(
            attraction=candidate,
            rank=index,
            score=round(value, 4),
            algo=ALGO_CONTENT,
            reason=reason,
        )
        for index, (_, (value, reason, candidate)) in enumerate(ordered[:limit], start=1)
    ]


def get_recommendations(db: Session, user_id: int | None, limit: int) -> list[Recommendation]:
    """入口。user_id 为 None 时直接走兜底(匿名访客)。"""
    if user_id is not None:
        offline = _offline_results(db, user_id, limit)
        if offline:
            return offline

    results = _content_based(db, user_id, limit) if user_id is not None else []
    if len(results) >= limit:
        return results

    used = {item.attraction.id for item in results}
    if user_id is not None:
        used |= _seen_ids(db, user_id)

    for attraction in popular_attractions(db, limit * 2):
        if len(results) >= limit:
            break
        if attraction.id in used:
            continue
        used.add(attraction.id)
        results.append(
            Recommendation(
                attraction=attraction,
                rank=len(results) + 1,
                score=None,
                algo=ALGO_POPULAR,
                reason=POPULAR_REASON,
            )
        )
    return results
