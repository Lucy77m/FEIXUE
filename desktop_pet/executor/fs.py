# author: bdth
# email: 2074055628@qq.com
# 文件系统执行器 读写 列目录 编辑 正则搜索 glob

from __future__ import annotations

import os
import re
from fnmatch import fnmatch
from pathlib import Path

_MAX_READ = 20000
_MAX_READ_CAP = 100_000
_MAX_ENTRIES = 200
_MAX_HITS = 80
_MAX_SEARCH_CHARS = 18_000
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
    """读文本并猜编码"""
    raw = target.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding), ("utf-8" if encoding == "utf-8-sig" else encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def paginate(text: str, offset: int = 0, max_chars: int = 0) -> str:
    """超长文本分片 offset 续读 max_chars 可调"""
    try:
        off = max(0, int(offset))  # offset 转不了就当从头读
    except (TypeError, ValueError):
        off = 0
    try:
        cap = min(int(max_chars), _MAX_READ_CAP) if int(max_chars) > 0 else _MAX_READ
    except (TypeError, ValueError):
        cap = _MAX_READ
    cap = max(cap, 1000)
    total = len(text)
    if off == 0 and total <= cap:
        return text or "(empty file)"
    if off >= total:
        return f"[offset {off} is past the end of the file ({total} chars) — nothing more to read]"
    chunk = text[off : off + cap]
    end = off + len(chunk)
    header = f"[chars {off}–{end} of {total}]\n"
    footer = f"\n[truncated; continue with offset={end} (or raise max_chars, up to {_MAX_READ_CAP})]" if end < total else "\n[end of file]"
    return header + chunk + footer


def read_file(path: str, offset: int = 0, max_chars: int = 0) -> str:
    """读文件 超长走 paginate 分片"""
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    try:
        text, _ = _read_with_encoding(target)
    except Exception as exc:
        return f"[read failed: {exc}]"
    return paginate(text, offset, max_chars)


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
    """抹平 CRLF CR 统一成 LF"""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _fit_indent(new_lines: list[str], old_first: str, file_first: str) -> list[str]:
    """把 new 缩进对齐到文件实际缩进"""
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
    """按行容错替换 精确匹配失败后的兜底"""
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
    """改文件 先精确替换不中再按行容错"""
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    if not old:
        return "[old_string can't be empty]"
    try:
        raw, encoding = _read_with_encoding(target)
    except Exception as exc:
        return f"[read failed: {exc}]"
    nl = "\r\n" if "\r\n" in raw else "\n"  # 记住原换行 回写时还原
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


def _iter_files(base: Path):
    """走目录树 剪掉 _IGNORE_DIRS 不下钻"""
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for name in files:
            yield Path(root) / name


def search_code(pattern: str, path: str = ".", max_results: int = _MAX_HITS, context: int = 0) -> str:
    """正则逐行搜文本文件 context 给命中行带前后文"""
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"[invalid regex: {exc}]"
    try:
        ctx = max(0, min(int(context), 5))
    except (TypeError, ValueError):
        ctx = 0
    base = Path(path).expanduser()
    if not base.exists():
        return f"[path doesn't exist: {path}]"
    candidates = [base] if base.is_file() else _iter_files(base)
    out: list[str] = []
    used = 0
    count = 0
    for file in candidates:
        if file.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            text, _ = _read_with_encoding(file)
        except Exception:
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if not regex.search(line):
                continue
            if ctx:
                block = [
                    f"{file}:{j + 1}{':' if j == idx else '-'} {lines[j].strip()[:160]}"
                    for j in range(max(0, idx - ctx), min(len(lines), idx + ctx + 1))
                ]
                piece = ("--\n" if out else "") + "\n".join(block)
            else:
                piece = f"{file}:{idx + 1}: {line.strip()[:160]}"
            out.append(piece)
            used += len(piece)
            count += 1
            if count >= max_results or used >= _MAX_SEARCH_CHARS:
                return "\n".join(out) + f"\n…[truncated at {count} results; narrow the search]"
    return "\n".join(out) if out else "(no matches)"


def glob_files(pattern: str, path: str = ".", max_results: int = _MAX_ENTRIES) -> str:
    base = Path(path).expanduser()
    if not base.exists():
        return f"[path doesn't exist: {path}]"
    matches: list[str] = []
    try:
        for file in _iter_files(base):
            rel = file.relative_to(base).as_posix()
            # 纯文件名和相对路径都试
            if not (fnmatch(file.name, pattern) or fnmatch(rel, pattern)):
                continue
            matches.append(str(file))
            if len(matches) >= max_results:
                matches.append(f"[hit the {max_results}-result cap]")
                break
    except Exception as exc:
        return f"[glob failed: {exc}]"
    return "\n".join(matches) if matches else "(no matching files)"
