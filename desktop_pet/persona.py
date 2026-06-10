# author: bdth
# email: 2074055628@qq.com
# 持久化并读写桌宠的「自我画像」演化层（存于 persona.json，注入对话上下文）

from __future__ import annotations

import json
import threading
from datetime import datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "persona.json"
_MAX_CHARS = 600  # 画像封顶，太长了注入上下文会挤掉别的、也容易让模型照抄
_LOCK = threading.RLock()


def _load() -> str:
    """读画像，没有/坏了一律当空——画像是锦上添花，缺了不该影响主流程。"""
    if not _PATH.exists():
        return ""
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""  # 文件被手改坏或半截写入，宁可丢画像也别抛出去
    return data.get("portrait", "") if isinstance(data, dict) else ""


def _save(portrait: str) -> None:
    """原子写盘，附带 updated 时间戳；写失败也吞掉——画像存不下不值得打断对话。"""
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
    """整段覆盖式更新画像；空串直接忽略，免得不小心把人格写没了。"""
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:  # 模型可能并发触发更新，加锁串行化读改写
        _save(text[:_MAX_CHARS])


def as_context() -> str:
    """包成注入系统提示的那段；画像为空就返回空串，让上层别白塞一段废话进去。"""
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
