"""Short-lived foreground-project signal for local desktop ambience."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import presence, somatic
from desktop_pet.companions.context_classifier import classify_window

_POLL_MS = 30_000


@dataclass
class _ProjectSession:
    project_key: str
    display_name: str
    category: str
    started_at: float
    last_active: float


class ProjectTracker(QObject):
    """Track a coarse foreground-work signal without journaling window titles."""

    _sampled = Signal(str)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._busy = False
        self._sampled.connect(self._on_sampled)
        self._current: _ProjectSession | None = None
        self._sessions_today: list[dict] = []
        self._project_totals: dict[str, float] = {}

    def start(self) -> None:
        self._timer.start(_POLL_MS)

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self._busy = False
        self._current = None
        somatic.set_state("project", None)

    def current_project(self) -> str:
        if self._current and self._current.category in ("code", "terminal", "document"):
            return self._current.display_name
        return ""

    def current_session_minutes(self) -> float:
        if self._current:
            return (time.monotonic() - self._current.started_at) / 60.0
        return 0.0

    def today_summary(self) -> str:
        return ""

    def _tick(self) -> None:
        if self._busy:
            return
        settings = getattr(self._host, "_settings", None)
        if not getattr(settings, "boredom_enabled", True):
            return
        if not getattr(settings, "proactive_enabled", True):
            return
        pet = self._host._pet
        if not pet.isVisible() or pet.is_asleep:
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True, name="feixue-proj-tracker").start()

    def _probe(self) -> None:
        try:
            title = presence.foreground_window_title()
            self._sampled.emit(title[:200])
        except Exception:
            pass
        finally:
            self._busy = False

    @Slot(str)
    def _on_sampled(self, title: str) -> None:
        category = classify_window(title)
        project_key, display_name = self._extract_project(title, category)
        now = time.monotonic()

        if self._current and self._current.project_key == project_key:
            self._current.last_active = now
            return

        if self._current and now - self._current.started_at > 60:
            duration = now - self._current.started_at
            self._sessions_today.append({
                "project_key": self._current.project_key,
                "display_name": self._current.display_name,
                "category": self._current.category,
                "duration_s": duration,
            })
            key = self._current.project_key
            self._project_totals[key] = self._project_totals.get(key, 0) + duration

        self._current = _ProjectSession(
            project_key=project_key, display_name=display_name,
            category=category, started_at=now, last_active=now,
        )

    @staticmethod
    def _extract_project(title: str, category: str) -> tuple[str, str]:
        if not title.strip():
            return "idle", "idle"
        if category == "code":
            for sep in (" - ", " — "):
                parts = title.split(sep)
                if len(parts) >= 2:
                    candidate = parts[-2].strip() if len(parts) > 2 else parts[0].strip()
                    if candidate and len(candidate) < 50:
                        return _hash_key(candidate), candidate
        return _hash_key(title[:60]), category


def _hash_key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode("utf-8")).hexdigest()[:12]
