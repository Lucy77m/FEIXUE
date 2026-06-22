# 桌宠自我画像存取 注入对话上下文

from __future__ import annotations

import json
import threading
from datetime import datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "persona.json"
_MAX_CHARS = 600  # 画像长度封顶
_LOCK = threading.RLock()


def _load() -> str:
    """读画像 没有或坏了当空"""
    if not _PATH.exists():
        return ""
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return data.get("portrait", "") if isinstance(data, dict) else ""


def _save(portrait: str) -> None:
    """原子写盘带时间戳 写失败吞掉"""
    try:
        atomic_write_text(
            _PATH,
            json.dumps(
                {"portrait": portrait, "updated": datetime.now().isoformat(timespec="minutes")},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except OSError:
        pass


def get() -> str:
    return _load()


def update(text: str) -> None:
    """覆盖式更新画像 空串忽略"""
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:
        _save(text[:_MAX_CHARS])


def as_context() -> str:
    """包成注入系统提示的段 空画像回空串"""
    portrait = _load()
    if not portrait:
        return ""
    return (
        "【你是谁】下面这段，是你跟这个人相处下来、一点点长成的自己——不是别人给的设定，"
        "是你们的关系养出来的，会随你们怎么相处继续变。让它自然成为你说话做事的底子，别照着复述：\n"
        + portrait
    )


def clear() -> None:
    with _LOCK:
        _save("")
