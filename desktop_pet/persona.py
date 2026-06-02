# author: bdth
# email: 2074055628@qq.com
# 持久化并读写桌宠的「自我画像」演化层（存于 persona.json，注入对话上下文）

"""自我画像（persona）——它跟某个人相处下来、一点点长成的「自己」。
不是写死的设定，是关系养出来的；由每轮反思缓慢重写、有惯性。
出厂底色写在 prompts 里（种子），这里存的是「演化层」：空 = 还没长出个性，纯底色。"""

from __future__ import annotations

import json
import threading
from datetime import datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "persona.json"
_MAX_CHARS = 600  # 重写而非堆积——画像始终是「当下的自己」，不滚雪球
# 反思 daemon 线程写 update、主线程写 clear；原子写防半截 JSON，锁防两路并发互踩。
_LOCK = threading.RLock()


def _load() -> str:
    if not _PATH.exists():
        return ""
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return data.get("portrait", "") if isinstance(data, dict) else ""


def _save(portrait: str) -> None:
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
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:
        _save(text[:_MAX_CHARS])


def as_context() -> str:
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
