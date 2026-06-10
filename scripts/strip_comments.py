# author: bdth
# email: 2074055628@qq.com
# 批量删注释工具：只保留文件顶部的头注释（author/email/文件描述）与功能性指令，删掉其余所有注释。
# 用 tokenize 精确识别真正的注释 token，绝不误伤字符串里的 #。dry-run 默认，加 --apply 才落地。

from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", ".git", "__pycache__", "ghcli", "build", "dist", ".idea", ".vscode"}
PRESERVE = ("noqa", "type:", "pragma", "pylint:", "ruff:", "fmt:", "isort:", "nopep8", "coding:", "coding=", "!/")


def _iter_py():
    for p in ROOT.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p


def _keep(comment_text: str) -> bool:
    if "--all" in sys.argv:
        return False
    low = comment_text.lower()
    return any(s in low for s in PRESERVE)


def strip_file(path: Path, apply: bool):
    src = path.read_bytes()
    try:
        toks = list(tokenize.tokenize(io.BytesIO(src).readline))
    except (tokenize.TokenError, SyntaxError):
        return None
    text = src.decode("utf-8")
    lines = text.splitlines(keepends=True)

    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING,
            tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
    first_code_row = None
    for t in toks:
        if t.type not in skip:
            first_code_row = t.start[0]
            break
    if first_code_row is None:
        first_code_row = 1 << 30

    del_lines: set[int] = set()
    trunc: dict[int, int] = {}
    removed = 0
    preserved = []
    for t in toks:
        if t.type != tokenize.COMMENT:
            continue
        row, col = t.start
        if row < first_code_row:
            continue
        if _keep(t.string):
            preserved.append((path, row, t.string.strip()))
            continue
        before = lines[row - 1][:col]
        if before.strip() == "":
            del_lines.add(row)
        else:
            trunc[row] = col
        removed += 1

    if removed and apply:
        out = []
        for i, line in enumerate(lines, start=1):
            if i in del_lines:
                continue
            if i in trunc:
                ending = line[len(line.rstrip("\r\n")):] or "\n"
                out.append(line[:trunc[i]].rstrip() + ending)
            else:
                out.append(line)
        path.write_text("".join(out), encoding="utf-8", newline="")
    return removed, preserved


def main():
    apply = "--apply" in sys.argv
    total_files = total_removed = changed = 0
    all_preserved = []
    for p in sorted(_iter_py()):
        res = strip_file(p, apply)
        if res is None:
            print(f"  SKIP (无法解析): {p.relative_to(ROOT)}")
            continue
        removed, preserved = res
        total_files += 1
        all_preserved.extend(preserved)
        if removed:
            changed += 1
            total_removed += removed
            print(f"  {removed:4d}  {p.relative_to(ROOT)}")
    print(f"\n{'已删除' if apply else 'DRY-RUN 将删除'} {total_removed} 条注释，涉及 {changed}/{total_files} 个文件")
    if all_preserved:
        print(f"\n保留的功能性指令 {len(all_preserved)} 条（删了会影响工具行为）：")
        for path, row, txt in all_preserved:
            print(f"  {path.relative_to(ROOT)}:{row}  {txt}")


if __name__ == "__main__":
    main()
