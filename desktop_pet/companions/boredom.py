"""Low-noise desktop-life director.

This keeps the old Boredom class name because PetApp already wires it as a
companion, but the behavior is now about small desktop-native cues instead of
"perform + bubble" prompts.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

from PySide6.QtGui import QCursor
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import presence
from desktop_pet.companions.context_classifier import classify_window

_POLL_MIN_MS = 3_000
_POLL_MAX_MS = 8_000
_FIRST_CUE_GAP = (60.0, 120.0)
_LIFE_CUE_GAP = (120.0, 720.0)
_EDGE_PEEK_COOLDOWN_S = 10 * 60.0
_CURSOR_NEAR_PAD = 90
_CURSOR_HOLD_S = 2.0
_CURSOR_REACT_COOLDOWN_S = 12.0
_CURSOR_SHY_HOLD_S = 8.0
_CURSOR_SHY_COOLDOWN_S = 60.0
_TERMINAL_IDLE_S = 90.0
_IDLE_S = 4 * 60.0
_AWAY_S = 20 * 60.0
_DRIFT_DWELL_S = 20 * 60.0

_CUE_ACTIONS = {
    "terminal_idle": ("coffee", "rubik"),
    "work_idle": ("coffee", "read"),
    "drift_watch": ("popcorn", "phone", "soda"),
    "plain_idle": ("yarn", "bubbles", "paperplane", "stars"),
}
_MORNING_ACTIONS = {
    "plain_idle": ("bubbles", "paperplane", "yarn"),
}
_NIGHT_ACTIONS = {
    "terminal_idle": ("coffee", "read"),
    "work_idle": ("read", "tea"),
    "drift_watch": ("tea", "stars"),
    "plain_idle": ("read", "tea", "stars"),
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
    """Quiet desktop-life cues; no model calls, web, OCR, or task dispatch."""

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
        self._next_life_at = 0.0
        self._last_edge_peek = -_EDGE_PEEK_COOLDOWN_S
        self._cursor_near_since = 0.0
        self._last_cursor_react = 0.0
        self._last_cursor_shy = -_CURSOR_SHY_COOLDOWN_S
        self._recent_cues: deque[str] = deque(maxlen=3)

    def start(self) -> None:
        self._next_life_at = time.monotonic() + random.uniform(*_FIRST_CUE_GAP)
        self._arm_timer()

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            logger.debug("boredom: timer stop failed", exc_info=True)

    def _arm_timer(self) -> None:
        self._timer.start(random.randint(_POLL_MIN_MS, _POLL_MAX_MS))

    def _tick(self) -> None:
        self._arm_timer()
        if self._busy or not self._life_available():
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True, name="feixue-life").start()

    def _probe(self) -> None:
        try:
            self._sampled.emit(presence.foreground_window_title(), presence.idle_seconds())
        except Exception:
            logger.debug("boredom: probe failed", exc_info=True)
            self._busy = False

    @Slot(str, float)
    def _on_sampled(self, title: str, idle: float) -> None:
        try:
            now = time.monotonic()
            hour = datetime.now().hour
            cat = _classify(title)
            if cat != self._cat:
                self._cat = cat
                self._since = now

            if self._maybe_cursor_attention(now):
                return
            if idle >= _AWAY_S:
                return
            if self._maybe_edge_peek(now):
                self._schedule_next(now)
                return
            if now < self._next_life_at:
                return
            if self._maybe_window_perch():
                self._schedule_next(now)
                return
            if self._maybe_desk_habit(cat, now - self._since, idle, hour):
                self._schedule_next(now)
        finally:
            self._busy = False

    def _life_available(self) -> bool:
        settings = getattr(self._host, "_settings", None)
        if not getattr(settings, "boredom_enabled", True):
            return False
        if not getattr(settings, "proactive_enabled", True):
            return False
        if getattr(self._host, "_meeting_mode", False):
            return False
        if bool(getattr(self._host, "_shown", False)) is False:
            return False
        engaged = getattr(self._host, "_engaged", None)
        if callable(engaged) and engaged():
            return False
        foreground_fullscreen = getattr(self._host, "_foreground_is_fullscreen", None)
        if callable(foreground_fullscreen) and foreground_fullscreen():
            return False
        wellbeing = getattr(self._host, "_wellbeing", None)
        if wellbeing is not None and getattr(wellbeing, "in_flow", lambda: False)():
            return False
        pet = getattr(self._host, "_pet", None)
        if pet is None or not pet.isVisible() or getattr(pet, "is_asleep", False):
            return False
        if getattr(pet, "is_life_busy", False):
            return False
        return True

    def _maybe_cursor_attention(self, now: float) -> bool:
        pet = getattr(self._host, "_pet", None)
        if pet is None or not hasattr(pet, "life_notice_cursor"):
            return False
        try:
            pos = QCursor.pos()
            near = pet.frameGeometry().adjusted(
                -_CURSOR_NEAR_PAD, -_CURSOR_NEAR_PAD,
                _CURSOR_NEAR_PAD, _CURSOR_NEAR_PAD,
            ).contains(pos)
        except Exception:
            return False
        if not near:
            self._cursor_near_since = 0.0
            return False
        if self._cursor_near_since <= 0.0:
            self._cursor_near_since = now
        lingered_for = now - self._cursor_near_since
        shy = lingered_for >= _CURSOR_SHY_HOLD_S and now - self._last_cursor_shy >= _CURSOR_SHY_COOLDOWN_S
        lingered = (
            now - self._cursor_near_since >= _CURSOR_HOLD_S
            and now - self._last_cursor_react >= _CURSOR_REACT_COOLDOWN_S
        )
        if not pet.life_notice_cursor(pos, lingered, shy):
            return False
        if shy:
            self._last_cursor_shy = now
            self._remember_cue("cursor_shy")
            return True
        if lingered:
            self._last_cursor_react = now
            self._remember_cue("cursor_attention")
            return True
        return False

    def _maybe_edge_peek(self, now: float) -> bool:
        if now - self._last_edge_peek < _EDGE_PEEK_COOLDOWN_S:
            return False
        pet = getattr(self._host, "_pet", None)
        if pet is None or not hasattr(pet, "start_edge_peek"):
            return False
        if not pet.start_edge_peek("", random.uniform(4.5, 7.0)):
            return False
        self._last_edge_peek = now
        self._remember_cue("edge_peek")
        self._maybe_trace("dot", 0.35, (1, 2))
        return True

    def _maybe_window_perch(self) -> bool:
        settings = getattr(self._host, "_settings", None)
        if not getattr(settings, "context_perch_enabled", True):
            return False
        playtime = getattr(self._host, "_playtime", None)
        if playtime is None:
            return False
        try:
            ok = bool(playtime.maybe_perch())
            if ok:
                self._remember_cue("window_perch")
            return ok
        except Exception:
            logger.debug("boredom: window perch failed", exc_info=True)
            return False

    def _maybe_desk_habit(self, cat: str, dwell: float, idle: float, hour: int | None = None) -> bool:
        hour = datetime.now().hour if hour is None else hour
        cue = self._choose_life_cue(cat, dwell, idle, hour)
        if not cue:
            return False
        perform = random.choice(self._actions_for(cue, hour))
        feeder = getattr(self._host, "_feed_perform", None)
        if callable(feeder):
            feeder(perform)
        else:
            self._host._pet.perform(perform)
        self._remember_cue(cue)
        self._maybe_trace("star" if cue == "plain_idle" else "dot", 0.30, (1, 3))
        return True

    def _choose_life_cue(self, cat: str, dwell: float, idle: float, hour: int) -> str:
        candidates: list[str] = []
        night = hour >= 23 or hour < 6
        if night and idle >= _IDLE_S:
            candidates.append("plain_idle")
        if cat == "terminal" and idle >= _TERMINAL_IDLE_S:
            candidates.append("terminal_idle")
        if cat == "work" and idle >= _IDLE_S:
            candidates.append("work_idle")
        if cat == "drift" and dwell >= _DRIFT_DWELL_S and idle < _IDLE_S:
            candidates.append("drift_watch")
        if idle >= _IDLE_S:
            candidates.append("plain_idle")
        if not candidates:
            return ""
        for cue in candidates:
            if cue not in self._recent_cues:
                return cue
        return "" if candidates[0] == (self._recent_cues[-1] if self._recent_cues else "") else candidates[0]

    def _actions_for(self, cue: str, hour: int) -> tuple[str, ...]:
        if 6 <= hour < 9 and cue in _MORNING_ACTIONS:
            return _MORNING_ACTIONS[cue]
        if (hour >= 23 or hour < 6) and cue in _NIGHT_ACTIONS:
            return _NIGHT_ACTIONS[cue]
        return _CUE_ACTIONS.get(cue, _CUE_ACTIONS["plain_idle"])

    def _remember_cue(self, cue: str) -> None:
        self._recent_cues.append(cue)

    def _maybe_trace(self, kind: str, chance: float, count_range: tuple[int, int]) -> None:
        pet = getattr(self._host, "_pet", None)
        if pet is None or not hasattr(pet, "leave_life_trace"):
            return
        if random.random() > chance:
            return
        pet.leave_life_trace(kind, random.randint(*count_range))

    def _schedule_next(self, now: float) -> None:
        hour = datetime.now().hour
        if 23 <= hour or hour < 6:
            gap = random.uniform(600, 1200)
        else:
            gap = random.uniform(*_LIFE_CUE_GAP)
        self._next_life_at = now + gap

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
