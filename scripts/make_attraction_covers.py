#!/usr/bin/env python3
"""为每个景点生成一张自绘封面图, 并产出配图的种子 SQL。

为什么是自绘: 图片和代码一样是版权资产, 但更难查。原计划用 CC0 / 公有领域的图库,
实测 Wikimedia Commons 与 Openverse 在本机网络下不可达(连接超时), 而 Unsplash /
Pixabay 一类可访问的图库用的是各自的专有许可(不是 CC0), 且对中国具体景点的覆盖很薄。
与其塞一批出处含糊的照片, 不如**自己画**: 出处就是本脚本, 与仓库同许可, 将来闭源
不受任何第三方约束。

产出两个东西:
  1. frontend/public/images/covers/<slug>.svg   每个景点一张, 按 slug 确定性生成
  2. db/seed/images.sql                         50 条 attraction_image 的幂等种子

同一个 slug 永远生成同一张图(颜色与构图都由 sha256(slug) 推导), 所以可以拿 --check
校验仓库里的文件有没有被手改过。

用法:
    python scripts/make_attraction_covers.py            # 生成 SVG 与 images.sql
    python scripts/make_attraction_covers.py --check    # 只校验是否与脚本一致
退出码: 0 成功或一致, 1 --check 发现不一致
"""
from __future__ import annotations

import colorsys
import hashlib
import io
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "db" / "seed" / "seed.sql"
IMAGES_SQL_PATH = REPO_ROOT / "db" / "seed" / "images.sql"
COVER_DIR = REPO_ROOT / "frontend" / "public" / "images" / "covers"

# ---------------------------------------------------------------- 版式
#
# 画布 3:2。详情页图集是 grid + object-fit: cover, 容器约 240x170(比例 1.41),
# 列宽变大时容器比例可以到 2.4 左右, 那时会裁掉上下。
#
# 所以整张图分三段, 中间那段是**任何容器比例下都不会被裁掉的安全区**:
#   y 0   ~ 160   上边距, 可能被裁
#   y 162 ~ 350   标题面板          <- 安全区内
#   y 360 ~ 655   场景             <- 安全区内(660 以下可能被裁)
#   y 660 ~ 800   地面 / 水面       <- 纯装饰, 裁掉也不影响
W, H = 1200, 800
PANEL = (160, 162, 880, 188)   # x, y, w, h
GROUND_Y = 660
SCENE_TOP = 360

# 署名与许可。所有封面共用一条, 声明页会聚合成一行。
CREDIT = "Have-A-Trip 自绘"
LICENSE = "MIT"
CAPTION = "自绘示意图"
URL_TEMPLATE = "/images/covers/{slug}.svg"

# 每个分类一套配色: 天空上端 / 天空下端 / 远景 / 中景 / 近景 / 点缀色。
# 具体到某个景点时整体做一次色相偏移, 所以同分类的图不会长得一模一样。
PALETTES = {
    "nature": [
        (0x1B, 0x2A, 0x3A), (0x3E, 0x5C, 0x5A), (0x2C, 0x44, 0x50),
        (0x22, 0x36, 0x42), (0x16, 0x25, 0x2F), (0xF4, 0x67, 0x32),
    ],
    "history": [
        (0x2B, 0x1E, 0x1A), (0x7A, 0x4E, 0x33), (0x5E, 0x3C, 0x27),
        (0x45, 0x2C, 0x1D), (0x28, 0x19, 0x11), (0xE8, 0xA0, 0x55),
    ],
    "museum": [
        (0x1D, 0x22, 0x2C), (0x3C, 0x46, 0x57), (0x2E, 0x37, 0x46),
        (0x23, 0x2A, 0x36), (0x16, 0x1A, 0x22), (0x8F, 0xA8, 0xC8),
    ],
    "landmark": [
        (0x14, 0x18, 0x2A), (0x33, 0x2E, 0x52), (0x26, 0x24, 0x44),
        (0x1B, 0x1A, 0x33), (0x10, 0x0F, 0x20), (0xF4, 0x67, 0x32),
    ],
    "religion": [
        (0x24, 0x1A, 0x22), (0x52, 0x33, 0x33), (0x3E, 0x27, 0x2A),
        (0x2D, 0x1C, 0x20), (0x1B, 0x11, 0x15), (0xE0, 0xB0, 0x5C),
    ],
    "ancient-town": [
        (0x1A, 0x22, 0x26), (0x39, 0x4E, 0x4E), (0x2B, 0x3C, 0x3E),
        (0x1F, 0x2C, 0x2F), (0x13, 0x1C, 0x1F), (0xE8, 0x8A, 0x5A),
    ],
    "theme-park": [
        (0x18, 0x1B, 0x33), (0x3D, 0x35, 0x67), (0x2C, 0x28, 0x50),
        (0x1F, 0x1D, 0x3C), (0x12, 0x11, 0x26), (0xF4, 0x67, 0x32),
    ],
}

