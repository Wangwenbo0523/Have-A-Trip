"""第三步: 把 TopN 预测写回 rec_result, 按批次原子切换。

```
recsys/output/<batch_id>/predictions.tsv  --(校验 + 写回)-->  rec_result
recsys/output/<batch_id>/meta.json
```

三件值得单独说的事:

1. **整批一个事务。** 新批次要么整批可见, 要么旧状态原封不动 —— 回写中途出错, 线上读到的仍是
   上一批结果, 不会读到一个半拉子批次。
2. **写完顺手清掉同用户的旧批次。** API 按 max(generated_at) 取最新, 旧批次从此没有读者;
   留着只会让 rec_result 无限膨胀。只删**更旧**的, 所以重跑一个历史批次不会误删更新的批次。
3. **写回前校验死链。** 只保留「用户存在」且「景点 status='published'」的行 —— 训练之后景点
   被下架是常态, 推一个已下架的景点没有意义。被丢掉的行会打日志, 不静默。
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import common

SQL_KNOWN_USERS = "SELECT id FROM app_user WHERE id = ANY(%s)"
SQL_PUBLISHED_ITEMS = "SELECT id FROM attraction WHERE status = 'published' AND id = ANY(%s)"

SQL_DELETE_BATCH = "DELETE FROM rec_result WHERE batch_id = %s"
SQL_COUNT_BATCH = "SELECT count(*) FROM rec_result WHERE batch_id = %s"

SQL_INSERT = """
INSERT INTO rec_result (user_id, attraction_id, score, rank, algo, reason, batch_id, generated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (user_id, attraction_id, batch_id) DO NOTHING
"""

# 只删比本批次旧的。反过来会出事: 重跑一个历史批次会把更新的批次删掉。
SQL_PRUNE_OLDER = """
DELETE FROM rec_result
WHERE user_id = ANY(%s)
  AND (generated_at < %s OR (generated_at = %s AND batch_id <> %s))
"""

PREDICTIONS_FILE = "predictions.tsv"
META_FILE = "meta.json"
HEADER = ["user_id", "rank", "attraction_id", "score"]
DEFAULT_ALGO = "BPR"
# meta.json 缺失时的兜底文案。reason 是 NOT NULL 且要给用户看, 不能空写。
DEFAULT_REASON = "{algo} 离线推荐: 根据与你兴趣相近的人看过、收藏过、评过高分的景点挑出"


def latest_batch_dir(root: pathlib.Path) -> pathlib.Path | None:
    """recsys/output 下最新的一批。

    批次号形如 20260924T172447Z-f586, 字典序就是时间序(UTC), 不用读文件时间。
    """
    if not root.is_dir():
        return None
    dirs = sorted(p for p in root.iterdir()
                  if p.is_dir() and (p / PREDICTIONS_FILE).is_file())
    return dirs[-1] if dirs else None


def load_predictions(path: pathlib.Path, log):
    """读 predictions.tsv, 返回 (行, 问题计数)。表头不对返回 (None, {})。

    坏行只跳过不抛异常: 一份预测里偶尔有脏行, 不该让整批白跑; 但必须留下痕迹。
    """
    problems: collections.Counter = collections.Counter()
    rows = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        header = fh.readline().rstrip("\r\n").split("\t")
        if header != HEADER:
            log.error("表头应为 %s, 实际 %s", HEADER, header)
            return None, problems
        for line in fh:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) != len(HEADER):
                problems["列数不对"] += 1
                continue
            user_raw, rank_raw, item_raw, score_raw = parts
            try:
                user_id, rank, attraction_id = int(user_raw), int(rank_raw), int(item_raw)
            except ValueError:
                problems["不是整数"] += 1
                continue
            # rec_result.rank 有 CHECK (rank >= 1), 这里先挡一道, 免得整批插入失败
            if rank < 1:
                problems["rank 小于 1"] += 1
                continue
            try:
                score = float(score_raw) if score_raw.strip() else None
            except ValueError:
                score = None
                problems["分数无法解析"] += 1
            rows.append((user_id, rank, attraction_id, score))

    # 同一个 (用户, 景点) 只留排名靠前的那条
    best: dict[tuple[int, int], tuple[int, float | None]] = {}
    for user_id, rank, attraction_id, score in rows:
        key = (user_id, attraction_id)
        current = best.get(key)
        if current is None or rank < current[0]:
            best[key] = (rank, score)
    if len(best) < len(rows):
        problems["重复的 (用户, 景点)"] += len(rows) - len(best)

    deduped = [(user_id, rank, attraction_id, score)
               for (user_id, attraction_id), (rank, score) in best.items()]
    deduped.sort(key=lambda row: (row[0], row[1]))
    return deduped, problems


def duplicate_ranks(rows) -> dict[tuple[int, int], int]:
    """同一用户出现重复 rank 的地方。表上没有唯一约束, 只能靠这里提醒。"""
    seen: collections.Counter = collections.Counter((row[0], row[1]) for row in rows)
    return {key: count for key, count in seen.items() if count > 1}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="把 TopN 预测写回 rec_result")
    common.add_common_args(parser)
    parser.add_argument("--input", default=None,
                        help="产出目录(含 predictions.tsv), 默认取 --out-dir 下最新一批")
    parser.add_argument("--out-dir", default=None, help="产出根目录, 默认 recsys/output")
    parser.add_argument("--batch-id", default=None, help="写回的批次号, 默认沿用 meta.json 里的")
    parser.add_argument("--algo", default=None, help="算法名, 默认沿用 meta.json 里的")
    parser.add_argument("--reason", default=None, help="给用户看的推荐理由, 默认沿用 meta.json 里的")
    parser.add_argument("--no-prune", action="store_true", help="不清理同用户的旧批次(默认清理)")
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印, 不写库")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    common.setup_logging(args.verbose)
    log = common.log()

    out_root = pathlib.Path(args.out_dir) if args.out_dir else common.OUTPUT_DIR
    batch_dir = pathlib.Path(args.input) if args.input else latest_batch_dir(out_root)
    if batch_dir is None:
        log.warning("SKIP: %s 下没有含 %s 的批次目录。先跑 run_recbole.py。",
                    out_root, PREDICTIONS_FILE)
        return 0
    predictions_path = batch_dir / PREDICTIONS_FILE
    if not predictions_path.is_file():
        log.error("找不到 %s", predictions_path)
        return 2

    meta_path = batch_dir / META_FILE
    if meta_path.is_file():
        meta = common.read_json(meta_path)
    else:
        log.warning("找不到 %s, 用默认值合成(算法名与理由会是通用文案)。", meta_path)
        meta = {}

    algo = args.algo or str(meta.get("algo") or DEFAULT_ALGO)
    batch_id = args.batch_id or str(meta.get("batch_id") or batch_dir.name)
    reason = args.reason or str(meta.get("reason") or DEFAULT_REASON.format(algo=algo))
    # 整批共用一个 generated_at, 不然 API 的 max(generated_at) 会只挑到一部分行
    generated_at = (common.parse_iso(str(meta["generated_at"]))
                    if meta.get("generated_at") else common.utcnow())

    rows, problems = load_predictions(predictions_path, log)
    if rows is None:
        return 2
    if not rows:
        log.warning("SKIP: %s 里没有一行可用预测, 不写库。", predictions_path)
        return 0
    log.info("读到预测 %d 行 / 问题 %s / 批次 %s / 算法 %s",
             len(rows), dict(problems) or "无", batch_id, algo)

    dups = duplicate_ranks(rows)
    if dups:
        log.warning("同一用户出现重复 rank(API 会把它们并列返回): %s",
                    sorted(dups.items())[:5])

    user_ids = sorted({row[0] for row in rows})
    item_ids = sorted({row[2] for row in rows})

    with common.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_KNOWN_USERS, (user_ids,))
            known_users = {row[0] for row in cur.fetchall()}
            cur.execute(SQL_PUBLISHED_ITEMS, (item_ids,))
            live_items = {row[0] for row in cur.fetchall()}

        missing_users = {row[0] for row in rows} - known_users
        missing_items = {row[2] for row in rows} - live_items
        if missing_users:
            log.warning("丢掉 %d 个库里没有的用户: %s",
                        len(missing_users), sorted(missing_users)[:10])
        if missing_items:
            log.warning("丢掉 %d 个不存在或已下架的景点: %s",
                        len(missing_items), sorted(missing_items)[:10])

        kept = [row for row in rows if row[0] in known_users and row[2] in live_items]
        if not kept:
            log.warning("SKIP: 所有预测都被校验挡掉, 不写库(否则就是一次全空的写入)。")
            return 0
        log.info("校验后保留 %d 行 / 丢掉 %d 行 / 覆盖 %d 个用户",
                 len(kept), len(rows) - len(kept), len({row[0] for row in kept}))

        params = [(user_id, attraction_id, score, rank, algo, reason, batch_id, generated_at)
                  for user_id, rank, attraction_id, score in kept]

        if args.dry_run:
            conn.rollback()
            log.info("DRY-RUN: 会写入 %d 行到 rec_result, 批次 %s, 生成时间 %s (未落库)",
                     len(params), batch_id, common.iso(generated_at))
            log.info("DRY-RUN: 前两行 %s", params[:2])
            return 0

        # 一个事务: 先清本批次(重跑同一批次是幂等的), 再整体插入, 最后清同用户的旧批次
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(SQL_DELETE_BATCH, (batch_id,))
                replaced = cur.rowcount
                cur.executemany(SQL_INSERT, params)
                cur.execute(SQL_COUNT_BATCH, (batch_id,))
                written = cur.fetchone()[0]
                pruned = 0
                if not args.no_prune:
                    cur.execute(SQL_PRUNE_OLDER, (sorted({row[0] for row in kept}),
                                                  generated_at, generated_at, batch_id))
                    pruned = cur.rowcount

    log.info("rec_result 写入 %d 行 / 批次 %s / 生成时间 %s",
             written, batch_id, common.iso(generated_at))
    if replaced:
        log.info("同批次旧结果被替换 %d 行(重跑同一批次是幂等的)", replaced)
    if args.no_prune:
        log.info("按 --no-prune 保留同用户的旧批次")
    else:
        log.info("清理同用户的更旧批次 %d 行", pruned)
    log.info("核对: select batch_id, count(*) from rec_result group by 1 order by 1;")
    return 0


if __name__ == "__main__":
    sys.exit(main())