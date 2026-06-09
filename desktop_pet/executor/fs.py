# author: bdth
# email: 2074055628@qq.com
# 文件系统执行器:提供读写、列目录、编辑、正则搜索和 glob 等文件操作工具

from __future__ import annotations

import re
from pathlib import Path

_MAX_READ = 20000
_MAX_ENTRIES = 200
_MAX_HITS = 80
_IGNORE_DIRS = frozenset(
    {".venv", "venv", "__pycache__", ".git", "node_modules", ".idea",
     ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build"}
)
_TEXT_EXT = frozenset(
    {".py", ".pyi", ".js", ".ts", ".tsx", ".jsx", ".vue", ".json", ".md", ".txt",
     ".toml", ".yaml", ".yml", ".cfg", ".ini", ".html", ".css", ".scss",
     ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php",
     ".sh", ".ps1", ".bat", ".sql", ".xml", ".env"}
)


def _read_with_encoding(target: Path) -> tuple[str, str]:
    raw = target.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding), ("utf-8" if encoding == "utf-8-sig" else encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def read_file(path: str) -> str:
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[read failed: {exc}]"
    if len(text) > _MAX_READ:
        return text[:_MAX_READ] + f"\n[truncated; full text is {len(text)} chars]"
    return text or "(empty file)"


def write_file(path: str, content: str) -> str:
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"[write failed: {exc}]"
    return f"Wrote {path} ({len(content)} chars)."


def list_dir(path: str = ".") -> str:
    target = Path(path).expanduser()
    if not target.is_dir():
        return f"[not a directory or doesn't exist: {path}]"
    try:
        entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except Exception as exc:
        return f"[listing failed: {exc}]"
    if not entries:
        return "(empty directory)"
    lines = []
    for entry in entries[:_MAX_ENTRIES]:
        if entry.is_dir():
            lines.append(entry.name + "/")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = "?"
            lines.append(f"{entry.name}  ({size}B)")
    if len(entries) > _MAX_ENTRIES:
        lines.append(f"[{len(entries)} items total; showing first {_MAX_ENTRIES}]")
    return "\n".join(lines)


def _norm_eol(s: str) -> str:
    """统一到 \\n，消除 CRLF/CR 差异(匹配只在 \\n 空间里做)。"""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _fit_indent(new_lines: list[str], old_first: str, file_first: str) -> list[str]:
    """按行容错命中(忽略了行首缩进)时，把 new 的缩进对齐到文件里实际的缩进。"""
    oind = old_first[: len(old_first) - len(old_first.lstrip())]
    find = file_first[: len(file_first) - len(file_first.lstrip())]
    if oind == find:
        return new_lines
    out = []
    for ln in new_lines:
        if not ln.strip():
            out.append(ln)
        elif not oind:
            out.append(find + ln)
        elif ln.startswith(oind):
            out.append(find + ln[len(oind):])
        else:
            out.append(ln)
    return out


def _fuzzy_replace(text: str, old: str, new: str, replace_all: bool):
    """精确匹配失败后的兜底：按行比对，忽略行尾空白；再不中就连行首缩进也忽略，
    并把 new 重新缩进到文件实际缩进。返回 (updated, n) / None(没命中) / 'AMBIGUOUS'。"""
    flines = text.split("\n")
    olines = old.split("\n")
    nlines = new.split("\n") if new else []
    n = len(olines)
    if n == 0:
        return None
    for full_strip in (False, True):
        key = (lambda s: s.strip()) if full_strip else (lambda s: s.rstrip())
        okeys = [key(l) for l in olines]
        hits = [i for i in range(len(flines) - n + 1)
                if [key(x) for x in flines[i:i + n]] == okeys]
        if not hits:
            continue
        if len(hits) > 1 and not replace_all:
            return "AMBIGUOUS"
        targets = hits if replace_all else hits[:1]
        out, prev = [], 0
        for i in targets:
            out.extend(flines[prev:i])
            block = _fit_indent(nlines, olines[0], flines[i]) if full_strip else nlines
            out.extend(block)
            prev = i + n
        out.extend(flines[prev:])
        return "\n".join(out), len(targets)
    return None


def edit_file(path: str, old: str, new: str, replace_all: bool = False) -> str:
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    if not old:
        return "[old_string can't be empty]"
    try:
        raw, encoding = _read_with_encoding(target)
    except Exception as exc:
        return f"[read failed: {exc}]"
    nl = "\r\n" if "\r\n" in raw else "\n"
    text, old_n, new_n = _norm_eol(raw), _norm_eol(old), _norm_eol(new)

    count = text.count(old_n)
    if count > 1 and not replace_all:
        return f"[old_string appears {count} times in {path} — ambiguous; make it longer to be unique, or set replace_all=true]"
    if count >= 1:
        updated = text.replace(old_n, new_n) if replace_all else text.replace(old_n, new_n, 1)
        note = ""
    else:
        result = _fuzzy_replace(text, old_n, new_n, replace_all)
        if result == "AMBIGUOUS":
            return f"[old_string matches several places in {path} (ignoring whitespace) — make it longer/unique, or set replace_all=true]"
        if result is None:
            return f"[nothing to replace: old_string not found in {path} (even after ignoring whitespace/indentation)]"
        updated, count = result
        note = " (matched by ignoring whitespace differences — double-check the diff)"

    try:
        target.write_text(updated, encoding=encoding, newline=nl)
    except Exception as exc:
        return f"[write failed: {exc}]"
    return f"Replaced {count if replace_all else 1} occurrence(s) in {path}.{note}"


def search_code(pattern: str, path: str = ".", max_results: int = _MAX_HITS) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"[invalid regex: {exc}]"
    base = Path(path).expanduser()
    if not base.exists():
        return f"[path doesn't exist: {path}]"
    candidates = [base] if base.is_file() else base.rglob("*")
    hits: list[str] = []
    for file in candidates:
        if not file.is_file() or file.suffix.lower() not in _TEXT_EXT:
            continue
        if any(part in _IGNORE_DIRS for part in file.parts):
            continue
        try:
            lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            if regex.search(line):
                hits.append(f"{file}:{number}: {line.strip()[:160]}")
                if len(hits) >= max_results:
                    return "\n".join(hits) + f"\n…[hit the {max_results}-result cap; narrow the search]"
    return "\n".join(hits) if hits else "(no matches)"


def glob_files(pattern: str, path: str = ".", max_results: int = _MAX_ENTRIES) -> str:
    base = Path(path).expanduser()
    if not base.exists():
        return f"[path doesn't exist: {path}]"
    matches: list[str] = []
    try:
        for file in base.rglob(pattern):
            if any(part in _IGNORE_DIRS for part in file.parts):
                continue
            matches.append(str(file))
            if len(matches) >= max_results:
                matches.append(f"[hit the {max_results}-result cap]")
                break
    except Exception as exc:
        return f"[glob failed: {exc}]"
    return "\n".join(matches) if matches else "(no matching files)"
