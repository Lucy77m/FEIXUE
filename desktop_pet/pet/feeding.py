# author: bdth
# email: 2074055628@qq.com
# 投喂分流 保护检查 回收站删除

from __future__ import annotations

import os
import time
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


def temp_junk_size(cap_files: int = 30000) -> int:
    """算temp目录体积 给虫子扫描用"""
    import tempfile
    total = 0
    seen = 0
    try:
        for root, _dirs, files in os.walk(tempfile.gettempdir()):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    pass
                seen += 1
                if seen >= cap_files:
                    return total
    except OSError:
        pass
    return total


def clean_temp(older_than_days: float = 7.0, cap_files: int = 5000) -> tuple[int, int]:
    """删过期temp文件 返回清掉的字节和个数 占用中的跳过"""
    import tempfile
    import time as _time
    cutoff = _time.time() - older_than_days * 86400
    freed = 0
    count = 0
    try:
        for root, _dirs, files in os.walk(tempfile.gettempdir()):
            for name in files:
                p = Path(root) / name
                try:
                    st = p.stat()
                    if st.st_mtime >= cutoff:
                        continue
                    p.unlink()
                    freed += st.st_size
                    count += 1
                except OSError:
                    continue  # 被占用删不掉很正常
                if count >= cap_files:
                    return freed, count
    except OSError:
        pass
    return freed, count


def _shfileop(items: str) -> str | None:
    """单次回收 成功None 失败给技术原因"""
    try:
        from win32com.shell import shell, shellcon
    except ImportError as exc:
        return f"shell unavailable: {exc}"
    flags = (shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION
             | shellcon.FOF_SILENT | shellcon.FOF_NOERRORUI)
    try:
        rc, aborted = shell.SHFileOperation((0, shellcon.FO_DELETE, items, None, flags))
    except Exception as exc:
        return str(exc)
    if rc != 0 or aborted:
        # rc 多半是 0x7C(DE_INVALIDFILES) 或 0x20(共享冲突)——其实都是"里面有文件正被打开"
        return f"SHFileOperation rc={rc} (0x{rc & 0xFFFFFFFF:X}) aborted={aborted}"
    return None


def recycle(paths: list[str]) -> str | None:
    """整批送回收站 成功返回None 失败返回原因"""
    # pFrom 必须双 null 结尾 pywin32 只给 Python 串补一个 末尾再手动补一个
    items = "\0".join(str(Path(p).expanduser().resolve()) for p in paths) + "\0"
    err = _shfileop(items)
    if err is not None and not err.startswith("shell unavailable"):
        time.sleep(0.4)  # 可能只是瞬时锁(杀软扫描/资源管理器刚松手) 等一下再试一次
        err = _shfileop(items)
    return err


def _is_locked(path: str) -> bool:
    """独占方式打开 打不开说明被别的进程占着 出错保守当没锁"""
    try:
        import pywintypes
        import win32con
        import win32file
    except ImportError:
        return False
    try:
        handle = win32file.CreateFile(
            path, win32con.GENERIC_READ, 0, None,  # share=0 不允许共享
            win32con.OPEN_EXISTING, 0, None)
        win32file.CloseHandle(handle)
        return False
    except pywintypes.error:
        return True
    except Exception:
        return False


def _lock_holder(path: str) -> str:
    """尽力找出谁开着这个文件 找不到/没权限返回空串"""
    try:
        import psutil
    except ImportError:
        return ""
    try:
        target = os.path.normcase(os.path.abspath(path))
    except OSError:
        return ""
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                for handle in proc.open_files():
                    if os.path.normcase(handle.path) == target:
                        return proc.info.get("name") or ""
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue
    except Exception:
        return ""
    return ""


def diagnose_lock(paths: list[str], cap: int = 400) -> tuple[str, str]:
    """投喂失败时找出第一个被占用的文件名和占用它的进程名 都找不到返回('', '')"""
    files: list[str] = []
    for raw in paths:
        p = Path(raw).expanduser()
        try:
            if p.is_file():
                files.append(str(p))
            elif p.is_dir():
                for root, _dirs, names in os.walk(p):
                    for name in names:
                        files.append(str(Path(root) / name))
                    if len(files) >= cap:
                        break
        except OSError:
            continue
        if len(files) >= cap:
            break
    for f in files[:cap]:
        if _is_locked(f):
            return Path(f).name, _lock_holder(f)
    return "", ""
