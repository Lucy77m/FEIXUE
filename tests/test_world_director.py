from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from desktop_pet.companions.world_director import WorldDirector
from desktop_pet.companions.workshop import WorkshopCtrl
from desktop_pet.world import WorldStore


class _Pet:
    is_asleep = False

    def isVisible(self):
        return True


class _Workshop:
    def __init__(self):
        self.calls = []

    def begin_revisit(self, item, use_ai, title):
        self.calls.append((item, use_ai, title))
        return True


class _Host:
    def __init__(self, configured=True):
        self._settings = SimpleNamespace(proactive_enabled=True, is_configured=configured)
        self._shown = True
        self._pet = _Pet()
        self._meeting_mode = False
        self._wellbeing = SimpleNamespace(in_flow=lambda: False)
        self._workshop = _Workshop()

    def _foreground_is_fullscreen(self):
        return False

    def _engaged(self):
        return False


def _book(store):
    item = store.create_reading("brief.md", "C:/alpha/brief.md")
    return store.complete(item.id, "private summary", "keepsake-id")


def test_world_director_uses_ai_only_under_daily_probability_gate(tmp_path, monkeypatch):
    store = WorldStore(tmp_path / "world.json")
    _book(store)
    host = _Host()
    monkeypatch.setattr("desktop_pet.companions.world_director.presence.idle_seconds", lambda: 1)
    monkeypatch.setattr("desktop_pet.companions.world_director.presence.foreground_window_title", lambda: "alpha - Code")
    director = WorldDirector(host, store, rng=lambda: 0.34)

    assert director.maybe_revisit(datetime(2026, 6, 22, 12, 0))
    assert host._workshop.calls[0][1:] == (True, "alpha - Code")


def test_world_director_refuses_when_user_is_away_or_unconfigured_ai(tmp_path, monkeypatch):
    store = WorldStore(tmp_path / "world.json")
    _book(store)
    host = _Host(configured=False)
    monkeypatch.setattr("desktop_pet.companions.world_director.presence.foreground_window_title", lambda: "alpha")
    monkeypatch.setattr("desktop_pet.companions.world_director.presence.idle_seconds", lambda: 500)
    director = WorldDirector(host, store, rng=lambda: 0.0)
    assert director.maybe_revisit(datetime(2026, 6, 22, 12, 0)) is False

    monkeypatch.setattr("desktop_pet.companions.world_director.presence.idle_seconds", lambda: 1)
    assert director.maybe_revisit(datetime(2026, 6, 22, 12, 0))
    assert host._workshop.calls[0][1] is False


def test_late_revisit_model_reply_is_consumed_after_timeout():
    ctrl = WorkshopCtrl.__new__(WorkshopCtrl)
    ctrl._discard_revisit_reply = True
    ctrl._active = False
    ctrl._mode = ""
    ctrl._waiting_ai = False

    assert ctrl.accept_revisit_reply("late model answer") is True
    assert ctrl._discard_revisit_reply is False
