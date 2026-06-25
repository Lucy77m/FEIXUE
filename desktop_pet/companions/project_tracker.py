# 项目感知伴生 跟踪前台窗口识别当前项目 写入 somatic 和 journal

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import i18n, journal, somatic
from desktop_pet.companions.context_classifier import classify_window
from desktop_pet import presence

_POLL_MS = 30_000
_JOURNAL_COOLDOWN = 25 * 60  # 25 分钟内不重复写 journal


@dataclass
class _ProjectSession:
    project_key: str
    display_name: str
    category: str
    started_at: float
    last_active: float
    window_titles: deque = field(default_factory=lambda: deque(maxlen=10))


class ProjectTracker(QObject):
    """跟踪前台窗口 识别项目身份 注入 somatic 上下文"""

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
        self._last_journal_at: float = 0.0

    def start(self) -> None:
        self._timer.start(_POLL_MS)

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass

    # ── 公开 API ──────────────────────────────────────────

    def current_project(self) -> str:
        if self._current and self._current.category in ("code", "terminal", "document"):
            return self._current.display_name
        return ""

    def current_session_minutes(self) -> float:
        if self._current:
            return (time.monotonic() - self._current.started_at) / 60.0
        return 0.0

    def today_summary(self) -> str:
        lines: list[str] = []
        if self._current and self._current.category in ("code", "terminal", "document"):
            mins = int((time.monotonic() - self._current.started_at) / 60)
            if mins >= 2:
                lines.append(f"- {self._current.display_name}: {mins}min (ongoing)")
        for s in self._sessions_today[-5:]:
            mins = int(s["duration_s"] / 60)
            if mins >= 2:
                lines.append(f"- {s['display_name']}: {mins}min")
        return ("Today's projects:\n" + "\n".join(lines)) if lines else ""

    # ── 内部 ──────────────────────────────────────────────

    def _tick(self) -> None:
        if self._busy:
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
            self._current.window_titles.append(title[:120])
        else:
            # 关闭旧 session
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
            # 开新 session
            self._current = _ProjectSession(
                project_key=project_key, display_name=display_name,
                category=category, started_at=now, last_active=now,
                window_titles=deque([title[:120]], maxlen=10),
            )

        # 写 somatic
        if self._current and category in ("code", "terminal", "document"):
            mins = int((now - self._current.started_at) / 60)
            if mins >= 2:
                somatic.set_state("project", f"working on: {display_name} ({mins}min)")
                self._maybe_journal(display_name, mins)
        elif self._current:
            somatic.set_state("project", None)

    def _maybe_journal(self, display_name: str, mins: int) -> None:
        if mins < 30:
            return
        now = time.monotonic()
        if now - self._last_journal_at < _JOURNAL_COOLDOWN:
            return
        self._last_journal_at = now
        try:
            journal.add(i18n.t("proj_journal").format(name=display_name, m=mins))
        except Exception:
            pass

    @staticmethod
    def _extract_project(title: str, category: str) -> tuple[str, str]:
        if not title.strip():
            return "idle", "idle"
        # code IDE: "file.py - project - VS Code" → "project"
        if category == "code":
            for sep in (" - ", " — "):
                parts = title.split(sep)
                if len(parts) >= 2:
                    candidate = parts[-2].strip() if len(parts) > 2 else parts[0].strip()
                    if candidate and len(candidate) < 50:
                        return _hash_key(candidate), candidate
        # terminal/document/browser: 取标题前 30 字符做 display name
        display = title.strip()[:30]
        return _hash_key(title[:60]), display


def _hash_key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode("utf-8")).hexdigest()[:12]
