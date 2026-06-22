"""Tests for boredom module classify and pick_mood logic."""
from __future__ import annotations

from desktop_pet.companions.boredom import Boredom, _classify


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
