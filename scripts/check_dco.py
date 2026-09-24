# -*- coding: utf-8 -*-
"""DCO 校验: 每个 commit 都必须带 Signed-off-by。

用法:
    python scripts/check_dco.py                # 只查 HEAD
    python scripts/check_dco.py BASE..HEAD     # 查区间
"""
from __future__ import annotations

import re
import subprocess
import sys

# 与 git commit -s 生成的格式一致: 名字 <邮箱>
SIGNOFF = re.compile(r"^Signed-off-by: .+ <[^<>@\s]+@[^<>\s]+>\s*$", re.MULTILINE)

ZERO_SHA = "0" * 40


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {result.stderr.strip()}")
    return result.stdout


def commits(rev_range: str) -> list[tuple[str, str]]:
    """返回 [(short_sha, message)], 跳过 merge commit。"""
    raw = git("log", "--no-merges", "--format=%h%x1f%B%x1e", rev_range)
    out = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        short, _, message = chunk.partition("\x1f")
        out.append((short.strip(), message))
    return out


def main(argv: list[str]) -> int:
    rev_range = argv[1] if len(argv) > 1 else "HEAD"

    # 首次推送 / force push 时 before 可能是全 0 或已不可达, 退回只查最新一个 commit
    if ".." in rev_range:
        base = rev_range.split("..", 1)[0]
        if base in ("", ZERO_SHA) or base.strip("0") == "":
            rev_range = "HEAD"
    try:
        found = commits(rev_range)
    except RuntimeError as exc:
        print(f"区间 {rev_range} 取不到 commit({exc}), 退回只查 HEAD")
        rev_range = "HEAD"
        found = commits(rev_range)

    if not found:
        print(f"区间 {rev_range} 内没有需要校验的 commit")
        return 0

    missing = [sha for sha, message in found if not SIGNOFF.search(message)]
    if missing:
        print("以下 commit 缺少 Signed-off-by, DCO 校验不通过:")
        for sha in missing:
            print(f"  - {sha}")
        print()
        print("修复方式(只补签名, 不改内容):")
        print("  git commit --amend -s --no-edit        # 最新一个")
        print("  git rebase --signoff <base>            # 一串")
        return 1

    print(f"DCO 校验通过: {len(found)} 个 commit 都带 Signed-off-by")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))