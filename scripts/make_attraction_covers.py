#!/usr/bin/env python3
"""为每个景点生成一张自绘封面图, 并产出配图的种子 SQL。

为什么自绘: 图片和代码一样是版权资产, 但更难查。原计划用 CC0 / 公有领域的图库,
实测 Wikimedia Commons 与 Openverse 在本机网络下不可达(连接超时), 而 Unsplash /
Pixabay 一类可访问的图库用的是各自的专有许可(不是 CC0), 且对中国具体景点的覆盖很薄。
与其塞一批出处含糊的照片, 不如**自己画** —— 这才是下面这段的由来。

v4.5 起本机可以经代理出去, 于是补了一批 Commons 实景照片(由 scripts/fetch_commons_photos.py
抓, 台账 db/seed/photos.json, 许可只收 PD / CC0 / CC BY / CC BY-SA), 所以现在是两种并存:
照片优先, 没有照片的景点仍画 SVG 兜底。

产出两个东西:
  1. frontend/public/images/covers/<slug>.svg   每个景点一张, 按 slug 确定性生成
  2. db/seed/images.sql                         每个景点一条 attraction_image 的幂等种子

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
# 景点 INSERT 分散在两个种子文件里: seed.sql 是逐条审过的自采档案,
# attractions_cn.sql 是脚本生成的名录条目。两个都要覆盖 —— 列表页的卡片
# 都以 sort = 0 的封面作首图, 漏掉一个文件就等于一批景点没有图。
SEED_PATHS = (
    REPO_ROOT / "db" / "seed" / "seed.sql",
    REPO_ROOT / "db" / "seed" / "attractions_cn.sql",
)
IMAGES_SQL_PATH = REPO_ROOT / "db" / "seed" / "images.sql"
# 抓自 Wikimedia Commons 的实景照片清单(可选)。没有它就跑成纯自绘 SVG 的老样子。
PHOTOS_JSON_PATH = REPO_ROOT / "db" / "seed" / "photos.json"
# 实拍照片的站内路径 = 前缀 + **台账里记的真实文件名**。
# 不用 `{slug}.jpg` 拼: fetch 那边是故意保留原图真实后缀的(.jpg / .jpeg / .png,
# 见 fetch_commons_photos.py 里「缩略图地址的后缀就是真实格式」那段), 台账记的也是
# 真实文件名。曾经这里写死 .jpg, 于是 199 张里唯一那张 .jpeg(珠海市圆明新园)指着
# 一个不存在的文件 —— 而 web.py 对找不到的静态路径会回落 SPA 外壳, 浏览器拿到的
# 是一段 HTML, 连 404 都看不到, 表现就是裂图。
PHOTO_URL_PREFIX = "/images/covers/"
PHOTO_CREDIT_FALLBACK = "Wikimedia Commons 用户"
# 一行 attraction_image: (景点, 站内路径, 标题, 署名, 许可, 来源页, 排序)。
# source_url 自己带引号或 NULL, 所以模板里这一位不加引号。
ROW_TEMPLATE = "    ((SELECT id FROM attraction WHERE slug = '%s'), '%s', '%s', '%s', '%s', %s, 0)"
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
    "palace": [
        (0x22, 0x1C, 0x2C), (0x5E, 0x47, 0x3A), (0x8C, 0x6B, 0x49),
        (0x6A, 0x4E, 0x35), (0x38, 0x29, 0x1D), (0xE8, 0xC0, 0x6A),
    ],
    "archaeology": [
        (0x1A, 0x21, 0x29), (0x4E, 0x53, 0x43), (0x71, 0x65, 0x49),
        (0x55, 0x4B, 0x36), (0x2F, 0x29, 0x1F), (0xE0, 0xA8, 0x4E),
    ],
    # 名录条目共用的分类。它们的主题在官方名录里没有, 所以不套用上面任何一套配色,
    # 单独给一套偏绿的, 与 "nature" 的青蓝区分开。
    "scenic-area": [
        (0x1A, 0x28, 0x22), (0x3F, 0x5E, 0x46), (0x2E, 0x47, 0x36),
        (0x20, 0x33, 0x28), (0x14, 0x22, 0x1B), (0xE0, 0xB4, 0x52),
    ],
}

CATEGORY_LABELS = {
    "nature": "自然风光", "history": "历史古迹", "museum": "博物馆",
    "landmark": "城市地标", "religion": "宗教场所",
    "ancient-town": "古镇村落", "theme-park": "主题乐园",
    "palace": "宫殿城堡", "archaeology": "考古遗址",
    "scenic-area": "A 级景区",
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
    """从种子 SQL 里抽出 (slug, name, name_en, category)。

    只认「单独一行左括号, 下一行是 'slug', '名称', 英文名(或 NULL),」的固定写法:
    比整份 SQL 解析可靠得多, 而且不用连数据库(所以 --check 在 CI 里也能裸跑)。
    两个种子文件(seed.sql / attractions_cn.sql)都走这一套写法, 所以都由它覆盖。

    返回 (rows, skipped)。**认出来的条目一律不许悄悄丢掉**: 形状对得上就说明它是一个
    景点元组, 此时取不到分类要记账 —— 被丢掉的后果是「这个景点没有封面」, 而封面缺失
    在界面上只表现为一张空白首图, 不报任何错, 是最难回头发现的一类回归。
    (v4.2 就吃过一次同类的亏: 旧正则遇到名字里的转义单引号 `''` 会把整行漏掉。)
    """
    rows = []
    skipped = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() != "(" or i + 1 >= len(lines):
            continue
        # 第三列是 name_en: 自采档案写英文名, 名录条目一律 NULL, 两种都要认。
        # 名字里的单引号在 SQL 里写成两个(''), 这里按同样的规则认回来并还原
        # (库里的值就是还原后的, 图上的标题必须跟库里一致)。
        m = re.match(
            r"^\s*'([a-z0-9-]+)',\s*'((?:[^']|'')+)',\s*(?:'((?:[^']|'')*)'|NULL),\s*$",
            lines[i + 1],
        )
        if not m:
            continue
        slug = m.group(1)
        name = m.group(2).replace("''", "'")
        # 第三列 name_en: 名录条目一律 NULL, 自采档案有英文名。抓图那个脚本要拿它当
        # 匹配关键词(中文名在文件名里常被翻成英文), 所以在解析这一步就留下。
        name_en = (m.group(3) or "").replace("''", "'")
        category = None
        for j in range(i + 1, min(i + 40, len(lines))):
            cm = re.search(r"category WHERE slug = '([a-z-]+)'", lines[j])
            if cm:
                category = cm.group(1)
                break
            if lines[j].strip() in ("),", ");"):
                break
        if category:
            rows.append((slug, name, name_en, category))
        else:
            skipped.append((slug, i + 2))
    return rows, skipped


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


def scene_palace(r, c):
    """宫殿城堡: 台基 + 两翼 + 中央主殿带穹顶 + 窗列 + 台阶。

    整组建筑压在 y 380 以下 —— 上面的标题面板是 162~350, 越过就会被挡住。
    """
    dome_apex, dome_base = 380.0, 474.0
    block_top, base_top = 550.0, 620.0
    out = [f'<rect x="70" y="{f(base_top)}" width="{W - 140}" height="22" fill="{c[3]}"/>']
    out.append(f'<rect x="104" y="{f(base_top + 22)}" width="{W - 208}" height="{f(H - base_top - 22)}" fill="{c[4]}"/>')
    # 两翼
    for x0, w in ((172.0, 250.0), (778.0, 250.0)):
        out.append(f'<rect x="{f(x0)}" y="556" width="{f(w)}" height="{f(base_top - 556)}" fill="{c[2]}"/>')
        out.append(f'<polygon points="{f(x0 - 20)},556 {f(x0 + w / 2)},502 {f(x0 + w + 20)},556" fill="{c[3]}"/>')
        for k in range(3):
            wx = x0 + 34 + k * 86
            out.append(f'<rect x="{f(wx)}" y="568" width="40" height="44" rx="19" fill="{c[4]}" opacity="0.75"/>')
    # 中央主殿
    out.append(f'<rect x="424" y="{f(block_top)}" width="352" height="{f(base_top - block_top)}" fill="{c[2]}"/>')
    for k in range(3):
        wx = 470 + k * 96
        out.append(f'<rect x="{f(wx)}" y="562" width="52" height="46" rx="21" fill="{c[4]}" opacity="0.7"/>')
    out.append(f'<rect x="462" y="{f(dome_base)}" width="276" height="{f(block_top - dome_base)}" fill="{c[3]}"/>')
    out.append(f'<path d="M506,{f(dome_base)} A94,94 0 0 1 694,{f(dome_base)} Z" fill="{c[2]}"/>')
    out.append(f'<rect x="{f(W / 2 - 20)}" y="{f(dome_apex + 16)}" width="40" height="12" fill="{c[5]}" opacity="0.8"/>')
    # 台阶
    for k in range(3):
        out.append(f'<rect x="{f(500 - k * 34)}" y="{f(base_top + 22 + k * 15)}" width="{f(200 + k * 68)}" height="15" fill="{c[4]}" opacity="0.85"/>')
    out.append(f'<rect x="0" y="{f(base_top)}" width="{W}" height="4" fill="{c[5]}" opacity="0.4"/>')
    return "\n  ".join(out)


def scene_ruins(r, c):
    """考古遗址: 阶梯台 + 残柱 + 断梁。"""
    out = []
    # 左侧: 阶梯台
    base_y = 656.0
    tiers = 5
    for k in range(tiers):
        tw = 430 - k * 68
        ty = base_y - (k + 1) * 46
        out.append(f'<rect x="{f(196 + k * 34)}" y="{f(ty)}" width="{f(tw)}" height="46" fill="{c[3] if k % 2 else c[2]}"/>')
    out.append(f'<rect x="{f(196 + (tiers - 1) * 34 + 12)}" y="{f(base_y - tiers * 46 - 34)}" width="74" height="34" fill="{c[4]}" opacity="0.9"/>')
    # 右侧: 残柱, 高度不一, 其中两根顶着一段残梁
    tops = []
    for k, cx in enumerate((760.0, 866.0, 972.0, 1078.0)):
        col_h = 150 + 96 * r(k + 6)
        top = base_y - col_h
        tops.append(top)
        out.append(f'<rect x="{f(cx - 27)}" y="{f(top)}" width="54" height="{f(col_h)}" fill="{c[2]}"/>')
        out.append(f'<rect x="{f(cx - 36)}" y="{f(top)}" width="72" height="17" fill="{c[3]}"/>')
        out.append(f'<rect x="{f(cx - 36)}" y="{f(base_y - 17)}" width="72" height="17" fill="{c[3]}"/>')
    out.append(f'<rect x="733" y="{f(tops[0] - 26)}" width="160" height="26" fill="{c[3]}" opacity="0.92"/>')
    out.append(f'<rect x="939" y="{f(tops[2] - 26)}" width="160" height="26" fill="{c[3]}" opacity="0.92"/>')
    # 地面与散落石块
    out.append(f'<rect x="0" y="{f(base_y)}" width="{W}" height="{f(H - base_y)}" fill="{c[4]}"/>')
    for k in range(5):
        bx = 120 + 210 * k + 60 * r(k + 21)
        out.append(f'<rect x="{f(bx)}" y="{f(base_y - 20 - 8 * r(k + 31))}" width="{f(30 + 40 * r(k + 41))}" height="20" rx="5" fill="{c[3]}" opacity="0.7"/>')
    out.append(f'<rect x="0" y="{f(base_y - 3)}" width="{W}" height="3" fill="{c[5]}" opacity="0.25"/>')
    return "\n  ".join(out)


SCENES = {
    "nature": scene_nature,
    "history": scene_history,
    "museum": scene_museum,
    "landmark": scene_landmark,
    "religion": scene_religion,
    "ancient-town": scene_ancient_town,
    "theme-park": scene_theme_park,
    "palace": scene_palace,
    "archaeology": scene_ruins,
    "scenic-area": scene_nature,
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


def one_line(text: str) -> str:
    """把值里的换行与连续空白压成单个空格。

    Commons 的 Artist 字段经常自带换行(「原始上传者是谁」另起一行): 直接写进 SQL, 一条
    INSERT 就会断成三行 —— 语句本身仍然合法, 但本文件是按「一行一条」看的, 断行既难看,
    又会被 git diff --check 这类行级检查挑出来(行尾挂一个孤零零的空格)。
    """
    return re.sub(r"\s+", " ", text or "").strip()


def sql_quote(text: str) -> str:
    """SQL 字符串字面量: 先压成一行, 再把单引号写成两个。"""
    return one_line(text).replace("'", "''")


def sql_text(value) -> str:
    """可空文本字面量: 空值写 NULL, 不写空串。

    「这张图没有外部来源」和「来源是空字符串」在声明页上不是一回事, 所以不合并。
    """
    text = one_line(value or "")
    return "NULL" if not text else "'%s'" % text.replace("'", "''")


def load_photos() -> dict:
    """读 db/seed/photos.json: 抓自 Wikimedia Commons 的实景照片。

    条目形如 {slug, seq, photo, license, artist, source, ...}。
    许可为空的直接丢掉 —— attraction_image.license 是 NOT NULL, 宁可用自绘。
    """
    import json

    if not PHOTOS_JSON_PATH.exists():
        return {}
    out = {}
    for item in json.loads(io.open(PHOTOS_JSON_PATH, encoding="utf-8").read()):
        slug, photo, lic = item.get("slug"), item.get("photo"), (item.get("license") or "").strip()
        if not slug or not photo or not lic:
            continue
        item["credit"] = (item.get("artist") or "").strip() or PHOTO_CREDIT_FALLBACK
        out[slug] = item
    return out


def photo_caption(item: dict) -> str:
    """标题里带编号, 方便对着编号清单逐张核对。"""
    name = (item.get("file") or item.get("photo") or "").replace("File:", "")
    return "#%03d · %s" % (item.get("pid") or item.get("seq") or 0, name)


def build_images_sql(rows, photos) -> str:
    entries = []
    for slug, _name, _name_en, _category in rows:
        item = photos.get(slug)
        if item:
            entries.append(ROW_TEMPLATE % (
                slug, PHOTO_URL_PREFIX + item["photo"], sql_quote(photo_caption(item)),
                sql_quote(item["credit"]), sql_quote(item["license"]),
                # 来源页指向 Commons 的文件页 —— CC BY / CC BY-SA 要求给出来源, 逐图署名靠它
                sql_text(item.get("source"))))
        else:
            entries.append(ROW_TEMPLATE % (
                slug, URL_TEMPLATE.format(slug=slug), sql_quote(CAPTION),
                sql_quote(CREDIT), sql_quote(LICENSE),
                # 自绘图没有外部来源, 写 NULL。它不是「来源缺失」, 而是「根本没有来源这回事」
                sql_text(None)))
    values = ",\n".join(entries)
    return f'''-- Have-A-Trip 景点配图的种子数据
--
-- 本文件由 scripts/make_attraction_covers.py 生成, **不要手改**。
-- 改图或加景点请改那个脚本再重跑, 否则 CI 的 --check 会拦下来。
--
-- 配图来源有两种:
--   1. 抓自 Wikimedia Commons 的实景照片, 清单在 db/seed/photos.json,
--      作者与许可逐张登记在 credit / license 里, url 用台账里的真实文件名
--      (/images/covers/<slug>.<后缀>, 后缀可能是 .jpg / .jpeg / .png),
--      source_url 指向 Commons 的文件页(逐图署名的依据, 见 docs/LICENSE-AUDIT.md 第三节);
--   2. 没有合适照片的景点, 退回仓库自绘的 SVG 示意图, 许可与仓库一致(MIT), source_url 为 NULL。
--
-- 幂等: 用 upsert, 重跑会把 caption / credit / license / source_url 同步成本文件的版本。
--
-- 执行:
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/images.sql

BEGIN;

-- 本文件是 /images/covers/ 这批封面图的唯一来源: 先清掉旧行再插。
-- 不清的话, 换图(比如某景点从自绘换成实景照片)会留下上一版的行,
-- 于是同一个景点有两行 sort = 0, cover_image 就成了碰运气。
DELETE FROM attraction_image WHERE url LIKE '/images/covers/%';

INSERT INTO attraction_image (attraction_id, url, caption, credit, license, source_url, sort) VALUES
{values}
ON CONFLICT (attraction_id, url) DO UPDATE SET
    caption    = EXCLUDED.caption,
    credit     = EXCLUDED.credit,
    license    = EXCLUDED.license,
    source_url = EXCLUDED.source_url,
    sort       = EXCLUDED.sort;

-- 列表页的封面取 sort = 0 的图。
UPDATE attraction a
SET cover_image = i.url
FROM attraction_image i
WHERE i.attraction_id = a.id
  AND i.sort = 0
  AND a.cover_image IS DISTINCT FROM i.url;

COMMIT;
'''


def main() -> int:
    rows = []
    problems = []
    for seed_path in SEED_PATHS:
        where = seed_path.relative_to(REPO_ROOT)
        parsed, skipped = parse_attractions(io.open(seed_path, encoding="utf-8").read())
        for slug, line_no in skipped:
            problems.append(f"{where}:{line_no} 认出了景点元组 {slug!r} 却找不到分类")
        rows.extend(parsed)
    # 重复的 slug 会被 files 这个 dict 静默吃掉(images.sql 也会对同一个 slug upsert
    # 两次), 与其等图对不上再回头找, 不如在这里就拦下。
    seen: dict[str, int] = {}
    for slug, *_ in rows:
        seen[slug] = seen.get(slug, 0) + 1
    problems += [f"slug 重复 {n} 次: {slug}" for slug, n in sorted(seen.items()) if n > 1]
    if problems:
        print("种子文件有问题, 先修好再生成:")
        for item in problems:
            print("  -", item)
        return 1
    if not rows:
        print("没有从 db/seed/ 的种子文件里解析出任何景点, 先检查文件格式")
        return 1

    photos = load_photos()
    files = {slug: build_svg(slug, name, category) for slug, name, _name_en, category in rows}
    sql = build_images_sql(rows, photos)

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
        for slug, item in sorted(photos.items()):
            path = COVER_DIR / item["photo"]
            if not path.exists():
                problems.append(f"缺失照片 {path.relative_to(REPO_ROOT)}")
        # 种子里的每个配图 URL 都得在磁盘上是同一个文件。这条盯的是**两处名字是否一致**:
        # 上面两个循环各查一半(台账→磁盘、SVG 内容), 合起来仍然可能指向一个不存在的文件 ——
        # URL 一度是拿 slug 拼死 .jpg 的, 台账记的却是真实后缀, 两边分别都对, 拼出来的
        # /images/covers/4a-guangdong-178.jpg 磁盘上没有(真文件是 .jpeg), 于是界面上裂图。
        # 只扫 INSERT 的值行: 上面那条 DELETE 里也有 '/images/covers/%', 不排除掉就会
        # 把通配符当文件名报一次假告警(写这条时就踩了)。后缀也要求是真后缀, 不吃 '%'。
        seeded = [l for l in sql.splitlines() if l.startswith("    ((SELECT id FROM attraction")]
        urls = sorted({
            u for line in seeded
            for u in re.findall(r"'(/images/covers/[^']*\.[A-Za-z0-9]+)'", line)
        })
        if len(urls) != len(files):
            problems.append(f"种子里的配图 URL 只认出 {len(urls)} 条, 应该有 {len(files)} 条")
        for url in urls:
            path = COVER_DIR / url.rsplit("/", 1)[-1]
            if not path.exists():
                problems.append(f"种子里的 {url} 在磁盘上不存在")
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
