#!/usr/bin/env python3
"""离线批量生成景点简介草稿: 只出待审 SQL, 永不写库。

为什么是离线
------------
简介一旦入库就是**景点档案的一部分**, 用户会把它当事实读。所以模型不碰运行时:
它只在本地生成草稿, 由人逐条核对后手工执行 SQL 入库。这个脚本**不调用任何写库
路径**, 对库只做 SELECT。

护栏
----
1. 输入只有这个景点已公开的档案字段(见 app/llm/draft.py), 数字必须可溯源;
2. 产物里只有 `UPDATE attraction SET summary = …` —— 来源、许可、状态、分类都不碰;
3. 模型不可用直接退出(code 2), 不生成空文件、不假装成功。

用法:
    export DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas
    python scripts/draft_attraction_summaries.py                  # 简介为空或过短的, 最多 20 个
    python scripts/draft_attraction_summaries.py --all --limit 5  # 不限「缺简介」, 只做 5 个
    python scripts/draft_attraction_summaries.py --slug west-lake  # 指定景点

退出码: 0 正常; 2 模型未配置(离线生成不降级)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.llm.client import LLMClient  # noqa: E402
from app.llm.draft import DISCLAIMER, drafts, needs_draft, render_sql  # noqa: E402
from app.models import Attraction  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "db" / "seed" / "drafts" / "ai_summary_draft.sql"


def pick(session: Session, slugs: list[str], limit: int, only_missing: bool) -> list[Attraction]:
    """挑出这一轮要处理的景点。只取已发布的 —— draft / archived 不对外, 不给它写简介。"""
    stmt = select(Attraction).where(Attraction.status == "published").order_by(Attraction.slug)
    if slugs:
        stmt = stmt.where(Attraction.slug.in_(slugs))
    rows = list(session.scalars(stmt).all())
    if only_missing:
        rows = [row for row in rows if needs_draft(row)]
    return rows[:limit] if limit > 0 else rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线生成景点简介草稿(产物是待审 SQL, 不写库)")
    parser.add_argument("--limit", type=int, default=20, help="最多处理几个景点, 0 表示不限")
    parser.add_argument("--slug", action="append", default=[], help="只处理这些 slug, 可重复")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="待审 SQL 写到哪里")
    parser.add_argument("--all", action="store_true",
                        help="不筛「简介为空或过短」, 所有已发布景点都来一版草稿")
    args = parser.parse_args(argv)

    client = LLMClient(get_settings())
    if not client.available:
        print("[跳过] 模型未配置(LLM_PROVIDER) —— 离线生成必须真的用模型, 不降级、不假装成功。",
              file=sys.stderr)
        return 2

    with Session(engine) as session:
        targets = pick(session, args.slug, args.limit, not args.all)
        if not targets:
            print("[跳过] 没有符合条件的景点(默认只挑简介为空或短于门槛的, 用 --all 放开)。")
            return 0
        print("[信息] 目标 %d 个景点 | 模型 %s" % (len(targets), client.model))
        results = drafts(client, targets)

    for item in results:
        print("  %-4s %-28s %s" % ("通过" if item.grounded else "跳过", item.slug,
                                   item.text or item.note))

    sql = render_sql(results, client.model or "")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(sql, encoding="utf-8", newline="\n")
    kept = sum(1 for item in results if item.grounded and item.text)
    print("\n[完成] %d/%d 条通过校验 -> %s" % (kept, len(results), args.out))
    print("[提醒] %s 核对通过后把语句抄进 db/seed/seed.sql。" % DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
