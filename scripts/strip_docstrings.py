# author: bdth
# email: 2074055628@qq.com
# 批量删 docstring：用 ast 精确定位 Module/函数/类的首个字符串语句并删除；
# 若 docstring 是函数/类体内唯一语句，删后补 pass 以免空体语法错误。dry-run 默认，--apply 落地。

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", ".git", "__pycache__", "ghcli", "build", "dist", ".idea", ".vscode"}
_HAS_BODY = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _iter_py():
    for p in ROOT.rglob("*.py"):
        if not any(part in EXCLUDE_DIRS for part in p.parts):
            yield p


def strip_file(path: Path, apply: bool):
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    lines = src.splitlines(keepends=True)

    targets = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, *_HAS_BODY)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        before = lines[first.lineno - 1][: first.col_offset]
        if before.strip() != "":
            continue
        need_pass = isinstance(node, _HAS_BODY) and len(body) == 1
        targets.append((first.lineno, first.end_lineno, first.col_offset, need_pass))

    if targets and apply:
        for start, end, indent, need_pass in sorted(targets, key=lambda x: -x[0]):
            lines[start - 1 : end] = [" " * indent + "pass\n"] if need_pass else []
        path.write_text("".join(lines), encoding="utf-8", newline="")
    return len(targets)


def main():
    apply = "--apply" in sys.argv
    total = changed = files = 0
    for p in sorted(_iter_py()):
        n = strip_file(p, apply)
        if n is None:
            print(f"  SKIP (无法解析): {p.relative_to(ROOT)}")
            continue
        files += 1
        if n:
            changed += 1
            total += n
            print(f"  {n:4d}  {p.relative_to(ROOT)}")
    print(f"\n{'已删除' if apply else 'DRY-RUN 将删除'} {total} 个 docstring，涉及 {changed}/{files} 个文件")


if __name__ == "__main__":
    main()
