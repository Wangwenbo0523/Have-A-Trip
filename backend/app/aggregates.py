"""从 behavior_log 重算聚合值。

`attraction.rating_avg` / `rating_count` 的唯一来源是 behavior_log —— 种子数据里
它们一律为 0, 不伪造评分。这里在每次 rate 事件写入后重算。

注意口径: 同一个用户对同一景点的多次评分**只算最后一次**。直接 avg 全部 rate 行会让
反复改分的用户获得更高权重, 所以用窗口函数取每个用户的最新一条。
用窗口函数而不是 PostgreSQL 的 DISTINCT ON, 是为了让 SQLite 上的测试也跑得通。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Attraction, BehaviorLog


def recount_attraction_rating(db: Session, attraction_id: int) -> None:
    """重算某景点的 rating_avg / rating_count。调用方负责 commit。"""
    latest = (
        select(
            BehaviorLog.user_id.label("user_id"),
            BehaviorLog.rating.label("rating"),
            func.row_number()
            .over(
                partition_by=BehaviorLog.user_id,
                order_by=(BehaviorLog.created_at.desc(), BehaviorLog.id.desc()),
            )
            .label("rn"),
        )
        .where(
            BehaviorLog.attraction_id == attraction_id,
            BehaviorLog.event_type == "rate",
            BehaviorLog.rating.is_not(None),
        )
        .subquery()
    )

    row = db.execute(
        select(func.count(latest.c.rating), func.avg(latest.c.rating)).where(latest.c.rn == 1)
    ).one()
    count = int(row[0] or 0)
    average = row[1]

    attraction = db.get(Attraction, attraction_id)
    if attraction is None:
        return
    attraction.rating_count = count
    attraction.rating_avg = average if average is not None else 0
