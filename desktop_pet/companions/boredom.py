# 无聊模式 只读前台窗口标题和键鼠空闲时间 让桌宠在合适时机演一点小剧场

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import i18n, presence
from desktop_pet.companions.context_classifier import classify_window

_POLL_MS = 45_000
_MIN_INTERVAL_S = 8 * 60
_MAX_INTERVAL_S = 14 * 60
_TERMINAL_IDLE_S = 90.0
_IDLE_S = 4 * 60.0
_AWAY_S = 20 * 60.0
_DRIFT_DWELL_S = 20 * 60.0

_PERFORMS = {
    "terminal": ("coffee", "sleuth", "rubik"),
    "stuck": ("coffee", "read", "sleuth"),
    "drift": ("popcorn", "phone", "soda"),
    "idle": ("yarn", "bubbles", "paperplane", "stars"),
}


def _classify(title: str) -> str:
    cat = classify_window(title)
    if cat == "terminal":
        return "terminal"
    if cat == "code":
        return "work"
    if cat in ("media", "social"):
        return "drift"
    return "idle"


class Boredom(QObject):
    """安全的桌面小剧场 不触碰模型、不联网、不操控电脑"""

    _sampled = Signal(str, float)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._busy = False
        self._sampled.connect(self._on_sampled)
        self._cat = ""
        self._since = 0.0
        self._next_at = 0.0

    def start(self) -> None:
        self._timer.start(_POLL_MS)
        self._next_at = time.monotonic() + random.uniform(60.0, 120.0)

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            logger.debug("boredom: timer stop failed", exc_info=True)

    def _tick(self) -> None:
        if self._busy or not getattr(self._host._settings, "boredom_enabled", True):
            return
        if not self._host._settings.proactive_enabled:
            return
        if self._host._meeting_mode or self._host._engaged():
            return
        pet = self._host._pet
        if not self._host._shown or not pet.isVisible() or pet.is_asleep:
            return
        if self._host._wellbeing.in_flow():
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True, name="feixue-boredom").start()

    def _probe(self) -> None:
        try:
            self._sampled.emit(presence.foreground_window_title(), presence.idle_seconds())
        except Exception:
            logger.debug("boredom: probe failed", exc_info=True)

    @Slot(str, float)
    def _on_sampled(self, title: str, idle: float) -> None:
        now = time.monotonic()
        cat = _classify(title)
        if cat != self._cat:
            self._cat = cat
            self._since = now
        if now < self._next_at or idle >= _AWAY_S:
            self._busy = False
            return

        mood = self._pick_mood(cat, now - self._since, idle)
        if not mood:
            self._busy = False
            return
        hour = datetime.now().hour
        if 23 <= hour or hour < 6:
            gap = random.uniform(900, 1500)   # 深夜：15-25 分钟
        elif 6 <= hour < 9:
            gap = random.uniform(300, 600)    # 早晨：5-10 分钟
        else:
            gap = random.uniform(_MIN_INTERVAL_S, _MAX_INTERVAL_S)  # 白天：正常
        self._next_at = now + gap
        self._host._feed_perform(random.choice(_PERFORMS[mood]))
        self._host._feed_pop(i18n.t("boredom_" + mood))
        self._busy = False

    @staticmethod
    def _pick_mood(cat: str, dwell: float, idle: float) -> str:
        if cat == "terminal" and idle >= _TERMINAL_IDLE_S:
            return "terminal"
        if cat == "work" and idle >= _IDLE_S:
            return "stuck"
        if cat == "drift" and dwell >= _DRIFT_DWELL_S and idle < _IDLE_S:
            return "drift"
        if idle >= _IDLE_S:
            return "idle"
        return ""
