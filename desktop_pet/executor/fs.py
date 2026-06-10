# author: bdth
# email: 2074055628@qq.com
# 文件系统执行器:提供读写、列目录、编辑、正则搜索和 glob 等文件操作工具

from __future__ import annotations

import os
import re
from fnmatch import fnmatch
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
    """读文本并猜编码 → (text, encoding)。utf-8-sig 优先(顺手吃掉 BOM)，再退 gbk —— 国内机器一堆
    记事本/老工具存的 gbk 源码；都不成才 utf-8 + replace 硬解，保证 edit 回写时编码不串。"""
    raw = target.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding), ("utf-8" if encoding == "utf-8-sig" else encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def read_file(path: str, offset: int = 0) -> str:
    """读文件，超 _MAX_READ 就分片：offset 从字符位续读，footer 带下一段 offset 让模型自己翻页。"""
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    try:
        text, _ = _read_with_encoding(target)
    except Exception as exc:
        return f"[read failed: {exc}]"
    try:
        off = max(0, int(offset))  # 模型常把 offset 传成字符串/null，转不了就当从头读
    except (TypeError, ValueError):
        off = 0
    total = len(text)
    if off == 0 and total <= _MAX_READ:
        return text or "(empty file)"
    if off >= total:
        return f"[offset {off} is past the end of the file ({total} chars) — nothing more to read]"
    chunk = text[off : off + _MAX_READ]
    end = off + len(chunk)
    header = f"[chars {off}–{end} of {total}]\n"
    footer = f"\n[truncated; continue with offset={end}]" if end < total else "\n[end of file]"
    return header + chunk + footer


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
    """匹配只在 \\n 空间里做 —— CRLF/CR 先抹平，省得 old_string 因换行风格不同对不上。"""
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
    """改文件：先精确替换；多处命中又没给 replace_all 就报歧义不动手。精确不中再走 _fuzzy_replace
    按行容错。回写时保留原编码和原换行风格。"""
    target = Path(path).expanduser()
    if not target.is_file():
        return f"[not a file or doesn't exist: {path}]"
    if not old:
        return "[old_string can't be empty]"
    try:
        raw, encoding = _read_with_encoding(target)
    except Exception as exc:
        return f"[read failed: {exc}]"
    nl = "\r\n" if "\r\n" in raw else "\n"  # 记住原换行：匹配统一在 \n 里做，回写再换回去，别把整文件刷成 LF 炸出满屏 diff
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
    """走目录树，原地剪掉 _IGNORE_DIRS —— dirs[:] 切片就地改 os.walk 才会真的不下钻，
    比 rglob('*') 全捞完再按 parts 过滤省掉整个 node_modules/.git 的遍历。"""
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for name in files:
            yield Path(root) / name


def search_code(pattern: str, path: str = ".", max_results: int = _MAX_HITS) -> str:
    """正则逐行搜 —— 只碰 _TEXT_EXT 白名单(跳过二进制/图片)，命中满 max_results 就截断返回。"""
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"[invalid regex: {exc}]"
    base = Path(path).expanduser()
    if not base.exists():
        return f"[path doesn't exist: {path}]"
    candidates = [base] if base.is_file() else _iter_files(base)
    hits: list[str] = []
    for file in candidates:
        if file.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            text, _ = _read_with_encoding(file)
        except Exception:
            continue
        for number, line in enumerate(text.splitlines(), 1):
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
        for file in _iter_files(base):
            rel = file.relative_to(base).as_posix()
            # 两头都试：纯文件名(*.py)和相对路径(sub/*.py)都能中；rel 统一 posix 斜杠，免得 Windows 反斜杠匹配不上
            if not (fnmatch(file.name, pattern) or fnmatch(rel, pattern)):
                continue
            matches.append(str(file))
            if len(matches) >= max_results:
                matches.append(f"[hit the {max_results}-result cap]")
                break
    except Exception as exc:
        return f"[glob failed: {exc}]"
    return "\n".join(matches) if matches else "(no matching files)"
