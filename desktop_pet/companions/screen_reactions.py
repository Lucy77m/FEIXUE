# Low-frequency screen-aware contextual reactions via OCR keyword matching.
# Every 5-8 minutes, takes a lightweight OCR snapshot of the active screen,
# matches keywords against a rule table, and triggers a pet reaction.
# No LLM call is needed — pure rule engine.

from __future__ import annotations

import logging
import random
import threading
import time

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import i18n, presence

# Poll interval: 5-8 minutes (with random jitter each cycle)
_POLL_BASE_MS = 5 * 60 * 1000
_POLL_JITTER_MS = 3 * 60 * 1000

# Cooldown between reactions (30 minutes)
_COOLDOWN_S = 30 * 60

# Rules: (keywords_list, reaction_name, i18n_key)
# Keywords are case-insensitive substrings matched against OCR text + window title.
_RULES: list[tuple[list[str], str, str]] = [
    # Test results passing
    (["passed", "pass", "通过", "success", "ok", "all passed", "全部通过"],
     "celebrate", "screen_test_pass"),
    # Errors / failures
    (["failed", "fail", "错误", "error:", "exception", "traceback"],
     "droop", "screen_error"),
    # Building / compiling
    (["building", "compiling", "编译", "构建", "webpack", "cargo build", "npm run build"],
     "read", "screen_building"),
    # Git operations
    (["git push", "git commit", "merged", "pull request", "合并", "merge pull request"],
     "perk_up", "screen_git"),
    # Travel planning
    (["机票", "航班", "flight", "hotel", "酒店", "booking", "预订"],
     "peek", "screen_travel"),
]


class ScreenReactions(QObject):
    """Observe screen content via OCR and trigger contextual pet reactions."""

    _sampled = Signal(str)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._busy = False
        self._last_react: float = 0.0
        self._sampled.connect(self._on_sampled)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start(_POLL_BASE_MS + random.randint(0, _POLL_JITTER_MS))

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            logger.debug("screen_reactions: timer stop failed", exc_info=True)

    def _tick(self) -> None:
        if self._busy:
            return
        if not self._host._settings.proactive_enabled:
            return
        if self._host._meeting_mode or self._host._engaged():
            return
        if self._host._wellbeing.in_flow():
            return
        pet = self._host._pet
        if not self._host._shown or not pet.isVisible() or pet.is_asleep:
            return
        self._busy = True
        # Jitter the next interval so it does not fire on a predictable cadence
        self._timer.setInterval(_POLL_BASE_MS + random.randint(0, _POLL_JITTER_MS))
        threading.Thread(target=self._probe, daemon=True, name="feixue-screen-react").start()

    def _probe(self) -> None:
        try:
            from desktop_pet.executor.vision import ocr_screen
            title = presence.foreground_window_title()
            text = ocr_screen()
            self._sampled.emit((title or "") + " " + (text or "")[:2000])
        except Exception:
            logger.debug("screen_reactions: probe failed", exc_info=True)
            self._busy = False

    @Slot(str)
    def _on_sampled(self, text: str) -> None:
        now = time.monotonic()
        if now - self._last_react < _COOLDOWN_S:
            return
        lowered = text.lower()
        for keywords, reaction, i18n_key in _RULES:
            if any(kw.lower() in lowered for kw in keywords):
                self._last_react = now
                self._host._feed_react(reaction)
                self._host._feed_pop(i18n.t(i18n_key))
                return