CATEGORY_LABELS = {
    "nature": "自然风光", "history": "历史古迹", "museum": "博物馆",
    "landmark": "城市地标", "religion": "宗教场所",
    "ancient-town": "古镇村落", "theme-park": "主题乐园",
}

FONT_STACK = "'PingFang SC','Microsoft YaHei','Hiragino Sans GB',sans-serif"


def f(value: float) -> str:
    """统一坐标格式, 保证同一 slug 每次序列化结果完全一致。"""
    return "%.1f" % value


def hexed(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb)


def shift(rgb, hue: float, sat: float = 1.0, val: float = 1.0) -> str:
    """把颜色在 HSV 空间里整体挪一下, 用来给同分类的不同景点制造差异。"""
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + hue) % 1.0
    s = max(0.0, min(1.0, s * sat))
    v = max(0.0, min(1.0, v * val))
    return hexed(tuple(c * 255.0 for c in colorsys.hsv_to_rgb(h, s, v)))


def rand01(slug: str):
    """由 slug 推导的确定性随机序列(0..1)。不依赖 random 的全局状态。"""
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    values = [b / 255.0 for b in digest]

    def get(i: int) -> float:
        return values[i % len(values)]

    return get


def parse_attractions(text: str):
    """从 seed.sql 里抽出 (slug, name, category)。

    只认 seed.sql 里「单独一行左括号, 下一行是 'slug', '名称', 'Name',」的固定写法:
    比整份 SQL 解析可靠得多, 而且不用连数据库(所以 --check 在 CI 里也能裸跑)。
    """
    rows = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() != "(" or i + 1 >= len(lines):
            continue
        m = re.match(r"^\s*'([a-z0-9-]+)',\s*'([^']+)',\s*'[^']*',\s*$", lines[i + 1])
        if not m:
            continue
        slug, name = m.group(1), m.group(2)
        category = None
        for j in range(i + 1, min(i + 40, len(lines))):
            cm = re.search(r"category WHERE slug = '([a-z-]+)'", lines[j])
            if cm:
                category = cm.group(1)
                break
            if lines[j].strip() in ("),", ");"):
                break
        if category:
            rows.append((slug, name, category))
    return rows


# ------------------------------------------------------------------ 场景绘制
# 每个场景函数返回写在地面以上的 SVG 片段, 全部画在 y ∈ [SCENE_TOP, GROUND_Y] 内。
# 参数 r 是 rand01(slug), 用来在同一分类里做出差异。

def _ridge(r, base_y: float, color: str, peaks: int, height: float, seed_i: int, opacity=None):
    """锯齿状山脊线: 从左到右折返, 最后落到画布底部形成一个闭合多边形。"""
    step = (W + 80) / peaks
    points = [(-40.0, float(H))]
    x = -40.0
    for k in range(peaks + 1):
        peak_h = height * (0.55 + 0.45 * r(seed_i + k * 3))
        points.append((x + step / 2, base_y - peak_h))
        x += step
        points.append((x, base_y - peak_h * 0.2))
    points.append((W + 40.0, float(H)))
    pts = " ".join("%s,%s" % (f(px), f(py)) for px, py in points)
    extra = ' opacity="%s"' % opacity if opacity else ""
    return f'<polygon points="{pts}" fill="{color}"{extra}/>'


