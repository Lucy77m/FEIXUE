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
    except Exception as exc:  # noqa: BLE001
        return f"[read failed: {exc}]"
    if len(text) > _MAX_READ:
        return text[:_MAX_READ] + f"\n[truncated; full text is {len(text)} chars]"
    return text or "(empty file)"


def write_file(path: str, content: str) -> str:
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return f"[write failed: {exc}]"
    return f"Wrote {path} ({len(content)} chars)."


def list_dir(path: str = ".") -> str:
    target = Path(path).expanduser()
    if not target.is_dir():
        return f"[not a directory or doesn't exist: {path}]"
    try:
        entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except Exception as exc:  # noqa: BLE001
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


def edit_file(path: str, old: str, new: str, replace_all: bool = False) -> str:
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    if not old:
        return "[old_string can't be empty]"
    try:
        text, encoding = _read_with_encoding(target)
    except Exception as exc:  # noqa: BLE001
        return f"[read failed: {exc}]"
    count = text.count(old)
    if count == 0:
        return f"[nothing to replace: old_string not found in {path} (whitespace/indentation must match exactly)]"
    if count > 1 and not replace_all:
        return f"[old_string appears {count} times in {path} — ambiguous; make it longer to be unique, or set replace_all=true]"
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    try:
        target.write_text(updated, encoding=encoding)
    except Exception as exc:  # noqa: BLE001
        return f"[write failed: {exc}]"
    return f"Replaced {count if replace_all else 1} occurrence(s) in {path}."


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
    except Exception as exc:  # noqa: BLE001
        return f"[glob failed: {exc}]"
    return "\n".join(matches) if matches else "(no matching files)"
