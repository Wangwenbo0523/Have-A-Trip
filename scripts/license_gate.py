#!/usr/bin/env python3
"""许可证卡口: 禁止 copyleft 进入本项目, 保住「将来可闭源」的退路。

检查三件事:
  1. 本机 Python 环境的依赖许可证
  2. frontend/package-lock.json 里 npm 依赖的许可证
  3. 基底的 LICENSE 文件是否仍在, 且与 bases.lock.json 声明一致

用法:
    python scripts/license_gate.py            # 违禁项报错, 未知项告警
    python scripts/license_gate.py --strict   # 未知项也报错
退出码: 0 通过, 1 未通过
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 违禁: 传染性 copyleft 或非商用条款 —— 一旦引入, 将来无法闭源
BANNED_PATTERNS = [
    (r"\bAGPL", "AGPL: 提供网络服务也触发开源义务, 对本项目是致命的"),
    (r"(?<!L)\bGPL", "GPL: 衍生作品必须同样开源"),
    (r"\bSSPL", "SSPL: 非 OSI 认可, 商用受限"),
    (r"CC-BY-NC", "CC-BY-NC: 禁止商用"),
    (r"\bBUSL|Business Source", "BUSL: 商用受限"),
]
# 告警: 弱 copyleft, 需人工判断
WARN_PATTERNS = [
    (r"\bLGPL", "LGPL: 动态链接通常可用, 静态链接需评估"),
    (r"\bMPL", "MPL: 文件级 copyleft, 修改过的文件需开源"),
    (r"\bEPL", "EPL: 弱 copyleft"),
    (r"CC-BY-SA", "CC-BY-SA: 相同方式共享, 数据与内容层要特别注意"),
    (r"\bODBL\b", "ODbL: 数据库层面的相同方式共享义务(OSM 即此)"),
]
# 宽松许可白名单: 明确允许, 避免被误报为「未知」
ALLOW_PATTERNS = [
    r"\bMIT\b", r"\bAPACHE", r"\bBSD\b", r"\bISC\b", r"\bZLIB\b",
    r"\bUNLICENSE\b", r"0BSD", r"PYTHON-2\.0", r"\bPSF\b",
    r"PUBLIC DOMAIN", r"\bCC0\b", r"MULANPSL", r"WTFPL",
]

ROOT = Path(__file__).resolve().parent.parent

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def classify(text: str) -> tuple[str, str] | None:
    """返回 (级别, 说明)。级别为 BANNED 或 WARN; 没问题返回 None。"""
    upper = text.upper()
    for pattern in ALLOW_PATTERNS:
        if re.search(pattern, upper):
            return None
    for pattern, why in BANNED_PATTERNS:
        if re.search(pattern, upper):
            return "BANNED", why
    for pattern, why in WARN_PATTERNS:
        if re.search(pattern, upper):
            return "WARN", why
    return None


def python_licenses() -> list[tuple[str, str, str]]:
    """扫描当前 Python 环境。返回 (包名, 版本, 许可证文本)。"""
    try:
        from importlib.metadata import distributions
    except ImportError:
        return []
    out = []
    for dist in distributions():
        meta = dist.metadata
        name = meta.get("Name") or "?"
        version = meta.get("Version") or "?"
        # PEP 639 起许可证写在 License-Expression, 旧的 License 字段已废弃
        parts = [meta.get("License-Expression") or "", meta.get("License") or ""]
        parts += [
            c.split("::")[-1].strip()
            for c in (meta.get_all("Classifier") or [])
            if c.startswith("License ::")
        ]
        out.append((name, version, " / ".join(p for p in parts if p)))
    return out


def npm_licenses() -> list[tuple[str, str, str]]:
    """解析 frontend/package-lock.json。"""
    lock = ROOT / "frontend" / "package-lock.json"
    if not lock.exists():
        return []
    data = json.loads(lock.read_text(encoding="utf-8-sig"))
    out = []
    for path, info in (data.get("packages") or {}).items():
        if not path or "node_modules" not in path:
            continue
        name = path.split("node_modules/")[-1]
        lic = info.get("license") or ""
        if isinstance(lic, list):
            lic = " / ".join(str(x) for x in lic)
        out.append((name, info.get("version") or "?", str(lic)))
    return out


def check_bases() -> list[str]:
    """确认基底的 LICENSE 还在, 且与 bases.lock.json 声明一致。"""
    problems = []
    lock_path = ROOT / "scripts" / "bases.lock.json"
    if not lock_path.exists():
        return ["缺少 scripts/bases.lock.json"]
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return [f"bases.lock.json 解析失败: {exc}"]
    bases = lock.get("bases", {})
    if "frontend" in bases:
        candidates = sorted(ROOT.glob("frontend/LICENSE*"))
        if not candidates:
            problems.append("基底 frontend: LICENSE 丢失(MIT 要求保留版权声明)")
        else:
            head = candidates[0].read_text(encoding="utf-8", errors="ignore")[:200].upper()
            if "MIT" not in head:
                problems.append("基底 frontend: LICENSE 不是 MIT, 与 bases.lock.json 声明不符")
    return problems


def main() -> int:
    strict = "--strict" in sys.argv
    banned: list[str] = []
    warned: list[str] = []
    unknown: list[str] = []

    for label, rows in (("python", python_licenses()), ("npm", npm_licenses())):
        for name, version, lic in rows:
            verdict = classify(lic)
            if verdict is None:
                if not lic.strip() or lic.strip().upper() in {"UNKNOWN", "NONE", "N/A"}:
                    unknown.append(f"[{label}] {name}@{version}")
                continue
            level, why = verdict
            entry = f"[{label}] {name}@{version}  <-- {lic.strip()[:80]}  ({why})"
            (banned if level == "BANNED" else warned).append(entry)

    problems = check_bases()

    print("=" * 68)
    print("许可证卡口 · 目标: 保住「将来可闭源」的退路")
    print("=" * 68)

    if banned:
        print(f"\n[违禁] {len(banned)} 项, 必须移除后才能合并:\n")
        for line in banned:
            print("  x " + line)
    if problems:
        print(f"\n[基底] {len(problems)} 项问题:\n")
        for line in problems:
            print("  ! " + line)
    if warned:
        print(f"\n[告警] 弱 copyleft / 相似许可 {len(warned)} 项, 需人工确认:\n")
        for line in warned:
            print("  ? " + line)
    if unknown:
        suffix = "(strict 下计为失败):" if strict else "(不阻塞):"
        print(f"\n[未知] {len(unknown)} 项未标注许可证{suffix}\n")
        for line in unknown[:15]:
            print("  . " + line)
        if len(unknown) > 15:
            print(f"  ... 另有 {len(unknown) - 15} 项")

    failed = bool(banned) or bool(problems) or (strict and bool(unknown))
    print("\n" + ("结果: 未通过" if failed else "结果: 通过"))
    if not failed:
        print("提示: 代码层干净。数据层许可(OSM=ODbL, CC BY-SA 有相同方式共享义务)需单独审。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())