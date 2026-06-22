from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from desktop_pet import tts


def _reset_tts():
    tts.set_enabled(False)
    tts._playing = False
    tts._current_stop = None
    tts._current_proc = None


def test_speak_is_gated_and_replaces_previous_request(monkeypatch):
    _reset_tts()
    calls = []

    class ThreadStub:
        def __init__(self, target, args, **_kwargs):
            calls.append((target, args))

        def start(self):
            pass

    monkeypatch.setattr(tts.threading, "Thread", ThreadStub)
    tts.speak("disabled")
    assert calls == []

    tts.set_enabled(True)
    tts.speak("first")
    first_stop = calls[0][1][2]
    tts.speak("second", "English")
    second_stop = calls[1][1][2]

    assert first_stop.is_set()
    assert not second_stop.is_set()
    assert calls[1][1][:2] == ("second", "English")


def test_generate_uses_edge_tts_without_network(monkeypatch):
    _reset_tts()

    class Communicate:
        def __init__(self, text, voice):
            assert (text, voice) == ("hello", "en-US-AnaNeural")

        async def stream(self):
            yield {"type": "audio", "data": b"abc"}
            yield {"type": "WordBoundary", "data": b""}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    path = asyncio.run(tts._generate("hello", "en-US-AnaNeural", threading.Event()))
    assert path is not None and Path(path).read_bytes() == b"abc"
    Path(path).unlink()


def test_speak_impl_selects_voice_and_cleans_cancelled_audio(tmp_path, monkeypatch):
    _reset_tts()
    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"audio")
    seen = []

    async def generate(_text, voice, stop_evt):
        seen.append(voice)
        stop_evt.set()
        return str(audio)

    monkeypatch.setattr(tts, "_generate", generate)
    stop_evt = threading.Event()
    tts._current_stop = stop_evt
    tts._speak_impl("こんにちは", "日本語", stop_evt)

    assert seen == ["ja-JP-NanamiNeural"]
    assert not audio.exists()
    assert tts._current_stop is None
    assert tts._playing is False


def test_speak_impl_failure_is_non_fatal(monkeypatch):
    _reset_tts()

    async def fail(*_args):
        raise RuntimeError("offline")

    monkeypatch.setattr(tts, "_generate", fail)
    stop_evt = threading.Event()
    tts._current_stop = stop_evt

    tts._speak_impl("hello", "English", stop_evt)

    assert tts._current_stop is None
    assert tts._playing is False


def test_stop_terminates_active_player():
    _reset_tts()

    class Proc:
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    proc = Proc()
    stop_evt = threading.Event()
    tts._current_stop = stop_evt
    tts._current_proc = proc

    tts.stop()

    assert stop_evt.is_set()
    assert proc.terminated
