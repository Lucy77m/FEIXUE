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
_stop_evt = threading.Event()
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
    with _lock:
        if _playing:
            _stop_evt.set()
    threading.Thread(
        target=_speak_impl, args=(text, lang),
        daemon=True, name="feixue-tts",
    ).start()


def stop() -> None:
    """Request immediate stop of in-progress speech."""
    _stop_evt.set()


# ------------------------------------------------------------------
# Internal implementation
# ------------------------------------------------------------------

def _speak_impl(text: str, lang: str) -> None:
    global _playing
    _stop_evt.clear()
    _playing = True
    try:
        import asyncio
        voice = _VOICES.get(lang, _VOICES["中文"])
        mp3_path = asyncio.run(_generate(text, voice))
        if mp3_path and not _stop_evt.is_set():
            _play_file(mp3_path)
    except Exception:
        logger.debug("tts: playback failed", exc_info=True)
    finally:
        _playing = False


async def _generate(text: str, voice: str) -> str | None:
    """Generate MP3 to a temp file.  Returns the path or None."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    audio = bytearray()
    async for chunk in communicate.stream():
        if _stop_evt.is_set():
            return None
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    if not audio or _stop_evt.is_set():
        return None
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        os.write(fd, audio)
    finally:
        os.close(fd)
    return path


def _play_file(path: str) -> None:
    """Play an MP3 file using the best available system player."""
    try:
        # Try PowerShell (always available on Windows 10+)
        _stop_evt.wait(0.05)  # tiny yield
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
                        "while ($p.Position -lt $p.NaturalDuration.TimeSpan) {"
                        "  if (Test-Path env:FEIXUE_TTS_STOP) { $p.Stop(); break }"
                        "  Start-Sleep -Milliseconds 100"
                        "}"
                    )
                ),
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Poll for stop signal
        while proc.poll() is None:
            if _stop_evt.wait(0.15):
                os.environ["FEIXUE_TTS_STOP"] = "1"
                proc.terminate()
                break
        proc.wait(timeout=3)
    except Exception:
        logger.debug("tts: PowerShell playback failed", exc_info=True)
    finally:
        _cleanup_env()
        try:
            os.unlink(path)
        except OSError:
            pass


def _cleanup_env() -> None:
    os.environ.pop("FEIXUE_TTS_STOP", None)
