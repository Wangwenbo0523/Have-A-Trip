"""第一步：把业务库里的用户行为导成 RecBole 的原子文件格式。

```
behavior_log  -->  recsys/dataset/<dataset>/<dataset>.inter  (用户-景点-强度-时间)
                   recsys/dataset/<dataset>/<dataset>.item   (景点侧信息)
                   recsys/dataset/<dataset>/stats.json       (规模, 给下一步做门槛判断)
```

几个刻意的选择：

* **只导 `published` 的景点。** 下架景点的历史行为仍然留在库里（不删用户数据），但不进训练集 ——
  训练出来的东西是要推给用户的，推一个已下架的景点没有意义。
* **同一个 (用户, 景点) 只留最后一次行为**，与 `backend/app/aggregates.py` 重算评分的口径一致。
  不按条累积，否则反复点开同一个景点的人会在训练里被算成更高的权重。
* **强度不是评分**，映射表在 `common.py` 里，理由也写在那儿。强度只喂模型，不写回任何
  用户可见的字段。
* 输出目录已进 `.gitignore`，训练数据与产物不入库。
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import common

# 每个 (用户, 景点) 取最后一次行为。用窗口函数而不是 PostgreSQL 的 DISTINCT ON,
# 与 backend 的口径一致, 将来若要换库也少一处特例。
SQL_LATEST_BEHAVIOR = """
WITH ranked AS (
    SELECT b.user_id,
           b.attraction_id,
           b.event_type,
           b.rating,
           b.dwell_ms,
           b.created_at,
           row_number() OVER (
               PARTITION BY b.user_id, b.attraction_id
               ORDER BY b.created_at DESC, b.id DESC
           ) AS rn
    FROM behavior_log b
)
SELECT r.user_id, r.attraction_id, r.event_type, r.rating, r.dwell_ms,
       extract(epoch FROM r.created_at) AS ts
FROM ranked r
JOIN attraction a ON a.id = r.attraction_id AND a.status = 'published'
WHERE r.rn = 1
ORDER BY r.user_id, r.attraction_id
"""

SQL_ITEMS = """
SELECT id, category_id, coalesce(city, '')
FROM attraction
WHERE status = 'published' AND id = ANY(%s)
ORDER BY id
"""

SQL_COUNTS = """
SELECT
    (SELECT count(*) FROM attraction WHERE status = 'published') AS published,
    (SELECT count(DISTINCT b.attraction_id) FROM behavior_log b
       JOIN attraction a ON a.id = b.attraction_id AND a.status = 'published') AS touched
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="导出交互数据(RecBole 原子文件)")
    common.add_common_args(parser)
    parser.add_argument("--out-dir", default=None, help="输出根目录, 默认 recsys/dataset")
    args = parser.parse_args(argv)
    common.setup_logging(args.verbose)
    log = common.log()

    out_root = pathlib.Path(args.out_dir) if args.out_dir else common.DATASET_DIR
    dataset_dir = out_root / args.dataset
    dataset_dir.mkdir(parents=True, exist_ok=True)

    with common.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_LATEST_BEHAVIOR)
            rows = cur.fetchall()
            cur.execute(SQL_COUNTS)
            published, touched = cur.fetchone()
            attraction_ids = sorted({row[1] for row in rows})
            if attraction_ids:
                cur.execute(SQL_ITEMS, (attraction_ids,))
                item_rows = cur.fetchall()
            else:
                item_rows = []

    if not rows:
        log.warning("没有任何可用的行为数据(需要 published 景点的 view/favorite/rate/share)。")
        log.warning("不产出文件: 空数据集会让 RecBole 直接报错, 而这里应当是一次干净的跳过。")
        return 0

    # ---------------------------------------------------------------- .inter
    inter_path = dataset_dir / f"{args.dataset}.inter"
    events: collections.Counter = collections.Counter()
    histogram: collections.Counter = collections.Counter()
    with inter_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("user_id:token\tattraction_id:token\trating:float\ttimestamp:float\n")
        for user_id, attraction_id, event_type, rating, dwell_ms, ts in rows:
            value = common.implicit_rating(event_type, rating, dwell_ms)
            events[event_type] += 1
            histogram[value] += 1
            fh.write(f"{user_id}\t{attraction_id}\t{value:.1f}\t{float(ts):.0f}\n")

    # ---------------------------------------------------------------- .item
    item_path = dataset_dir / f"{args.dataset}.item"
    with item_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("attraction_id:token\tcategory_id:token\tcity:token\n")
        for attraction_id, category_id, city in item_rows:
            fh.write(f"{attraction_id}\t{category_id}\t{city}\n")

    users = {row[0] for row in rows}
    items = {row[1] for row in rows}
    stats = {
        "generated_at": common.iso(common.utcnow()),
        "dataset": args.dataset,
        "database_url": common.mask_url(common.database_url(args.database_url)),
        "interactions": len(rows),
        "users": len(users),
        "items": len(items),
        "events": dict(sorted(events.items())),
        "rating_histogram": {f"{k:.1f}": v for k, v in sorted(histogram.items())},
        "attractions_published": published,
        "attractions_with_behavior": touched,
        "thresholds": {
            "min_interactions": common.MIN_INTERACTIONS,
            "min_users": common.MIN_USERS,
            "min_items": common.MIN_ITEMS,
        },
        "files": {"inter": inter_path.name, "item": item_path.name},
    }
    common.write_json(dataset_dir / "stats.json", stats)

    log.info("交互 %d 条 / 用户 %d 人 / 景点 %d 个 -> %s",
             len(rows), len(users), len(items), inter_path)
    log.info("事件构成: %s", dict(sorted(events.items())))
    log.info("强度分布: %s", {f"{k:.1f}": v for k, v in sorted(histogram.items())})
    log.info("已发布景点 %d 个, 其中被行为覆盖 %d 个", published, touched)

    gates = [("MIN_INTERACTIONS", common.MIN_INTERACTIONS, stats["interactions"]),
             ("MIN_USERS", common.MIN_USERS, stats["users"]),
             ("MIN_ITEMS", common.MIN_ITEMS, stats["items"])]
    thin = [f"{name}={got} < {need}" for name, need, got in gates if got < need]
    if thin:
        log.warning("数据量低于训练门槛(%s), 下一步 run_recbole.py 会跳过训练。", "; ".join(thin))
        log.warning("这是预期行为: 冷启动阶段靠 API 的内容相似度兜底, 不要硬训。")
    else:
        log.info("数据量达到训练门槛, 可以跑 run_recbole.py。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