def scene_nature(r, c):
    sun_x = 330 + 540 * r(1)
    sun_y = 430 + 32 * r(2)
    out = [f'<circle cx="{f(sun_x)}" cy="{f(sun_y)}" r="{f(40 + 12 * r(3))}" fill="{c[5]}" opacity="0.88"/>']
    out.append(_ridge(r, 566, c[2], 5, 150, 4))
    out.append(_ridge(r, 626, c[3], 4, 116, 11))
    out.append(f'<rect x="0" y="{GROUND_Y}" width="{W}" height="{H - GROUND_Y}" fill="{c[4]}"/>')
    out.append(_ridge(r, 700, c[4], 6, 96, 17, opacity="0.6"))
    out.append(f'<rect x="0" y="{GROUND_Y + 42}" width="{W}" height="3" fill="{c[5]}" opacity="0.28"/>')
    return "\n  ".join(out)


def scene_history(r, c):
    """城墙 + 门洞 + 两座墩台。"""
    wall_y = 528.0
    out = []
    merlon_w, gap = 48, 36
    x = 40.0
    while x < W - 40:
        out.append(f'<rect x="{f(x)}" y="{f(wall_y - 30)}" width="{merlon_w}" height="30" fill="{c[2]}"/>')
        x += merlon_w + gap
    out.append(f'<rect x="30" y="{f(wall_y)}" width="{W - 60}" height="{f(H - wall_y)}" fill="{c[2]}"/>')
    for tx in (110.0, W - 270.0):
        out.append(f'<rect x="{f(tx)}" y="436" width="160" height="{f(H - 436)}" fill="{c[3]}"/>')
        out.append(f'<rect x="{f(tx - 13)}" y="404" width="186" height="36" fill="{c[2]}"/>')
    # 门洞: 用近景色挖出来, 顶部做成拱
    arch_w = 200.0
    ax = W / 2 - arch_w / 2
    spring = wall_y + 96          # 起拱高度
    out.append(
        f'<path d="M{f(ax)},{H} L{f(ax)},{f(spring)} '
        f'A{f(arch_w / 2)},{f(arch_w / 2)} 0 0 1 {f(ax + arch_w)},{f(spring)} '
        f'L{f(ax + arch_w)},{H} Z" fill="{c[4]}"/>'
    )
    out.append(f'<rect x="0" y="{f(wall_y - 5)}" width="{W}" height="7" fill="{c[5]}" opacity="0.45"/>')
    return "\n  ".join(out)


def scene_museum(r, c):
    """柱廊: 台基 + 立柱 + 檐口 + 山花。"""
    base_y, col_top = 636.0, 492.0
    out = [f'<rect x="110" y="{f(base_y)}" width="{W - 220}" height="{f(H - base_y)}" fill="{c[4]}"/>']
    out.append(f'<rect x="80" y="{f(base_y - 24)}" width="{W - 160}" height="24" fill="{c[3]}"/>')
    columns = 7
    span = (W - 340) / (columns - 1)
    for k in range(columns):
        cx = 170.0 + span * k
        out.append(f'<rect x="{f(cx - 21)}" y="{f(col_top)}" width="42" height="{f(base_y - 24 - col_top)}" fill="{c[2]}"/>')
        out.append(f'<rect x="{f(cx - 29)}" y="{f(col_top)}" width="58" height="16" fill="{c[3]}"/>')
    out.append(f'<rect x="110" y="426" width="{W - 220}" height="46" fill="{c[3]}"/>')
    out.append(f'<polygon points="{f(W / 2 - 290)},426 {f(W / 2)},382 {f(W / 2 + 290)},426" fill="{c[2]}"/>')
    return "\n  ".join(out)


