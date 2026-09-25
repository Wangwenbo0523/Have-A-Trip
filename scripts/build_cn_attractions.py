#!/usr/bin/env python3
"""把官方名录数据集渲染成 db/seed/attractions_cn.sql。

输入是 db/seed/data/cn_a_level.csv(来历见 db/seed/data/README.md), 输出是可直接
psql 执行的种子 SQL。**不要手改输出文件**, 改数据请改 CSV 再重跑本脚本。

为什么单独一个文件, 不并进 seed.sql:
  * seed.sql 是逐条写、逐条审的自采档案(带简介、标签、方案、自绘封面);
    本文件是 1200 多条从政府公开名录搬过来的条目, 只有名称/等级/省市/来源这几列,
    两者的维护方式完全不同, 混在一个文件里会让两边都难读。
  * 本文件整份由脚本生成, 与 db/seed/images.sql 一样属于「生成物」。

与 seed.sql 的两处刻意不一致:
  * a_level 直接写进 INSERT 的列清单。seed.sql 把它放在文件末尾单独一块, 理由是
    「加进列清单会让每条老记录都要改一遍」; 本文件是新文件, 没有老记录, 放进列
    清单更短也更好核对。口径仍然是「只填能核实的」。
  * 这批条目**没有标签、没有旅游方案、没有配图**。它们是从名录搬来的名称条目,
    不是逐条整理的档案; 编一套标签或行程出来就是造假。封面由
    scripts/make_attraction_covers.py 统一生成(与 seed.sql 里的景点同一套逻辑)。

用法:
    python scripts/build_cn_attractions.py            # 生成 db/seed/attractions_cn.sql
    python scripts/build_cn_attractions.py --check    # 只校验磁盘上的文件是否与 CSV 一致
退出码: 0 成功或一致, 1 --check 发现不一致 / 数据有问题
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "db" / "seed" / "data" / "cn_a_level.csv"
OUT_PATH = REPO_ROOT / "db" / "seed" / "attractions_cn.sql"

# 这批条目共用一个分类。它们的主题(自然/古迹/博物馆...)在名录里没有, 与其猜一个,
# 不如老实开一格「A 级景区」。sort=100 让它排在现有 9 个主题分类之后。
CATEGORY = ("scenic-area", "A 级景区", 100)

GRADES = {"5A", "4A", "3A"}

HEADER = """-- Have-A-Trip · 中国 A 级旅游景区名录(种子数据)
--
-- 本文件由 scripts/build_cn_attractions.py 生成, **不要手改**。
-- 改数据请改 db/seed/data/cn_a_level.csv 再重跑脚本。
--
-- 内容: {total} 条中国大陆 A 级旅游景区(5A {n5} / 4A {n4} / 3A {n3}), 覆盖 {provs} 个省级行政区、
-- {cities} 个地市。全部来自政府公开名录, 来源与口径见 db/seed/data/README.md。
--
-- 刻意不造假的数据(与 db/seed/seed.sql 同一套口径):
--   * name_en / summary / description 一律 NULL —— 名录只有名称, 没有简介;
--     前端对空简介与空方案都有兜底文案(detail.descriptionEmpty / card.summary.none)。
--   * lat / lon 一律 NULL —— 一期不做地图与定位。文旅部的接口其实带经纬度, 但
--     本项目的坐标口径是「不填」, 不是「没查到」, 所以不引。
--   * ticket_price 一律 NULL, rating_avg / rating_count 一律 0。
--   * a_level 只写官方名录里核实过的等级, 不推算、不外推。
--   * **没有标签、没有旅游方案** —— 见文件头说明; 这两样只对自采档案有要求。
--
-- 幂等: 用 upsert, 重跑会把内容列同步成本文件里的版本(等级被摘牌也会跟着改)。
--
-- 执行(在 db/seed/seed.sql 之后):
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/attractions_cn.sql
"""

COLS = (
    "slug, name, name_en, category_id, country_code, province, city,\n"
    "    a_level, best_season, suggested_hours, ticket_price,\n"
    "    status, source, license, source_url"
)


def sql_text(value: str | None) -> str:
    """SQL 字符串字面量。空值与 None 都写成 NULL —— 空串与 NULL 在这张表里不是一个意思。"""
    if value is None or value == "":
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def read_rows() -> list[dict]:
    with io.open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    problems = []
    seen = set()
    for i, row in enumerate(rows, start=2):
        slug = (row.get("slug") or "").strip()
        if not slug:
            problems.append(f"第 {i} 行缺 slug")
            continue
        if slug in seen:
            problems.append(f"第 {i} 行 slug 重复: {slug}")
        seen.add(slug)
        if row.get("grade") not in GRADES:
            problems.append(f"第 {i} 行等级越界: {row.get('grade')!r}(schema 只允许 5A/4A/3A)")
        for field in ("name", "province", "source", "license"):
            if not (row.get(field) or "").strip():
                problems.append(f"第 {i} 行缺 {field}")
    if problems:
        print("数据集有问题:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    return rows


def render(rows: list[dict]) -> str:
    counts = {g: sum(1 for r in rows if r["grade"] == g) for g in ("5A", "4A", "3A")}
    provinces = len({r["province"] for r in rows})
    cities = len({(r["province"], r["city"]) for r in rows})
    block = ",\n".join(
        "(\n"
        "    %s, %s, NULL,\n"
        "    (SELECT id FROM category WHERE slug = %s),\n"
        "    'CN', %s, %s,\n"
        "    %s, NULL, NULL, NULL,\n"
        "    'published', %s, %s, %s\n"
        ")"
        % (
            sql_text(r["slug"]), sql_text(r["name"]), sql_text(CATEGORY[0]),
            sql_text(r["province"]), sql_text(r["city"]),
            sql_text(r["grade"]),
            sql_text(r["source"]), sql_text(r["license"]), sql_text(r.get("source_url")),
        )
        for r in rows
    )
    return (
        HEADER.format(total=len(rows), n5=counts["5A"], n4=counts["4A"], n3=counts["3A"],
                      provs=provinces, cities=cities)
        + "\nBEGIN;\n\n-- ---------------------------------------------------------------- 分类\n"
        "-- 这批条目共用一个分类, 理由见文件头。\n\n"
        "INSERT INTO category (slug, name, sort) VALUES\n"
        "    (%s, %s, %d)\n"
        "ON CONFLICT (slug) DO UPDATE SET\n"
        "    name = EXCLUDED.name,\n"
        "    sort = EXCLUDED.sort;\n\n"
        % (sql_text(CATEGORY[0]), sql_text(CATEGORY[1]), CATEGORY[2])
        + "-- ---------------------------------------------------------------- 景点\n\n"
        "INSERT INTO attraction (\n    " + COLS + "\n) VALUES\n"
        + block
        + "\nON CONFLICT (slug) DO UPDATE SET\n"
        "    name        = EXCLUDED.name,\n"
        "    category_id = EXCLUDED.category_id,\n"
        "    province    = EXCLUDED.province,\n"
        "    city        = EXCLUDED.city,\n"
        "    a_level     = EXCLUDED.a_level,\n"
        "    status      = EXCLUDED.status,\n"
        "    source      = EXCLUDED.source,\n"
        "    license     = EXCLUDED.license,\n"
        "    source_url  = EXCLUDED.source_url;\n\n"
        "COMMIT;\n"
    )


def main() -> int:
    rows = read_rows()
    sql = render(rows)
    if "--check" in sys.argv[1:]:
        if not OUT_PATH.exists():
            print(f"缺失 {OUT_PATH.relative_to(REPO_ROOT)}")
            return 1
        if io.open(OUT_PATH, encoding="utf-8", newline="").read() != sql:
            print(f"内容不一致 {OUT_PATH.relative_to(REPO_ROOT)}")
            print("跑 `python scripts/build_cn_attractions.py` 重新生成。")
            return 1
        print(f"一致: {len(rows)} 条 -> {OUT_PATH.relative_to(REPO_ROOT)}")
        return 0
    io.open(OUT_PATH, "w", encoding="utf-8", newline="\n").write(sql)
    print(f"已写入 {OUT_PATH.relative_to(REPO_ROOT)} ({len(sql.encode('utf-8'))} 字节, {len(rows)} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
