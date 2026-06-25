# 做梦伴生 主人离开它睡着够久 就把高显著记忆揉成一个梦 攒着等你回来迷迷糊糊提一嘴

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer

from desktop_pet import presence  # noqa: F401  先留着 将来按在场细分触发
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.emotion.state import emotion

_POLL_MS = 60_000
_DREAM_AFTER_S = 8 * 60    # 睡着满这么久才做一个梦
_RAPPORT_GATE = 0.4        # 还不熟就不做关于你的梦


class Dreams(QObject):
    """睡着够久就让worker后台做一个梦 醒来或回来时交给打招呼用一次 只在内存"""

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._asleep_since = 0.0
        self._dreamed_this_sleep = False
        self._pending = ""

    def start(self) -> None:
        self._timer.start(_POLL_MS)

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass

    def set_dream(self, text: str) -> None:
        """worker 把做好的梦回传过来 攒着"""
        self._pending = (text or "").strip()
        if self._pending:
            try:
                from desktop_pet.world import get_world
                get_world().create_dream(self._pending)
            except Exception:
                pass

    def take_dream_hint(self) -> str:
        """回来打招呼时取一次梦的提示 取完即清 没梦给空串"""
        dream, self._pending = self._pending, ""
        return agent_prompts.dream_recall_hint(dream) if dream else ""

    def _tick(self) -> None:
        pet = self._host._pet
        if not pet.isVisible() or not pet.is_asleep:
            # 醒着或不在场景 重置这觉的计时
            self._asleep_since = 0.0
            self._dreamed_this_sleep = False
            return
        now = time.monotonic()
        if self._asleep_since == 0.0:
            self._asleep_since = now
            return
        if self._dreamed_this_sleep or self._host._worker.is_running:
            return
        if now - self._asleep_since < _DREAM_AFTER_S:
            return
        rapport = emotion.unlocked_rapport()
        if rapport < _RAPPORT_GATE:
            return
        self._dreamed_this_sleep = True
        self._host.request_dream.emit()  # 后台揉个梦 不出声
        # 同一觉里顺手做记忆合并 把这阵子攒的同主题零碎揉成高阶概括
        # 自限的 揉过的标记掉 要等新的相关记忆攒够才再成簇 没簇就静默
        self._host.request_consolidate.emit()
