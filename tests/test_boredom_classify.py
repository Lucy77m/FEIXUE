"""Tests for boredom module classify and pick_mood logic."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

import desktop_pet.companions.boredom as boredom_mod
from desktop_pet.companions.boredom import Boredom, _classify

if QApplication.instance() is None:
    QApplication([])


class _Wellbeing:
    def __init__(self):
        self.flow = False

    def in_flow(self):
        return self.flow


class _Pet:
    def __init__(self):
        self.visible = True
        self.is_asleep = False
        self.is_life_busy = False
        self.performs = []
        self.edge_peeks = []
        self.notices = []
        self.traces = []

    def isVisible(self):
        return self.visible

    def perform(self, name):
        self.performs.append(name)
        return True

    def start_edge_peek(self, edge, duration):
        self.edge_peeks.append((edge, duration))
        return True

    def frameGeometry(self):
        return QRect(0, 0, 100, 100)

    def life_notice_cursor(self, pos, lingered=False, shy=False):
        self.notices.append((pos, lingered, shy))
        return True

    def leave_life_trace(self, kind="dot", count=1):
        self.traces.append((kind, count))
        return True


class _Host:
    def __init__(self):
        self._settings = SimpleNamespace(
            boredom_enabled=True,
            proactive_enabled=True,
            context_perch_enabled=True,
        )
        self._shown = True
        self._meeting_mode = False
        self._pet = _Pet()
        self._wellbeing = _Wellbeing()
        self._playtime = SimpleNamespace(maybe_perch=lambda: False)
        self.performs = []

    def _engaged(self):
        return False

    def _foreground_is_fullscreen(self):
        return False

    def _feed_perform(self, name):
        self.performs.append(name)


def test_classify_terminal():
    assert _classify("Windows PowerShell") == "terminal"


def test_classify_work():
    assert _classify("main.py - Visual Studio Code") == "work"


def test_classify_drift():
    assert _classify("YouTube - funny cats") == "drift"


def test_classify_idle():
    assert _classify("Desktop") == "idle"


def test_classify_empty():
    assert _classify("") == "idle"


def test_classify_social_as_drift():
    assert _classify("reddit - front page") == "drift"


def test_pick_mood_terminal_idle():
    assert Boredom._pick_mood("terminal", 100, 100) == "terminal"


def test_pick_mood_terminal_not_idle():
    assert Boredom._pick_mood("terminal", 100, 10) == ""


def test_pick_mood_work_idle():
    assert Boredom._pick_mood("work", 100, 300) == "stuck"


def test_pick_mood_drift_active():
    assert Boredom._pick_mood("drift", 1300, 30) == "drift"


def test_pick_mood_drift_short_dwell():
    assert Boredom._pick_mood("drift", 100, 30) == ""


def test_pick_mood_general_idle():
    assert Boredom._pick_mood("idle", 100, 300) == "idle"


def test_pick_mood_not_idle_enough():
    assert Boredom._pick_mood("idle", 10, 10) == ""


def test_life_director_blocks_busy_states():
    host = _Host()
    boredom = Boredom(host)

    assert boredom._life_available()
    host._pet.is_life_busy = True
    assert not boredom._life_available()
    host._pet.is_life_busy = False
    host._meeting_mode = True
    assert not boredom._life_available()
    host._meeting_mode = False
    host._wellbeing.flow = True
    assert not boredom._life_available()


def test_life_director_can_start_edge_peek_once():
    host = _Host()
    boredom = Boredom(host)

    assert boredom._maybe_edge_peek(1000.0)
    assert host._pet.edge_peeks
    assert not boredom._maybe_edge_peek(1001.0)


def test_life_director_triggers_quiet_desk_habit_without_bubble():
    host = _Host()
    host._pet.start_edge_peek = lambda _edge, _duration: False
    boredom = Boredom(host)
    boredom._next_life_at = 0.0

    boredom._on_sampled("main.py - Visual Studio Code", 300.0)

    assert host.performs


def test_life_director_choose_cue_avoids_immediate_repeat_and_quiets_night():
    host = _Host()
    boredom = Boredom(host)

    assert boredom._choose_life_cue("terminal", 120, 120, 14) == "terminal_idle"
    boredom._remember_cue("terminal_idle")
    assert boredom._choose_life_cue("terminal", 120, 120, 14) == ""
    assert boredom._choose_life_cue("terminal", 120, 300, 23) == "plain_idle"


def test_cursor_attention_has_linger_and_shy_cooldowns(monkeypatch):
    host = _Host()
    boredom = Boredom(host)
    monkeypatch.setattr(boredom_mod, "QCursor", SimpleNamespace(pos=lambda: QPoint(10, 10)))

    assert not boredom._maybe_cursor_attention(10.0)
    assert host._pet.notices[-1][1:] == (False, False)
    assert boredom._maybe_cursor_attention(12.2)
    assert host._pet.notices[-1][1:] == (True, False)
    assert boredom._maybe_cursor_attention(18.1)
    assert host._pet.notices[-1][1:] == (False, True)