def scene_landmark(r, c):
    """天际线 + 一座带球体的高塔。"""
    out = []
    x = -20.0
    k = 0
    while x < W:
        bw = 74 + 92 * r(k * 3 + 3)
        bh = 84 + 200 * r(k * 5 + 9)
        out.append(f'<rect x="{f(x)}" y="{f(GROUND_Y - bh)}" width="{f(bw)}" height="{f(bh)}" fill="{c[3]}"/>')
        rows = int(bh // 58)
        for row in range(rows):
            if r(k * 7 + row * 5) > 0.55:
                out.append(
                    f'<rect x="{f(x + 14)}" y="{f(GROUND_Y - bh + 16 + row * 58)}" width="{f(max(10, bw - 28))}" '
                    f'height="9" fill="{c[5]}" opacity="0.3"/>'
                )
        x += bw + 26
        k += 1
    tower_x = 560 + 200 * (r(2) - 0.5)
    out.append(f'<rect x="{f(tower_x - 15)}" y="442" width="30" height="{f(GROUND_Y - 442)}" fill="{c[2]}"/>')
    out.append(f'<circle cx="{f(tower_x)}" cy="442" r="40" fill="{c[2]}"/>')
    out.append(f'<circle cx="{f(tower_x)}" cy="442" r="40" fill="{c[5]}" opacity="0.22"/>')
    out.append(f'<rect x="{f(tower_x - 3)}" y="376" width="6" height="30" fill="{c[2]}"/>')
    return "\n  ".join(out)


def scene_religion(r, c):
    """楼阁式塔: 收分的塔身 + 每层一圈飞檐 + 塔刹。"""
    out = []
    tiers = 5
    body_h, step = 34.0, 52.0
    y = GROUND_Y
    for k in range(tiers):
        bw = 124.0 - k * 16
        out.append(f'<rect x="{f(W / 2 - bw / 2)}" y="{f(y - body_h)}" width="{f(bw)}" height="{f(body_h)}" fill="{c[3]}"/>')
        eave = bw + 132.0
        out.append(
            f'<polygon points="{f(W / 2 - eave / 2)},{f(y - body_h)} {f(W / 2)},{f(y - body_h - 26)} '
            f'{f(W / 2 + eave / 2)},{f(y - body_h)}" fill="{c[2]}"/>'
        )
        out.append(f'<rect x="{f(W / 2 - bw / 2 - 9)}" y="{f(y - body_h - 6)}" width="{f(bw + 18)}" height="7" fill="{c[2]}"/>')
        y -= step
    out.append(f'<rect x="{f(W / 2 - 4)}" y="{f(y - 30)}" width="8" height="34" fill="{c[5]}"/>')
    out.append(f'<circle cx="{f(W / 2)}" cy="{f(y - 40)}" r="10" fill="{c[5]}"/>')
    return "\n  ".join(out)


def scene_ancient_town(r, c):
    """马头墙屋顶 + 水面 + 两条乌篷船。"""
    out = []
    water_y = 604.0
    x = -30.0
    k = 0
    while x < W:
        hw = 150 + 56 * r(k * 3 + 2)
        top = water_y - 96 - 58 * r(k * 5 + 5)
        out.append(f'<rect x="{f(x)}" y="{f(top)}" width="{f(hw)}" height="{f(water_y - top)}" fill="{c[3]}"/>')
        out.append(
            f'<polygon points="{f(x - 16)},{f(top)} {f(x + hw / 2)},{f(top - 50)} {f(x + hw + 16)},{f(top)}" fill="{c[2]}"/>'
        )
        # 两侧阶梯状的马头墙
        for s in range(3):
            sw = 34 - s * 6
            out.append(f'<rect x="{f(x - 12)}" y="{f(top - 24 - s * 24)}" width="{f(sw)}" height="24" fill="{c[2]}"/>')
        x += hw + 30
        k += 1
    out.append(f'<rect x="0" y="{f(water_y)}" width="{W}" height="{f(H - water_y)}" fill="{c[4]}"/>')
    for bx, sc in ((320.0, 1.0), (880.0, 0.82)):
        y0 = water_y + 34
        w0 = 118 * sc
        out.append(f'<path d="M{f(bx - w0)},{f(y0)} Q{f(bx)},{f(y0 + 26 * sc)} {f(bx + w0)},{f(y0)} Z" fill="{c[2]}"/>')
        out.append(f'<path d="M{f(bx - 44 * sc)},{f(y0 - 3)} Q{f(bx)},{f(y0 - 42 * sc)} {f(bx + 44 * sc)},{f(y0 - 3)} Z" fill="{c[3]}"/>')
    out.append(f'<rect x="0" y="{f(water_y + 96)}" width="{W}" height="3" fill="{c[5]}" opacity="0.22"/>')
    return "\n  ".join(out)


def scene_theme_park(r, c):
    """摩天轮 + 帐篷 + 旗子。"""
    out = []
    cx, cy, rad = 380 + 120 * r(1), 500.0, 138.0
    out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(rad)}" fill="none" stroke="{c[2]}" stroke-width="15"/>')
    for k in range(12):
        a = k * math.pi / 6
        x2, y2 = cx + rad * math.cos(a), cy + rad * math.sin(a)
        out.append(f'<line x1="{f(cx)}" y1="{f(cy)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{c[3]}" stroke-width="5"/>')
        out.append(f'<circle cx="{f(x2)}" cy="{f(y2)}" r="17" fill="{c[5]}" opacity="0.85"/>')
    out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="22" fill="{c[5]}"/>')
    out.append(f'<polygon points="{f(cx - 64)},{f(GROUND_Y)} {f(cx)},{f(cy)} {f(cx + 64)},{f(GROUND_Y)}" fill="{c[3]}"/>')
    for k, tx in enumerate((830.0, 1010.0)):
        th = 128 + 46 * r(k + 4)
        out.append(f'<polygon points="{f(tx - 104)},{f(GROUND_Y)} {f(tx)},{f(GROUND_Y - th)} {f(tx + 104)},{f(GROUND_Y)}" fill="{c[2]}"/>')
        out.append(f'<rect x="{f(tx - 104)}" y="{f(GROUND_Y - 12)}" width="208" height="12" fill="{c[3]}"/>')
    out.append(f'<rect x="1122" y="376" width="7" height="{f(GROUND_Y - 376)}" fill="{c[3]}"/>')
    out.append(f'<polygon points="1129,384 1196,412 1129,440" fill="{c[5]}"/>')
    return "\n  ".join(out)


