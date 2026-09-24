"""离线训练链路的共用部分：连库、路径、批次号、日志、以及「行为 -> 隐式偏好」的口径。

这个目录下的脚本**只跑在 Python 3.11 的独立环境**里（为什么，见 README 与
`../docs/BASES.md`）。它们绝不能被 `backend/` import —— `backend/tests/test_no_recbole.py`
有一条 AST 检查专门拦这件事。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import secrets
import sys

# ---------------------------------------------------------------------------- 路径
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "recsys" / "config" / "recbole.yaml"
DATASET_DIR = REPO_ROOT / "recsys" / "dataset"
OUTPUT_DIR = REPO_ROOT / "recsys" / "output"
SAVED_DIR = REPO_ROOT / "recsys" / "saved"

DEFAULT_DATASET = "attraction_atlas"
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/attraction_atlas"

# ---------------------------------------------------------------------------- 行为口径
# 「行为 -> 隐式偏好强度」的映射。
#
# **这不是评分。** 对用户可见的评分只有 `attraction.rating_avg` / `rating_count`，
# 它们只能由 `rate` 事件聚合得出（见 db/README.md 的字段口径）。下面这些分值只喂给
# 离线模型当正反馈强度用，不会写进任何用户可见的字段，也不允许拿去初始化种子数据。
#
# 为什么要这么映射：BPR 这类协同过滤只吃「正反馈」这一种信号，得先把
# 「浏览 / 收藏 / 分享 / 评分」四种强弱不同的行为折算到同一根轴上。
EVENT_RATING = {
    "favorite": 4.0,   # 收藏：明确的强正反馈
    "share": 3.0,      # 分享：也算正反馈，但比收藏弱
}
VIEW_STRONG_RATING = 2.0   # 浏览且停留达标的，算弱正反馈
VIEW_WEAK_RATING = 1.0     # 点开就走的，基本是误触
STRONG_DWELL_MS = 30_000   # 停留超过 30 秒才算「看进去了」

# 同一个用户对同一个景点的多次行为，只取**最后一次**（与 backend/app/aggregates.py
# 重算评分的口径一致）。

# 训练前的最低数据量。低于就**明确跳过**，不产垃圾推荐 —— 协同过滤在几十条交互上
# 只能过拟合，与其写出噪音不如让 API 走内容相似度兜底（S2 已经做了）。
MIN_INTERACTIONS = 200
MIN_USERS = 20
MIN_ITEMS = 20


def implicit_rating(event_type: str, rating, dwell_ms) -> float:
    """把一个行为折算成隐式偏好强度。`rate` 用用户给的实际分。"""
    if event_type == "rate":
        if rating is None:
            # 数据库的 CHECK 约束不允许这种行, 这里只是防御
            return 0.0
        return float(rating)
    if event_type in EVENT_RATING:
        return EVENT_RATING[event_type]
    if event_type == "view":
        return VIEW_STRONG_RATING if (dwell_ms or 0) >= STRONG_DWELL_MS else VIEW_WEAK_RATING
    raise ValueError(f"未知的 event_type: {event_type!r}")


# ---------------------------------------------------------------------------- 数据库
def database_url(explicit: str | None = None) -> str:
    """按 显式参数 -> RECSYS_DATABASE_URL -> DATABASE_URL -> 默认值 取连接串。

    与 backend 共用 `DATABASE_URL` 时不必手改：SQLAlchemy 的
    `postgresql+psycopg://` 前缀在这里去掉即可。
    """
    url = explicit or os.environ.get("RECSYS_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return DEFAULT_DATABASE_URL
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


def mask_url(url: str) -> str:
    """把连接串里的密码换成 ***，用于日志与 stats.json。"""
    import re

    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


def connect(url: str | None = None, **kwargs):
    """连数据库。psycopg 只在这里 import, 让 --help 在没有依赖时也能跑。"""
    import psycopg

    return psycopg.connect(database_url(url), **kwargs)


# ---------------------------------------------------------------------------- 批次与时间
def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_batch_id(ts: dt.datetime | None = None) -> str:
    """批次号：`20260925T011530Z-3f9a`。回写按它整体切换。"""
    ts = ts or utcnow()
    return ts.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)


def parse_iso(text: str) -> dt.datetime:
    """解析 `...Z` 形式的时间戳，产出带时区的 datetime。"""
    ts = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts


# ---------------------------------------------------------------------------- JSON 与日志
def write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # 训练时的进度条与第三方库的碎日志没必要全飘出来
    for noisy in ("matplotlib", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """每个脚本都有的那几个参数。

    注意参数名刻意避开 RecBole 的配置键名：RecBole 会自己解析 `sys.argv` 里
    `--key=value` 形式的参数并当成训练配置（见 config/configurator.py），
    名字撞上就会悄悄改掉训练超参。
    """
    parser.add_argument("--database-url", default=None,
                        help="连接串。默认读 RECSYS_DATABASE_URL / DATABASE_URL, 再不行用本机默认值")
    parser.add_argument("--dataset", default=DEFAULT_DATASET,
                        help=f"数据集名, 对应 recsys/dataset/<名字>/(默认 {DEFAULT_DATASET})")
    parser.add_argument("--verbose", action="store_true", help="打开 DEBUG 日志")
    return parser


def log() -> logging.Logger:
    return logging.getLogger("recsys")
