"""API 进程绝不能依赖 RecBole —— 把「物理隔离」变成可执行的断言。

RecBole 的 ray<=2.6.3 / hyperopt==0.2.5 把 Python 上限锁在 3.11, 与 API 的 3.13
不可能共存(见 docs/BASES.md)。

注意这里查的是**真实 import 与依赖清单**, 不是文本里出现过这个词:
app 里的注释和文档反而要明确写出「绝不 import ___」, 那种提及是好事, 不该判违规。
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
NEEDLE = "recbole"


def imported_roots(path: pathlib.Path) -> set[str]:
    """一个 Python 文件里所有 import 的最顶层模块名。"""
    roots: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_app_code_does_not_import_recbole():
    offenders = {}
    for path in (BACKEND / "app").rglob("*.py"):
        roots = imported_roots(path)
        if NEEDLE in roots:
            offenders[str(path.relative_to(BACKEND))] = sorted(roots)
    assert offenders == {}, f"API 代码 import 了 {NEEDLE}: {offenders}"


def test_recbole_is_not_loaded_at_runtime():
    """导入整个 app 之后, ___ 不应该出现在 sys.modules 里。"""
    import app.main  # noqa: F401

    loaded = [name for name in sys.modules if name.split(".")[0] == NEEDLE]
    assert loaded == [], f"运行期加载了 {NEEDLE}: {loaded}"


def test_requirements_do_not_list_recbole():
    """requirements 里可以有「不要装 ___」的注释, 但不能真把它列成依赖。"""
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (BACKEND / name).read_text(encoding="utf-8").splitlines():
            spec = line.split("#", 1)[0].strip().lower()
            assert NEEDLE not in spec, f"{name} 把 {NEEDLE} 列成了依赖: {line!r}"