SCENES = {
    "nature": scene_nature,
    "history": scene_history,
    "museum": scene_museum,
    "landmark": scene_landmark,
    "religion": scene_religion,
    "ancient-town": scene_ancient_town,
    "theme-park": scene_theme_park,
}


def build_svg(slug: str, name: str, category: str) -> str:
    r = rand01(slug)
    hue = (r(0) - 0.5) * 0.09          # 色相偏移 ±16 度左右
    sat = 0.9 + 0.25 * r(31)
    c = [shift(rgb, hue, sat) for rgb in PALETTES[category]]
    label = CATEGORY_LABELS[category]

    # 标题字号按字数收敛: 最长的名字 9 个字, 也留在面板宽 880 以内
    title_size = min(84, int(840 / max(1, len(name))))
    scene = SCENES[category](r, c)
    px, py, pw, ph = PANEL

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{name}">
  <title>{name}</title>
  <desc>自绘示意图, 不代表实景</desc>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{c[0]}"/>
      <stop offset="1" stop-color="{c[1]}"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#sky)"/>
  {scene}
  <g>
    <rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="24" fill="#000000" opacity="0.38"/>
    <text x="{W // 2}" y="{py + 46}" text-anchor="middle" font-family="{FONT_STACK}" font-size="27"
          fill="{c[5]}" letter-spacing="7">{label}</text>
    <text x="{W // 2}" y="{py + 112}" text-anchor="middle" font-family="{FONT_STACK}" font-size="{title_size}"
          font-weight="700" fill="#f4f5f7">{name}</text>
    <text x="{W // 2}" y="{py + 160}" text-anchor="middle" font-family="{FONT_STACK}" font-size="21"
          fill="#a7adb8" letter-spacing="2">自绘示意图 · 不代表实景</text>
  </g>
