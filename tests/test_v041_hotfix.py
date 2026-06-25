from __future__ import annotations

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QRect, Signal
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet import somatic
from desktop_pet.app.lifecycle import LifecycleMixin
from desktop_pet.companions.memory_weather import MemoryWeather
from desktop_pet.companions.project_tracker import ProjectTracker
from desktop_pet.pet.workshop import WorkshopWindow
from desktop_pet.world import WorldObject


class _Pet(QObject):
    moved = Signal()

    def __init__(self):
        super().__init__()
        self.visible = True
        self.is_asleep = False
        self.weather = "rain"
        self.visible_set = []

    def isVisible(self):
        return self.visible

    def frameGeometry(self):
        return QRect(0, 0, 100, 100)

    def set_mood_weather(self, kind):
        self.weather = kind

    def wake(self):
        pass

    def setVisible(self, visible):
        self.visible = visible
        self.visible_set.append(visible)

    def clear_pending(self):
        pass


class _Overlay:
    def __init__(self):
        self.hidden = False

    def hide_layer(self):
        self.hidden = True


def test_memory_weather_stop_clears_overlay_pet_and_somatic():
    somatic.clear()
    host = SimpleNamespace(_pet=_Pet())
    weather = MemoryWeather(host)
    weather._overlay = _Overlay()
    weather._current = "rain"
    somatic.set_state("mweather", "memory weather: rain")

    weather.stop()

    assert weather.current_weather() == "clear"
    assert weather._overlay.hidden is True
    assert host._pet.weather == ""
    assert not somatic.has_state("mweather")


def test_project_tracker_is_gated_and_does_not_write_somatic_or_journal(monkeypatch):
    somatic.clear()
    pet = _Pet()
    host = SimpleNamespace(
        _pet=pet,
        _settings=SimpleNamespace(boredom_enabled=False, proactive_enabled=True),
    )
    tracker = ProjectTracker(host)
    probed = []
    monkeypatch.setattr(tracker, "_probe", lambda: probed.append(True))

    tracker._tick()

    assert probed == []
    assert tracker._current is None

    host._settings.boredom_enabled = True
    tracker._on_sampled("main.py - alpha - Visual Studio Code")
    tracker._current.started_at = time.monotonic() - 31 * 60
    tracker._on_sampled("other.py - beta - Visual Studio Code")

    assert tracker.current_project() == "beta"
    assert not somatic.has_state("project")
    assert tracker.today_summary() == ""


def test_project_tracker_stop_clears_current_and_somatic():
    somatic.clear()
    host = SimpleNamespace(
        _pet=_Pet(),
        _settings=SimpleNamespace(boredom_enabled=True, proactive_enabled=True),
    )
    tracker = ProjectTracker(host)
    tracker._on_sampled("main.py - alpha - Visual Studio Code")
    somatic.set_state("project", "working on: alpha")

    tracker.stop()

    assert tracker._current is None
    assert not somatic.has_state("project")


def test_lifecycle_power_toggles_memory_weather_and_project_tracker(monkeypatch):
    class Toggle:
        def __init__(self):
            self.starts = 0
            self.stops = 0

        def start(self):
            self.starts += 1

        def stop(self):
            self.stops += 1

    class Noop:
        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

        def isVisible(self):
            return False

    class Event:
        def __init__(self):
            self.sets = 0

        def set(self):
            self.sets += 1

    class Host(LifecycleMixin):
        def __init__(self):
            self._shown = False
            self._cancelling = False
            self._worker = Noop()
            self._confirm_result = None
            self._confirm_event = Event()
            self._confirm_box = Noop()
            self._speech = Noop()
            self._media = Noop()
            self._todo = Noop()
            self._control_hide_timer = Noop()
            self._control_hint = Noop()
            self._input = Noop()
            self._pending_bg = []
            self._pet = _Pet()
            self._workflow = Toggle()
            self._fishing = Toggle()
            self._workshop = Toggle()
            self._world_director = Toggle()
            self._memory_weather = Toggle()
            self._project_tracker = Toggle()
            self._just_returned = False

        def _bring_online(self):
            self._pet.setVisible(True)

        def _drain_reminders(self):
            pass

        def _requeue_timed(self):
            pass

        def _on_busy(self, _busy):
            pass

        def _reset_lecture(self):
            pass

    monkeypatch.setattr("desktop_pet.app.lifecycle.emotion.apply", lambda _name: None)
    monkeypatch.setattr("desktop_pet.app.lifecycle.emotion.snapshot", lambda: (0.0, 0.0, 0.0))
    monkeypatch.setattr("desktop_pet.app.lifecycle.selector.set_emotion", lambda *_args: None)
    monkeypatch.setattr("desktop_pet.app.lifecycle.radar.reset", lambda: None)

    host = Host()
    host._power_on()
    host._power_off()

    assert host._memory_weather.starts == 1
    assert host._project_tracker.starts == 1
    assert host._memory_weather.stops == 1
    assert host._project_tracker.stops == 1
    assert host._pet.visible is False


def test_dream_motif_index_is_stable():
    item = WorldObject(
        id="dream1", kind="dream", title="dream", summary="same moonlit dream",
        source="", project_key="dream", state="shelved", zone="shelf", slot=0,
        placement="auto", origin_keepsake_id="", created_at="", updated_at="",
        last_revisited_at="", revisit_count=0,
    )

    first = WorkshopWindow._dream_motif_idx(item)
    second = WorkshopWindow._dream_motif_idx(item)

    assert first == second
    assert 0 <= first < len(WorkshopWindow._DREAM_MOTIFS)
