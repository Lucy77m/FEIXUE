from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet import journal, keepsakes, stats
from desktop_pet.companions.memory_fishing import MemoryFishingCtrl
from desktop_pet.emotion import state as emotion_mod
from desktop_pet.pet.window import PetWindow


def test_old_emotion_file_migrates_and_peak_stage_does_not_decay(tmp_path, monkeypatch):
    path = tmp_path / "emotion.json"
    path.write_text(json.dumps({
        "valence": 0.25,
        "arousal": 0.35,
        "rapport": 0.46,
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
    }), encoding="utf-8")
    monkeypatch.setattr(emotion_mod, "_STATE_PATH", path)

    engine = emotion_mod.EmotionEngine()
    bond = engine.bond_snapshot()

    assert bond["stage"] == "in_sync"
    assert bond["peak_rapport"] >= 0.46
    assert bond["rapport"] < bond["peak_rapport"]


def test_bond_stage_callback_fires_once_when_peak_crosses_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(emotion_mod, "_STATE_PATH", tmp_path / "emotion.json")
    engine = emotion_mod.EmotionEngine()
    engine._state.rapport = 0.299
    engine._state.peak_rapport = 0.299
    engine._state.updated_at = engine._now()
    unlocked = []
    engine.set_stage_callback(unlocked.append)

    engine.apply("interaction")
    engine.apply("interaction")

    assert unlocked == ["familiar"]
    assert engine.bond_snapshot()["stage"] == "familiar"


def test_fishing_score_tiers():
    assert MemoryFishingCtrl.score_marker(0.50, 0.50, 0.20) == 100
    assert MemoryFishingCtrl.score_marker(0.58, 0.50, 0.20) == 70
    assert MemoryFishingCtrl.score_marker(0.63, 0.50, 0.20) == 30
    assert MemoryFishingCtrl.score_marker(0.70, 0.50, 0.20) == 0


def test_fishing_stats_award_bond_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "_PATH", tmp_path / "stats.json")
    today = date(2026, 6, 22)

    first = stats.record_fishing(170, 1, today)
    second = stats.record_fishing(230, 2, today)

    assert first == {"score": 170, "best": 170, "new_best": True, "bond_awarded": True}
    assert second == {"score": 230, "best": 230, "new_best": True, "bond_awarded": False}
    assert stats.snapshot()["fishing_runs"] == 2
    assert stats.snapshot()["fishing_perfects"] == 3


def test_fishing_catches_do_not_repeat_keepsakes(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    monkeypatch.setattr(journal, "_PATH", tmp_path / "journal.json")
    keepsakes.add("file", "First", "one")
    keepsakes.add("file", "Second", "two")
    ctrl = MemoryFishingCtrl.__new__(MemoryFishingCtrl)
    ctrl._used_ids = set()
    ctrl._used_journal = set()
    monkeypatch.setattr("desktop_pet.companions.memory_fishing.random.choice", lambda items: items[0])

    first = ctrl._pick_catch()
    second = ctrl._pick_catch()

    assert first["id"] != second["id"]


def test_fishing_stop_cleans_visible_overlays():
    class Host:
        def __init__(self):
            self._app = QApplication.instance()
            self._pet = PetWindow("xiaofeixue")
            self._pet.show()
            self._shown = True
            self._settings = SimpleNamespace()

        def _engaged(self):
            return False

        def _feed_pop(self, _message):
            pass

    host = Host()
    ctrl = MemoryFishingCtrl(host)
    ctrl._active = True
    ctrl._gauge.begin(1, 0, 0.5, 0.2, 0.6, 5.0)
    QApplication.processEvents()

    ctrl.stop()

    assert ctrl.is_active() is False
    assert ctrl._gauge.isVisible() is False
    assert ctrl._summary.isVisible() is False