</svg>
'''


def build_images_sql(rows) -> str:
    values = ",\n".join(
        "    ((SELECT id FROM attraction WHERE slug = '%s'), '%s', '%s', '%s', '%s', 0)"
        % (slug, URL_TEMPLATE.format(slug=slug), CAPTION, CREDIT, LICENSE)
        for slug, _name, _category in rows
    )
    return f'''-- Have-A-Trip · 景点配图的种子数据
--
-- 本文件由 scripts/make_attraction_covers.py 生成, **不要手改**。
-- 改图或加景点请改那个脚本再重跑, 否则 CI 的 --check 会拦下来。
--
-- 封面是自绘的 SVG, 出处就是仓库里的脚本本身, 许可与仓库一致(MIT)。
-- 为什么不用第三方照片: 见 docs/LICENSE-AUDIT.md 第五节。
--
-- 幂等: 用 upsert, 重跑会把 caption / credit / license 同步成本文件的版本。
--
-- 执行:
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/images.sql

BEGIN;

INSERT INTO attraction_image (attraction_id, url, caption, credit, license, sort) VALUES
{values}
ON CONFLICT (attraction_id, url) DO UPDATE SET
    caption = EXCLUDED.caption,
    credit  = EXCLUDED.credit,
    license = EXCLUDED.license,
    sort    = EXCLUDED.sort;

COMMIT;
'''


def main() -> int:
    seed_text = io.open(SEED_PATH, encoding="utf-8").read()
    rows = parse_attractions(seed_text)
    if not rows:
        print("没有从 db/seed/seed.sql 里解析出任何景点, 先检查文件格式")
        return 1

    files = {slug: build_svg(slug, name, category) for slug, name, category in rows}
    sql = build_images_sql(rows)

    if "--check" in sys.argv[1:]:
        problems = []
        for slug, content in sorted(files.items()):
            path = COVER_DIR / f"{slug}.svg"
            if not path.exists():
                problems.append(f"缺失 {path.relative_to(REPO_ROOT)}")
            elif io.open(path, encoding="utf-8", newline="").read() != content:
                problems.append(f"内容不一致 {path.relative_to(REPO_ROOT)}")
        if not IMAGES_SQL_PATH.exists():
            problems.append(f"缺失 {IMAGES_SQL_PATH.relative_to(REPO_ROOT)}")
        elif io.open(IMAGES_SQL_PATH, encoding="utf-8", newline="").read() != sql:
            problems.append(f"内容不一致 {IMAGES_SQL_PATH.relative_to(REPO_ROOT)}")
        # 反向检查: 景点被删了但图还留着, 属于孤儿文件
        if COVER_DIR.exists():
            known = {f"{slug}.svg" for slug in files}
            for path in sorted(COVER_DIR.glob("*.svg")):
                if path.name not in known:
                    problems.append(f"多余文件 {path.relative_to(REPO_ROOT)}")
        if problems:
            print("封面与脚本不一致:")
            for p in problems:
                print("  -", p)
            print("跑 `python scripts/make_attraction_covers.py` 重新生成。")
            return 1
        print(f"一致: {len(files)} 张封面 + {IMAGES_SQL_PATH.relative_to(REPO_ROOT)}")
        return 0

    COVER_DIR.mkdir(parents=True, exist_ok=True)
    for slug, content in files.items():
        io.open(COVER_DIR / f"{slug}.svg", "w", encoding="utf-8", newline="\n").write(content)
    io.open(IMAGES_SQL_PATH, "w", encoding="utf-8", newline="\n").write(sql)
    total = sum(len(c.encode("utf-8")) for c in files.values())
    print(f"已写入 {len(files)} 张封面到 {COVER_DIR.relative_to(REPO_ROOT)} (合计 {total / 1024:.1f} KB)")
    print(f"已写入 {IMAGES_SQL_PATH.relative_to(REPO_ROOT)} ({len(sql.encode('utf-8'))} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())