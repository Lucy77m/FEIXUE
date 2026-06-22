"""Low-frequency autonomous revisits to books in the desk workshop."""

from __future__ import annotations

import logging
import random
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import presence
from desktop_pet.world import WorldStore, get_world


_CHECK_MS = 10 * 60 * 1000
_PRESENT_IDLE_S = 180


class WorldDirector(QObject):
    _sampled = Signal(str)

    def __init__(self, host, store: WorldStore | None = None, rng=None) -> None:
        super().__init__()
        self._host = host
        self._store = store or get_world()
        self._random = rng or random.random
        self._busy = False
        self._sampled.connect(self._on_sampled)
        self._timer = QTimer(self)
        self._timer.setInterval(_CHECK_MS)
        self._timer.timeout.connect(self.maybe_revisit)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def maybe_revisit(self, now: datetime | None = None) -> bool:
        # When called from QTimer (now=None), offload blocking calls to a
        # background thread.  When called from tests with an explicit *now*,
        # run synchronously so assertions can inspect the return value.
        if now is not None:
            return self._do_revisit(now)
        if self._busy:
            return False
        if not self._eligible():
            return False
        self._busy = True
        threading.Thread(target=self._probe, daemon=True, name="feixue-world-director").start()
        return False

    def _probe(self) -> None:
        try:
            title = presence.foreground_window_title()
            idle = presence.idle_seconds()
            if idle >= _PRESENT_IDLE_S:
                return
            self._sampled.emit(title[:120])
        except Exception:
            logger.debug("world_director: probe failed", exc_info=True)
        finally:
            self._busy = False

    @Slot(str)
    def _on_sampled(self, title: str) -> None:
        self._do_revisit(datetime.now(), title=title)

    def _do_revisit(self, now: datetime, title: str = "") -> bool:
        if not self._eligible():
            return False
        if not title:
            title = presence.foreground_window_title()[:120]
        if presence.idle_seconds() >= _PRESENT_IDLE_S:
            return False
        if not self._store.revisit_allowed(now):
            return False
        item = self._store.choose_revisit(title, now)
        if item is None:
            return False
        use_ai = bool(
            self._host._settings.is_configured
            and self._store.ai_revisit_allowed(now)
            and self._random() < 0.35
        )
        return self._host._workshop.begin_revisit(item, use_ai, title)

    def _eligible(self) -> bool:
        host = self._host
        return bool(
            host._settings.proactive_enabled
            and host._shown
            and host._pet.isVisible()
            and not host._pet.is_asleep
            and not host._meeting_mode
            and not host._foreground_is_fullscreen()
            and not host._wellbeing.in_flow()
            and not host._engaged()
        )
