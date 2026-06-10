# author: bdth
# email: 2074055628@qq.com
# 投喂分流 保护检查 回收站删除

from __future__ import annotations

import os
from pathlib import Path

from desktop_pet.settings import DATA_DIR

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
_DOC_EXTS = frozenset({".pdf", ".md", ".doc", ".docx", ".pptx"})  # txt等含糊的当食物
_RISKY_EXTS = frozenset({".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".dll", ".sys", ".lnk", ".scr"})
_BIG_BYTES = 200 * 1024 * 1024
_SIZE_SCAN_CAP = 20000  # 文件夹算大小最多走这么多个文件


def _protected_dirs() -> list[Path]:
    """绝不许吃的目录"""
    dirs: list[Path] = []
    for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(env)
        if v:
            dirs.append(Path(v))
    home = Path.home()
    dirs.append(DATA_DIR)
    # 主目录本身和一级特殊目录只保护目录自身 里面的文件可以吃
    dirs.extend(home / n for n in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"))
    dirs.append(home)
    return dirs


def is_protected(path: str) -> bool:
    """目录自身或系统目录内的东西不能吃"""
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        return True
    for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(env)
        if v:
            root = Path(v)
            if p == root or root in p.parents:
                return True
    home = Path.home()
    if p == home or p == DATA_DIR or DATA_DIR in p.parents:
        return True
    if p.parent == home and p.is_dir():  # 主目录一级子目录整个吃掉太危险
        return True
    if p.drive and p == Path(p.drive + "\\"):  # 盘根
        return True
    return False


def classify(paths: list[str]) -> str:
    """整批定性 protected risky image doc food missing"""
    existing = [p for p in paths if Path(p).expanduser().exists()]
    if not existing:
        return "missing"
    if any(is_protected(p) for p in existing):
        return "protected"
    exts = [Path(p).suffix.lower() for p in existing]
    if any(e in _RISKY_EXTS for e in exts):
        return "risky"
    if len(existing) == 1 and not Path(existing[0]).expanduser().is_dir():
        if exts[0] in _IMAGE_EXTS:
            return "image"
        if exts[0] in _DOC_EXTS:
            return "doc"
    return "food"


def total_size(paths: list[str]) -> tuple[int, bool]:
    """算总字节 文件夹递归 超扫描上限返回截断标记"""
    total = 0
    seen = 0
    for raw in paths:
        p = Path(raw).expanduser()
        try:
            if p.is_file():
                total += p.stat().st_size
                seen += 1
            elif p.is_dir():
                for root, _dirs, files in os.walk(p):
                    for name in files:
                        try:
                            total += (Path(root) / name).stat().st_size
                        except OSError:
                            pass
                        seen += 1
                        if seen >= _SIZE_SCAN_CAP:
                            return total, True
        except OSError:
            pass
        if seen >= _SIZE_SCAN_CAP:
            return total, True
    return total, False


def has_dir(paths: list[str]) -> bool:
    return any(Path(p).expanduser().is_dir() for p in paths)


def human_size(nbytes: int) -> str:
    """字节转人话"""
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size:.1f}GB"


def recycle(paths: list[str]) -> str | None:
    """整批送回收站 成功返回None 失败返回原因"""
    try:
        from win32com.shell import shell, shellcon
    except ImportError as exc:
        return f"shell unavailable: {exc}"
    items = "\0".join(str(Path(p).expanduser().resolve()) for p in paths)
    flags = (shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION
             | shellcon.FOF_SILENT | shellcon.FOF_NOERRORUI)
    try:
        rc, aborted = shell.SHFileOperation((0, shellcon.FO_DELETE, items, None, flags))
    except Exception as exc:
        return str(exc)
    if rc != 0 or aborted:
        return f"SHFileOperation rc={rc} aborted={aborted}"
    return None
