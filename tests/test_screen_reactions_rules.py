"""Tests for screen_reactions keyword matching rules."""
from __future__ import annotations

from desktop_pet.companions.screen_reactions import _RULES


def _match(text: str) -> tuple[str | None, str | None]:
    """Simulate the rule matching logic from ScreenReactions._on_sampled."""
    lowered = text.lower()
    for keywords, reaction, i18n_key in _RULES:
        if any(kw.lower() in lowered for kw in keywords):
            return reaction, i18n_key
    return None, None


def test_detects_test_pass():
    reaction, key = _match("128 passed, 0 failed")
    assert reaction == "celebrate"
    assert key == "screen_test_pass"


def test_detects_error():
    reaction, key = _match("Error: FileNotFoundError")
    assert reaction == "droop"
    assert key == "screen_error"


def test_detects_traceback():
    reaction, key = _match("Traceback (most recent call last)")
    assert reaction == "droop"


def test_detects_building():
    reaction, key = _match("webpack building...")
    assert reaction == "read"
    assert key == "screen_building"


def test_detects_git():
    reaction, key = _match("git push origin main")
    assert reaction == "perk_up"
    assert key == "screen_git"


def test_detects_travel():
    reaction, key = _match("携程 - 机票预订 - 北京到上海")
    assert reaction == "peek"
    assert key == "screen_travel"


def test_no_match():
    reaction, key = _match("just some normal text about nothing")
    assert reaction is None
    assert key is None


def test_match_case_insensitive():
    reaction, key = _match("ALL PASSED IN GREEN")
    assert reaction == "celebrate"
