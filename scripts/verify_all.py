#!/usr/bin/env python3
"""提交前的一把过: 把本机能跑的静态门禁一次跑完, 出一份汇总。

为什么需要它
------------
守线是一条条攒起来的, 现在散在五个工作流里: 许可证红线、生成物可复现(站点图标 /
景点封面)、种子 SQL 与源文件一致、前端类型与守线、DCO。提交前逐条手敲, 漏掉的那条
往往正好是 CI 会红的那条 —— v4.2 写完 `build_cn_attractions.py --check` 却没接进任何
工作流, 直到这一版才发现, 靠的就是把「该跑哪些」固定成一个入口。

不跑什么, 以及为什么
--------------------
* `db-schema.yml` 的结构与行数断言 —— 要真实 PostgreSQL(CI 起 postgres:16 服务),
  本机没有 psql 时无从跑起, 所以留在 CI。
* `backend` 的 pytest 与 `frontend` 的 typecheck / test / build —— 要装依赖、以分钟
  计, 不适合当每次提交的必跑项; 照 CONTRIBUTING.md 第五节单独跑。
* 前端守线(地图 / 定位 / restcountries) —— 判据是 `frontend-build.yml` 里的那条正则。
  抄一份到这里就等于同一个口径存了两处, 迟早对不上; 宁可只有一份, 由 CI 执行。
* DCO 签名 —— `push` 到 main 时 `dco.yml` 只告警(GitHub 网页编辑产生的 commit 补不上
  签名), 本地照着硬判会对这类 commit 误报, 所以留给 CI。

用法(用装了 backend/requirements.txt 的解释器, 否则许可证卡口会误报):
    python scripts/verify_all.py          # 跑全部
    python scripts/verify_all.py --list   # 只看会跑什么, 不跑
退出码: 0 全部通过; 1 有失败项
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

# 逐条门禁。每条对应 CI 里的一个步骤, 判据不在这里重写 —— 这里只负责跑与汇总。
SCRIPT_CHECKS = (
    ("许可证红线", "license_gate.py", ("--strict",)),
    ("站点图标可复现", "make_favicon.py", ("--check",)),
    ("景点封面可复现", "make_attraction_covers.py", ("--check",)),
    ("名录 SQL 与源 CSV 一致", "build_cn_attractions.py", ("--check",)),
)

# 本脚本故意不碰的检查。全写进报告, 免得读者以为「这里过了就等于全过了」。
NOT_COVERED = (
    ("db-schema.yml 的结构与行数断言", "要真实 PostgreSQL(CI 起 postgres:16 服务), 本机没有 psql"),
    ("backend 的 pytest", "要装后端依赖, 以分钟计; 按 CONTRIBUTING.md 第五节单独跑"),
    ("frontend 的 typecheck / test / build", "同上"),
    ("前端守线(地图 / 定位 / restcountries)", "判据只在 frontend-build.yml 里, 不在这里抄第二份"),
    ("DCO 签名", "push 到 main 时只告警(GitHub 网页编辑的 commit 补不上签名), 本地硬判会误报"),
)


def run_script(script: str, args: tuple[str, ...]) -> tuple[bool, str, str]:
    """跑 scripts/ 下的一个门禁。返回 (是否通过, 摘要, 完整输出)。"""
    # 子进程的输出编码必须钉死成 UTF-8: 中文 Windows 上 Python 往管道写时会退回
    # cp936, 父进程按 UTF-8 解出来就是一串乱码, 其中一个还可能 GBK 编不回去, 直接
    # 把本脚本打崩(第一版就是这么崩的)。钉死之后两边都是 UTF-8, 与终端无关。
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    out = (done.stdout or "") + (done.stderr or "")
    lines = [line for line in out.splitlines() if line.strip()]
    # 这几个脚本的末行就是结论(「一致: …」「通过: …」), 成功时只看它, 失败时看全文
    return done.returncode == 0, (lines[-1] if lines else "(没有输出)"), out


def check_workflows() -> tuple[bool, str, str]:
    """工作流写坏了的话, GitHub 只会记一次没有 job 的 failure, 之后每次推送都「看起来
    跑了, 其实一步没跑」。解析一遍挡住这种静默失效 —— 与 license-gate.yml 里那步是同
    一件事, 只是这里在本地也能跑。"""
    try:
        import yaml
    except ImportError:
        return True, "跳过(本机未装 pyyaml)", ""
    bad, detail = [], []
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = list((doc or {}).get("jobs") or {})
        if not jobs:
            bad.append(path.name)
        detail.append("%s: name=%r jobs=%s" % (path.name, (doc or {}).get("name"), jobs))
    if bad:
        return False, "解析不出 job: %s" % ", ".join(bad), "\n".join(detail)
    return True, "%d 份工作流都解析出 job" % len(detail), "\n".join(detail)


def main(argv: list[str]) -> int:
    if "--list" in argv[1:]:
        print("会跑:")
        for name, script, args in SCRIPT_CHECKS:
            print("  - %s: python scripts/%s %s" % (name, script, " ".join(args)))
        print("  - 工作流可解析: 解析 .github/workflows/*.yml")
        print("\n不跑:")
        for name, why in NOT_COVERED:
            print("  - %s(%s)" % (name, why))
        return 0

    total = len(SCRIPT_CHECKS) + 1
    print("=" * 68)
    print("提交前的一把过   解释器 %s" % sys.executable)
    print("=" * 68)

    results = []
    for index, (name, script, args) in enumerate(SCRIPT_CHECKS, start=1):
        ok, summary, detail = run_script(script, args)
        results.append((name, ok, summary, detail))
        print("\n[%d/%d] %s" % (index, total, name))
        print("      %s  %s" % ("通过" if ok else "失败", summary))
    ok, summary, detail = check_workflows()
    results.append(("工作流可解析", ok, summary, detail))
    print("\n[%d/%d] 工作流可解析" % (total, total))
    print("      %s  %s" % ("通过" if ok else "失败", summary))

    failed = [name for name, ok, _, _ in results if not ok]
    skipped = [name for name, ok, summary, _ in results if ok and summary.startswith("跳过")]
    print("\n" + "-" * 68)
    print("通过 %d 项 / 跳过 %d 项 / 失败 %d 项"
          % (len(results) - len(failed) - len(skipped), len(skipped), len(failed)))

    if failed:
        print("\n失败明细:")
        for name, ok, summary, detail in results:
            if ok:
                continue
            print("\n--- %s ---" % name)
            print("\n".join("    " + line for line in (detail or summary).splitlines()))
        print("\n常见修法: 生成物对不上就重跑对应脚本(--check 的反面就是生成命令), 别手改产物;")
        print("          许可证红了先看导入链, 不要往告警名单里加例外。")

    print("\n没覆盖的(要 CI 或单独跑):")
    for name, why in NOT_COVERED:
        print("  - %s —— %s" % (name, why))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
