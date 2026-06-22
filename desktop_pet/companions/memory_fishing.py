"""A three-round timing game that fishes memories from local history."""

from __future__ import annotations

import random

from PySide6.QtCore import QObject, QTimer, Slot

from desktop_pet import i18n, journal, keepsakes, stats
from desktop_pet.emotion.state import emotion
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.fishing_gauge import FishingGauge, FishingSummary


_ROUND_SPECS = (
    (0.23, 0.66, 4.5),
    (0.19, 0.84, 4.0),
    (0.15, 1.04, 3.5),
)
_EDGE_MARGIN = 0.04


class MemoryFishingCtrl(QObject):
    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._gauge = FishingGauge()
        self._summary = FishingSummary()
        from desktop_pet.eyes import capture
        capture.register_own_window(int(self._gauge.winId()))
        capture.register_own_window(int(self._summary.winId()))
        self._gauge.reeled.connect(self._on_reel)
        self._gauge.timed_out.connect(self._on_timeout)
        self._summary.view_requested.connect(self._view_memory)
        self._host._pet.moved.connect(self._follow)
        self._active = False
        self._owns_performance = False
        self._session_id = 0
        self._round = 0
        self._score = 0
        self._perfects = 0
        self._target = 0.5
        self._width = 0.2
        self._catches: list[dict] = []
        self._used_ids: set[str] = set()
        self._used_journal: set[str] = set()

    def is_active(self) -> bool:
        return self._active

    @Slot()
    def start(self) -> bool:
        if self._active:
            self._pop(i18n.t("fishing_already"))
            return False
        if (not self._host._shown or not self._host._pet.isVisible()
                or self._host._pet.is_asleep or self._host._engaged()):
            self._pop(i18n.t("fishing_busy"))
            return False
        self._summary.hide()
        self._active = True
        self._owns_performance = True
        self._session_id += 1
        self._round = 0
        self._score = 0
        self._perfects = 0
        self._catches = []
        self._used_ids = set()
        self._used_journal = set()
        self._host._pet.wake()
        self._host._pet.yield_performance()
        self._host._pet.perform("fish")
        self._pop(i18n.t("fishing_start"))
        self._next_round(self._session_id)
        return True

    def stop(self) -> None:
        self._session_id += 1
        self._active = False
        self._owns_performance = False
        self._gauge.stop_round()
        self._summary.hide()

    @staticmethod
    def score_marker(marker: float, target: float, width: float) -> int:
        distance = abs(float(marker) - float(target))
        if distance <= width / 8:
            return 100
        if distance <= width / 2:
            return 70
        if distance <= width / 2 + _EDGE_MARGIN:
            return 30
        return 0

    def _next_round(self, session_id: int) -> None:
        if not self._active or session_id != self._session_id:
            return
        if self._round >= len(_ROUND_SPECS):
            self._finish()
            return
        self._round += 1
        self._width, speed, duration = _ROUND_SPECS[self._round - 1]
        half = self._width / 2
        self._target = random.uniform(0.15 + half, 0.85 - half)
        self._gauge.begin(self._round, self._score, self._target, self._width, speed, duration)
        self._follow()

    @Slot(float)
    def _on_reel(self, marker: float) -> None:
        if not self._active:
            return
        points = self.score_marker(marker, self._target, self._width)
        self._score += points
        if points == 100:
            self._perfects += 1
        if points:
            caught = self._pick_catch()
            self._catches.append(caught)
            self._pop(i18n.t("fishing_caught").format(
                points=points, title=caught.get("title", "")))
        else:
            self._pop(i18n.t("fishing_missed"))
        session_id = self._session_id
        QTimer.singleShot(650, lambda: self._next_round(session_id))

    @Slot()
    def _on_timeout(self) -> None:
        if not self._active:
            return
        self._pop(i18n.t("fishing_timeout"))
        session_id = self._session_id
        QTimer.singleShot(650, lambda: self._next_round(session_id))

    def _pick_catch(self) -> dict:
        available = [item for item in keepsakes.recent(64) if item.get("id") not in self._used_ids]
        if available:
            item = dict(random.choice(available))
            self._used_ids.add(str(item.get("id", "")))
            return item
        memories = [item for item in journal.recent(20)
                    if item.get("text") and item.get("text") not in self._used_journal]
        if memories:
            entry = random.choice(memories)
            text = str(entry.get("text", ""))
            self._used_journal.add(text)
            return {
                "id": "", "kind": "journal",
                "title": i18n.t("fishing_journal_catch").format(text=text[:44]),
                "detail": text,
            }
        key = random.randint(1, 4)
        return {"id": "", "kind": "trinket", "title": i18n.t(f"fishing_trinket_{key}"), "detail": ""}

    def _finish(self) -> None:
        self._active = False
        result = stats.record_fishing(self._score, self._perfects)
        if result["bond_awarded"]:
            emotion.apply("played")
            selector.set_emotion(*emotion.snapshot())
        self._host._pet.react("celebrate" if result["new_best"] else "nod")
        screen = self._screen()
        self._summary.show_result(
            self._score, result["best"], result["new_best"], self._catches,
            self._host._pet, screen,
        )

    def consume_activity(self, name: str) -> bool:
        if name != "fish" or not self._owns_performance:
            return False
        self._owns_performance = False
        return True

    def _pop(self, message: str) -> None:
        if getattr(self._host, "_meeting_mode", False) or not getattr(self._host, "_shown", True):
            return
        thought = getattr(self._host, "_thought", None)
        if thought is not None:
            thought.pop(message, self._host._pet)
        else:
            self._host._feed_pop(message)

    @Slot(str)
    def _view_memory(self, item_id: str) -> None:
        if keepsakes.get(item_id) is None:
            return
        self._host._open_keepsake(item_id)

    @Slot()
    def _follow(self) -> None:
        screen = self._screen()
        if self._gauge.isVisible():
            self._gauge.follow(self._host._pet, screen)
        if self._summary.isVisible():
            from desktop_pet.pet.fx import place_beside_pet
            place_beside_pet(self._summary, self._host._pet, screen, prefer="left", gap=12)

    def _screen(self):
        return (self._host._app.screenAt(self._host._pet.frameGeometry().center())
                or self._host._app.primaryScreen()).availableGeometry()
