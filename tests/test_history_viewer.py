"""Tests for history_viewer helper functions."""
from __future__ import annotations

import json
import time

from desktop_pet.pet.history_viewer import _extract_text, _fmt_time, _load_session


def test_extract_text_simple():
    assert _extract_text({"role": "user", "content": "hello"}) == "hello"


def test_extract_text_strips_emotion():
    assert _extract_text({"role": "assistant", "content": "[happy] hi there"}) == "hi there"


def test_extract_text_multimodal():
    msg = {"role": "user", "content": [
        {"type": "text", "text": "look at this"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}
    assert _extract_text(msg) == "look at this"


def test_extract_text_tool_calls():
    msg = {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "read_file"}}
    ]}
    result = _extract_text(msg)
    assert "read_file" in result


def test_extract_text_empty_content_no_tools():
    assert _extract_text({"role": "assistant", "content": ""}) == ""


def test_extract_text_non_string_content():
    assert _extract_text({"role": "user", "content": 123}) == ""


def test_fmt_time_zero():
    assert _fmt_time(0) == ""


def test_fmt_time_valid():
    result = _fmt_time(1719100800)
    assert ":" in result  # HH:MM format
    assert len(result) == 5


def test_load_session_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("desktop_pet.pet.history_viewer._SESSION_PATH", tmp_path / "nope.json")
    assert _load_session() is None


def test_load_session_expired(tmp_path, monkeypatch):
    p = tmp_path / "session.json"
    p.write_text(json.dumps({"saved_at": time.time() - 999999, "messages": []}))
    monkeypatch.setattr("desktop_pet.pet.history_viewer._SESSION_PATH", p)
    assert _load_session() is None


def test_load_session_fresh(tmp_path, monkeypatch):
    p = tmp_path / "session.json"
    p.write_text(json.dumps({"saved_at": time.time() - 60, "messages": [{"role": "user", "content": "hi"}]}))
    monkeypatch.setattr("desktop_pet.pet.history_viewer._SESSION_PATH", p)
    data = _load_session()
    assert data is not None
    assert len(data["messages"]) == 1


def test_load_session_corrupt_json(tmp_path, monkeypatch):
    p = tmp_path / "session.json"
    p.write_text("not json {{{")
    monkeypatch.setattr("desktop_pet.pet.history_viewer._SESSION_PATH", p)
    assert _load_session() is None
