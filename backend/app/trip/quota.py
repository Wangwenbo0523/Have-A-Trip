"""限额与预算的原子记数。

为什么不用 count(itinerary)
---------------------------
「先 select 条数, 判断没超, 再 insert」在**任何**隔离级别下都不是原子的:
两个并发请求会同时通过检查, 然后都调模型、都计费。要修就得加锁或唯一约束,
而计数器行是最简单的那种。

这里的办法是一条语句完成读-改-写:

    UPDATE trip_quota SET used = used + 1
     WHERE owner_key = :owner AND day = :day AND used < :limit

单条 UPDATE 的读-改-写在 PostgreSQL(行锁)与 SQLite(写锁)上都是原子的。
拿 rowcount 判断有没有抢到名额 —— 0 就是没抢到, 不需要再查一次。

限额按**东八区自然日**结算。用固定偏移而不是 IANA 时区名: Windows 上的 Python
没有内置 tzdata, ZoneInfo("Asia/Shanghai") 会直接抛异常, 而这里要的只是"哪天"。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import TripQuota

# 全站 token 预算记在这一行上, 与具体 owner 区分开
GLOBAL_OWNER = "__global__"

BEIJING = timezone(timedelta(hours=8))


def today() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d")


def ensure_row(db: Session, owner_key: str, day: str) -> None:
    """计数器行不存在就建一个。并发下撞唯一键是正常的, 回滚即可。"""
    exists = db.scalar(
        select(TripQuota.id).where(TripQuota.owner_key == owner_key, TripQuota.day == day)
    )
    if exists is not None:
        return
    db.add(TripQuota(owner_key=owner_key, day=day, used=0, tokens_used=0))
    try:
        db.commit()
    except IntegrityError:
        # 另一个请求抢先建好了。它也是 0, 没有任何影响。
        db.rollback()


def consume_slot(db: Session, *, owner_key: str, day: str, limit: int) -> bool:
    """抢一个当日名额。limit <= 0 表示不限, 直接放行。"""
    if limit <= 0:
        return True
    ensure_row(db, owner_key, day)
    result = db.execute(
        update(TripQuota)
        .where(
            TripQuota.owner_key == owner_key,
            TripQuota.day == day,
            TripQuota.used < limit,
        )
        .values(used=TripQuota.used + 1, updated_at=func.now())
    )
    db.commit()
    return result.rowcount == 1


def release_slot(db: Session, *, owner_key: str, day: str) -> None:
    """归还名额。只在"抢到了名额但最终复用了既有行程"这条竞态路径上调用。"""
    db.execute(
        update(TripQuota)
        .where(
            TripQuota.owner_key == owner_key,
            TripQuota.day == day,
            TripQuota.used > 0,
        )
        .values(used=TripQuota.used - 1, updated_at=func.now())
    )
    db.commit()


def budget_exhausted(db: Session, *, day: str, budget: int) -> bool:
    """全站当日 token 预算是否已用尽。budget <= 0 表示不限。"""
    if budget <= 0:
        return False
    ensure_row(db, GLOBAL_OWNER, day)
    used = db.scalar(
        select(TripQuota.tokens_used).where(
            TripQuota.owner_key == GLOBAL_OWNER, TripQuota.day == day
        )
    )
    return bool(used) and int(used) >= budget


def add_tokens(db: Session, *, owner_key: str, day: str, tokens: int) -> None:
    """生成结束后记账: 该 owner 与全站各加一笔。token 为 0 时什么都不做。"""
    if tokens <= 0:
        return
    for key in (owner_key, GLOBAL_OWNER):
        ensure_row(db, key, day)
        db.execute(
            update(TripQuota)
            .where(TripQuota.owner_key == key, TripQuota.day == day)
            .values(tokens_used=TripQuota.tokens_used + tokens, updated_at=func.now())
        )
    db.commit()
