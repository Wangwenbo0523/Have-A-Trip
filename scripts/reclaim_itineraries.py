#!/usr/bin/env python3
"""回收卡住的行程生成任务: 把心跳过期的 generating 置为 failed。

为什么需要单独一个脚本
----------------------
读取路径已经会自愈(见 app/trip/service.py 的 reclaim_one): 用户轮询到一条死掉的任务
时会就地置失败, 不会一直转圈。但**没人轮询的那种**(用户提交完就关了页面)会一直留在
generating。这个脚本负责把它们扫掉, 顺带看一眼积压情况。

判据是**心跳过期**, 不是"跑了多久": 多 worker 下按耗时一刀切会误杀别人正在跑的任务。

用法:
    export DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas
    python scripts/reclaim_itineraries.py             # 回收
    python scripts/reclaim_itineraries.py --dry-run   # 只看有几条

退出码: 0 正常
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import func, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import Itinerary  # noqa: E402

MESSAGE = "生成中断(进程退出或超时), 请重试。"


def main() -> int:
    parser = argparse.ArgumentParser(description="回收心跳过期的行程生成任务")
    parser.add_argument("--dry-run", action="store_true", help="只统计, 不写库")
    args = parser.parse_args()

    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.trip_stale_after_seconds)

    with Session(engine) as session:
        stale = (
            func.coalesce(Itinerary.heartbeat_at, Itinerary.started_at).is_(None)
        ) | (func.coalesce(Itinerary.heartbeat_at, Itinerary.started_at) < cutoff)
        pending = session.scalar(
            select(func.count())
            .select_from(Itinerary)
            .where(Itinerary.status == "generating", stale)
        ) or 0
        print("心跳阈值: 早于 %s 视为已死" % cutoff.isoformat())
        print("待回收  : %d 条" % pending)
        if args.dry_run or not pending:
            return 0

        result = session.execute(
            update(Itinerary)
            .where(Itinerary.status == "generating", stale)
            .values(status="failed", error=MESSAGE)
        )
        session.commit()
        print("已回收  : %d 条" % result.rowcount)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
