#!/usr/bin/env python3
"""离线批量向量化: 给已发布景点灌/更新描述向量。

为什么放在 scripts/ 而不是单独一个 embeddings/ 环境
---------------------------------------------------
原本的设计是「批量任务走独立环境」。但那个前提是向量化要用 torch —— 而这里走的是
HTTP 调服务商的 /embeddings(见 backend/app/llm/embedding.py), 依赖与 API 进程完全一样。
独立环境没有任何东西可隔离, 只会多出一套要同步维护的 requirements。
所以它就跑在 backend 的 venv 里, 不需要新的 CI 环境, 许可面也不扩大。

幂等性: 只重算 content_hash 变了的行。指纹里含 model 与 pipeline_version
(见 backend/app/search/canonical.py), 所以换模型或改拼串口径会让全部行失效并重建
—— 这正是要的: 新旧模型的向量混在一张表里比, 结果是垃圾而且不会报错。

用法:
    export DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/attraction_atlas
    python scripts/build_embeddings.py                 # 增量: 只补缺的与过期的
    python scripts/build_embeddings.py --dry-run       # 只报要做什么, 不写库、不打网络
    python scripts/build_embeddings.py --force         # 全部重算
    python scripts/build_embeddings.py --slug west-lake
    python scripts/build_embeddings.py --report        # 只看覆盖率

退出码: 0 正常; 2 向量模型未配置(离线任务不降级, 不假装成功)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.llm.embedding import EmbeddingClient, EmbeddingError  # noqa: E402
from app.models import Attraction, AttractionEmbedding  # noqa: E402
from app.search.canonical import PIPELINE_VERSION, canonical_text, content_hash  # noqa: E402
from app.search.vectors import encode  # noqa: E402


def pick(session: Session, slugs: list[str]) -> list[Attraction]:
    """只做已发布景点: draft / archived 不对外, 给它们算向量没有意义。"""
    statement = (
        select(Attraction).where(Attraction.status == "published").order_by(Attraction.slug)
    )
    if slugs:
        statement = statement.where(Attraction.slug.in_(slugs))
    return list(session.scalars(statement).all())


def existing(session: Session, model: str) -> dict[int, AttractionEmbedding]:
    rows = session.scalars(
        select(AttractionEmbedding).where(AttractionEmbedding.model == model)
    ).all()
    return {row.attraction_id: row for row in rows}


def stray_models(session: Session, model: str) -> list[tuple[str, int, int, int]]:
    """表里除当前模型之外的向量行。返回 (model, 行数, 最小维度, 最大维度)。

    active_model 只取行数最多的那一份, 所以换过向量模型之后留下的旧行不会被检索
    用到 —— 但也正因为用不到, 它们在界面上完全看不出来, 只能一直占着这张表。
    这里把它们报出来, 是为了让「换个模型要重灌」这件事有个收尾的地方。
    """
    rows = session.execute(
        select(
            AttractionEmbedding.model,
            func.count(),
            func.min(AttractionEmbedding.dim),
            func.max(AttractionEmbedding.dim),
        )
        .where(AttractionEmbedding.model != model)
        .group_by(AttractionEmbedding.model)
        .order_by(func.count().desc(), AttractionEmbedding.model.asc())
    ).all()
    return [(str(name), int(count), int(low), int(high)) for name, count, low, high in rows]


def report(session: Session, model: str) -> None:
    total = session.scalar(
        select(func.count()).select_from(Attraction).where(Attraction.status == "published")
    ) or 0
    done = session.scalar(
        select(func.count()).select_from(AttractionEmbedding).where(
            AttractionEmbedding.model == model
        )
    ) or 0
    dims = session.execute(
        select(AttractionEmbedding.dim, func.count())
        .where(AttractionEmbedding.model == model)
        .group_by(AttractionEmbedding.dim)
    ).all()
    print("模型      : %s" % model)
    print("已发布景点: %d" % total)
    print("已向量化  : %d" % done)
    if dims:
        print("维度分布  : %s" % ", ".join("%d 维 x %d" % (dim, count) for dim, count in dims))
        if len(dims) > 1:
            print("警告      : 同一模型下出现多种维度, 检索会拒绝使用这批数据。")
    for other, count, low, high in stray_models(session, model):
        span = "%d 维" % low if low == high else "%d..%d 维" % (low, high)
        print("其它模型  : %s x %d (%s) —— 检索不会用到;" % (other, count, span))
        print("            换模型时留下的旧向量。模型换回去还要用就别删, 确定不要了再清。")


def main() -> int:
    parser = argparse.ArgumentParser(description="给已发布景点灌描述向量")
    parser.add_argument("--dry-run", action="store_true", help="只报告要做什么, 不写库也不打网络")
    parser.add_argument("--force", action="store_true", help="忽略指纹, 全部重算")
    parser.add_argument("--slug", action="append", default=[], help="只处理指定景点(可重复)")
    parser.add_argument("--report", action="store_true", help="只看覆盖率然后退出")
    args = parser.parse_args()

    settings = get_settings()
    embedding = EmbeddingClient(settings)
    model = embedding.signature

    with Session(engine) as session:
        if args.report:
            report(session, model)
            return 0

        if not embedding.available and not args.dry_run:
            print(
                "向量模型未配置(EMBEDDING_PROVIDER)。\n"
                "本脚本不做关键词降级 —— 离线任务要么真的算出向量, 要么明确失败。\n"
                "见 backend/.env.example 的 AI / 向量检索一节。",
                file=sys.stderr,
            )
            return 2

        attractions = pick(session, args.slug)
        if not attractions:
            print("没有匹配的已发布景点。", file=sys.stderr)
            return 0

        known = existing(session, model)
        todo: list[tuple[Attraction, str, str]] = []
        for attraction in attractions:
            text = canonical_text(attraction)
            digest = content_hash(text, model)
            row = known.get(attraction.id)
            if args.force or row is None or row.content_hash != digest:
                todo.append((attraction, text, digest))

        print("模型      : %s" % model)
        print("待处理    : %d / %d" % (len(todo), len(attractions)))
        if not todo:
            report(session, model)
            return 0
        if args.dry_run:
            for attraction, _, _ in todo[:20]:
                print("  将会重算: %s" % attraction.slug)
            if len(todo) > 20:
                print("  ... 还有 %d 个" % (len(todo) - 20))
            return 0

        try:
            vectors = embedding.embed([text for _, text, _ in todo])
        except EmbeddingError as exc:
            print("向量化失败: %s" % exc, file=sys.stderr)
            return 2

        if len(vectors) != len(todo):
            print(
                "向量条数与请求不符: %d != %d" % (len(vectors), len(todo)), file=sys.stderr
            )
            return 2

        for (attraction, _, digest), vector in zip(todo, vectors):
            row = known.get(attraction.id)
            if row is None:
                session.add(
                    AttractionEmbedding(
                        attraction_id=attraction.id,
                        model=model,
                        dim=len(vector),
                        pipeline_version=PIPELINE_VERSION,
                        content_hash=digest,
                        embedding=encode(vector),
                    )
                )
            else:
                row.dim = len(vector)
                row.pipeline_version = PIPELINE_VERSION
                row.content_hash = digest
                row.embedding = encode(vector)
        session.commit()
        print("已写入    : %d" % len(todo))
        report(session, model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
