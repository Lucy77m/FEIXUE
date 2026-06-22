"""Text-to-speech output using edge-tts.

Generates audio in a background thread and plays it via a temp file
and the system's default audio player.  Falls back gracefully when
edge-tts is not installed or network is unavailable.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading

logger = logging.getLogger(__name__)

# Language → Edge TTS voice name
_VOICES: dict[str, str] = {
    "中文": "zh-CN-XiaoyiNeural",
    "English": "en-US-AnaNeural",
    "日本語": "ja-JP-NanamiNeural",
}

_enabled = False
_playing = False
_current_stop: threading.Event | None = None
_current_proc: subprocess.Popen | None = None
_lock = threading.Lock()


def set_enabled(on: bool) -> None:
    """Toggle TTS on/off.  Called from settings live-reload."""
    global _enabled
    _enabled = on


def is_ready() -> bool:
    """Check whether edge-tts can be imported."""
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def speak(text: str, lang: str = "中文") -> None:
    """Speak *text* asynchronously.  Non-blocking — spawns a daemon thread."""
    if not _enabled or not text.strip():
        return
    global _current_stop
    with _lock:
        if _current_stop is not None:
            _current_stop.set()
        stop_evt = threading.Event()
        _current_stop = stop_evt
    threading.Thread(
        target=_speak_impl, args=(text, lang, stop_evt),
        daemon=True, name="feixue-tts",
    ).start()


def stop() -> None:
    """Request immediate stop of in-progress speech."""
    with _lock:
        if _current_stop is not None:
            _current_stop.set()
        proc = _current_proc
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass


# ------------------------------------------------------------------
# Internal implementation
# ------------------------------------------------------------------

def _speak_impl(text: str, lang: str, stop_evt: threading.Event) -> None:
    global _playing, _current_stop
    with _lock:
        if _current_stop is not stop_evt:
            return
        _playing = True
    try:
        import asyncio
        voice = _VOICES.get(lang, _VOICES["中文"])
        mp3_path = asyncio.run(_generate(text, voice, stop_evt))
        if mp3_path and not stop_evt.is_set():
            _play_file(mp3_path, stop_evt)
        elif mp3_path:
            try:
                os.unlink(mp3_path)
            except OSError:
                pass
    except Exception:
        logger.debug("tts: playback failed", exc_info=True)
    finally:
        with _lock:
            if _current_stop is stop_evt:
                _current_stop = None
                _playing = False


async def _generate(text: str, voice: str, stop_evt: threading.Event) -> str | None:
    """Generate MP3 to a temp file.  Returns the path or None."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    audio = bytearray()
    async for chunk in communicate.stream():
        if stop_evt.is_set():
            return None
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    if not audio or stop_evt.is_set():
        return None
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        os.write(fd, audio)
    finally:
        os.close(fd)
    return path


def _play_file(path: str, stop_evt: threading.Event) -> None:
    """Play an MP3 file using the best available system player."""
    try:
        # Try PowerShell (always available on Windows 10+)
        stop_evt.wait(0.05)  # tiny yield
        proc = subprocess.Popen(
            [
                "powershell", "-NoProfile", "-Command",
                (
                    f"(New-Object Media.SoundPlayer '{path}').PlaySync()"
                    if path.endswith(".wav") else
                    (
                        "Add-Type -AssemblyName presentationCore; "
                        f"$p = New-Object System.Windows.Media.MediaPlayer; "
                        f"$p.Open([uri]'{path}'); "
                        "$p.Play(); "
                        "Start-Sleep -Milliseconds 200; "
                        "while ($p.Position -lt $p.NaturalDuration.TimeSpan) { Start-Sleep -Milliseconds 100 }"
                    )
                ),
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        global _current_proc
        with _lock:
            if _current_stop is stop_evt:
                _current_proc = proc
        while proc.poll() is None:
            if stop_evt.wait(0.15):
                proc.terminate()
                break
        proc.wait(timeout=3)
    except Exception:
        logger.debug("tts: PowerShell playback failed", exc_info=True)
    finally:
        with _lock:
            if _current_proc is locals().get("proc"):
                _current_proc = None
        try:
            os.unlink(path)
        except OSError:
            pass
