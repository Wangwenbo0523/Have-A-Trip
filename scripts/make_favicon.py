#!/usr/bin/env python3
"""生成站点图标 frontend/public/favicon.ico —— 自绘, 不带任何第三方素材。

图标和代码一样是版权资产, 但更隐蔽: 代码有 lockfile 可以扫, 图标只能靠人记。
上游基底带的那两个占位图标出处无从查证, 所以这里改成**自己画**。脚本只用标准库,
不新增依赖; 改下面的常量再重跑就能换图, 图标因此是可复现的产物。

画面: 深色圆角方块 + 橙色太阳 + 两座山。刻意**不用地图针 / 定位符**, 与
「只做景点介绍, 不做地图与定位」的产品定位保持一致。

用法:
    python scripts/make_favicon.py            # 写入 frontend/public/favicon.ico
    python scripts/make_favicon.py --check    # 只校验现有文件与脚本产出是否一致
退出码: 0 成功或一致, 1 --check 发现不一致
"""
from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = REPO_ROOT / "frontend" / "public" / "favicon.ico"

# ICO 里塞这几档。256 是 ICO 格式的上限(目录项里用 0 表示 256)。
SIZES = (16, 24, 32, 48, 64, 128, 256)

# 采样倍率与目标边长成反比, 让每档都从约 512x512 的采样量降下来: 小图多采,
# 大图少采。既保证边缘抗锯齿, 又不至于让脚本跑上几十秒。
SUPERSAMPLE_TARGET = 512
MIN_SUPERSAMPLE = 2

# 配色直接取 frontend/src/index.css 里的变量, 图标与站点同色系
BG_COLOR = (0x14, 0x16, 0x1A)     # --page-bg
SUN_COLOR = (0xF4, 0x67, 0x32)    # --accent
FRONT_COLOR = (0xF4, 0xF5, 0xF7)  # --text
BACK_COLOR = (0xA7, 0xAD, 0xB8)   # --muted

# 以下都在归一化坐标(0..1)里描述
CORNER_RADIUS = 0.20
SUN_CENTER = (0.66, 0.33)
SUN_RADIUS = 0.135
# 两座山的底边刻意压到画布之外, 这样和圆角方块的下边缘自然齐平
TRI_BACK = ((0.30, 0.30), (-0.10, 0.94), (0.66, 0.94))
TRI_FRONT = ((0.64, 0.46), (0.28, 1.02), (1.06, 1.02))


def supersample(size: int) -> int:
    return max(MIN_SUPERSAMPLE, round(SUPERSAMPLE_TARGET / size))


def _in_rounded_square(u: float, v: float) -> bool:
    """圆角方块的符号距离场: 距离 <= 0 即在内部。"""
    half = 0.5
    qx = abs(u - half) - (half - CORNER_RADIUS)
    qy = abs(v - half) - (half - CORNER_RADIUS)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - CORNER_RADIUS <= 0.0


def _in_triangle(u: float, v: float, tri) -> bool:
    """叉积同号判定。顶点顺序无所谓, 所以只比较正负号是否混用。"""
    (x1, y1), (x2, y2), (x3, y3) = tri
    d1 = (u - x2) * (y1 - y2) - (x1 - x2) * (v - y2)
    d2 = (u - x3) * (y2 - y3) - (x2 - x3) * (v - y3)
    d3 = (u - x1) * (y3 - y1) - (x3 - x1) * (v - y1)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def _color_at(u: float, v: float):
    """归一化坐标处的颜色; 落在图形之外返回 None, 表示透明。

    判定顺序就是绘制顺序: 前山压后山, 山压太阳, 太阳压底色。
    """
    if not _in_rounded_square(u, v):
        return None
    if _in_triangle(u, v, TRI_FRONT):
        return FRONT_COLOR
    if _in_triangle(u, v, TRI_BACK):
        return BACK_COLOR
    if math.hypot(u - SUN_CENTER[0], v - SUN_CENTER[1]) <= SUN_RADIUS:
        return SUN_COLOR
    return BG_COLOR


def render_rgba(size: int) -> bytes:
    """渲染一档尺寸的 RGBA 字节流。逐像素超采样得到抗锯齿边缘。"""
    ss = supersample(size)
    step = 1.0 / (size * ss)
    total = ss * ss
    out = bytearray(size * size * 4)
    for py in range(size):
        for px in range(size):
            r = g = b = 0.0
            hits = 0
            for sy in range(ss):
                v = (py * ss + sy + 0.5) * step
                for sx in range(ss):
                    u = (px * ss + sx + 0.5) * step
                    color = _color_at(u, v)
                    if color is None:
                        continue
                    r += color[0]
                    g += color[1]
                    b += color[2]
                    hits += 1
            if hits == 0:
                continue
            offset = (py * size + px) * 4
            # 颜色只对「命中」的样本求平均。若把透明样本也算进来, 边缘会被黑色拖暗,
            # 在浅色浏览器界面上会看到一圈脏边。
            out[offset] = round(r / hits)
            out[offset + 1] = round(g / hits)
            out[offset + 2] = round(b / hits)
            out[offset + 3] = round(255 * hits / total)
    return bytes(out)


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def encode_png(size: int, rgba: bytes) -> bytes:
    """把 RGBA 编成 PNG。手写而不用 Pillow, 是为了画一个图标不额外引入依赖。"""
    stride = size * 4
    # 每行开头补一个 0, 即 PNG 的 filter type「不过滤」
    raw = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(size))
    # 位深 8, 颜色类型 6 = 真彩 + alpha
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )


def encode_ico(images) -> bytes:
    """把若干 PNG 组装成一个 ICO。

    目录项里直接内嵌 PNG 从 Vista 起就是合法写法, 现代浏览器全都认, 而且比
    BMP 条目小得多。
    """
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for size, png in images:
        dim = 0 if size >= 256 else size  # 目录项里 0 代表 256
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        payload += png
    return bytes(header + entries + payload)


def build() -> bytes:
    images = [(size, encode_png(size, render_rgba(size))) for size in SIZES]
    return encode_ico(images)


def main() -> int:
    icon = build()
    shown = ICON_PATH.relative_to(REPO_ROOT)

    if "--check" in sys.argv[1:]:
        if not ICON_PATH.exists():
            print(f"缺失: {shown}")
            return 1
        if ICON_PATH.read_bytes() != icon:
            print(f"不一致: {shown} 不是 scripts/make_favicon.py 的产出")
            print("跑 `python scripts/make_favicon.py` 重新生成。")
            return 1
        print(f"一致: {shown}")
        return 0

    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICON_PATH.write_bytes(icon)
    print(f"已写入 {shown}: {len(icon)} 字节, {len(SIZES)} 档尺寸 {list(SIZES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())