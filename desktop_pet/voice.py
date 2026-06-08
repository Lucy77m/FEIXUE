# author: bdth
# email: 2074055628@qq.com
# 语音朗读(TTS)：可切换 Edge TTS / 系统 SAPI 两种后端。

from __future__ import annotations

import os
import queue
import re
import tempfile
import threading

_queue: "queue.Queue[tuple]" = queue.Queue()
_enabled = False
_started = False
_lock = threading.Lock()
_stop = threading.Event()
_shutdown = threading.Event()
_worker_thread: "threading.Thread | None" = None

_voice = ""
_rate = 0

SYSTEM_VOICE = ""
EDGE_VOICES: list[tuple[str, str]] = [
    ("zh-CN-XiaoxiaoNeural", "晓晓 Xiaoxiao · 温柔"),
    ("zh-CN-XiaoyiNeural", "晓伊 Xiaoyi · 活泼"),
    ("zh-CN-YunxiNeural", "云希 Yunxi · 少年"),
    ("zh-CN-YunyangNeural", "云扬 Yunyang · 播音"),
    ("zh-CN-YunjianNeural", "云健 Yunjian · 浑厚"),
    ("zh-CN-YunxiaNeural", "云夏 Yunxia · 童声"),
    ("zh-CN-liaoning-XiaobeiNeural", "小北 Xiaobei · 东北"),
    ("zh-CN-shaanxi-XiaoniNeural", "晓妮 Xiaoni · 陕西"),
]

_TAG = re.compile(r"^\s*\[(\w+)\]\s*")
_MD = re.compile(r"[*#`>~_|]+")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\U00002300-\U000023FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D\U000020E3"
    "\U00002122\U00002139\U0000203C\U00002049"
    "\U00003030\U0000303D\U00003297\U00003299"
    "]+",
    flags=re.UNICODE,
)


def _clean(text: str) -> str:
    text = _LINK.sub(r"\1", text or "")
    text = _TAG.sub("", text)
    text = _MD.sub("", text)
    text = _EMOJI.sub("", text)
    return " ".join(text.split())[:600]


def is_enabled() -> bool:
    return _enabled


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)
    if _enabled:
        _ensure()
    else:
        flush()


def set_voice(voice_id: str) -> None:
    global _voice
    _voice = voice_id or ""


def set_rate(percent) -> None:
    global _rate
    try:
        _rate = max(-50, min(50, int(percent)))
    except (TypeError, ValueError):
        _rate = 0


def current_voice() -> str:
    return _voice


_edge_ok: "bool | None" = None


def edge_available() -> bool:
    """edge-tts 是否可用(装了包)。"""
    global _edge_ok
    if _edge_ok is None:
        try:
            import edge_tts
            _edge_ok = True
        except Exception:
            _edge_ok = False
    return _edge_ok


def _ensure() -> None:
    global _started, _worker_thread
    with _lock:
        if _started:
            return
        _started = True
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="mochi-tts")
    _worker_thread.start()


def _select_voice(sp) -> None:
    try:
        for v in sp.GetVoices():
            desc = v.GetDescription() or ""
            if any(k in desc for k in ("Chinese", "中文", "Huihui", "Yaoyao", "Kangkang", "Xiaoxiao")):
                sp.Voice = v
                return
    except Exception:
        pass


def _edge_say(text: str, voice_id: str, rate: int) -> None:
    """Edge TTS：合成 mp3 → MCI 阻塞播放。"""
    import asyncio

    import edge_tts

    path = os.path.join(tempfile.gettempdir(), "mochi_tts.mp3")
    rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"

    async def _go() -> None:
        comm = edge_tts.Communicate(text, voice_id, rate=rate_str)
        await comm.save(path)

    _mci_close()
    asyncio.run(_go())
    _play_file(path)


def _mci(cmd: str) -> int:
    import ctypes
    return ctypes.windll.winmm.mciSendStringW(cmd, None, 0, 0)


def _mci_close() -> None:
    try:
        _mci("close mochitts")
    except Exception:
        pass


def _mci_status(what: str) -> str:
    import ctypes
    buf = ctypes.create_unicode_buffer(128)
    ctypes.windll.winmm.mciSendStringW(f"status mochitts {what}", buf, 128, 0)
    return buf.value


def _play_file(path: str) -> None:
    """用 winmm(MCI) 播放音频文件。"""
    import time as _t

    if _mci(f'open "{path}" type mpegvideo alias mochitts') != 0:
        if _mci(f'open "{path}" alias mochitts') != 0:
            raise RuntimeError("MCI open failed")
    try:
        if _mci("play mochitts") != 0:
            raise RuntimeError("MCI play failed")
        while _mci_status("mode") == "playing":
            if _stop.is_set():
                _mci("stop mochitts")
                break
            _t.sleep(0.05)
    finally:
        _mci_close()


def _apply_sapi_rate(sp, percent: int) -> None:
    try:
        sp.Rate = max(-10, min(10, round(percent / 5)))
    except Exception:
        pass


_SVSF_ASYNC = 1
_SVSF_PURGE = 3


def _sapi_speak(sp, text: str) -> None:
    """异步念 + 轮询，让 flush() 能中途打断(_stop)。"""
    try:
        sp.Speak(text, _SVSF_ASYNC)
    except Exception:
        return
    try:
        while not sp.WaitUntilDone(80):
            if _stop.is_set():
                try:
                    sp.Speak("", _SVSF_PURGE)
                except Exception:
                    pass
                return
    except Exception:
        try:
            sp.WaitUntilDone(-1)
        except Exception:
            pass


def _worker() -> None:
    sp = None
    sapi_ready = False

    def sapi():
        nonlocal sp, sapi_ready
        if not sapi_ready:
            sapi_ready = True
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                sp = win32com.client.Dispatch("SAPI.SpVoice")
                _select_voice(sp)
            except Exception:
                sp = None
        return sp

    while True:
        text, on_done, voice, rate = _queue.get()
        if _shutdown.is_set():
            try:
                if sp is not None:
                    sp.Speak("", _SVSF_PURGE)
            except Exception:
                pass
            _mci_close()
            if sapi_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            return
        _stop.clear()
        if text and not _stop.is_set():
            played = False
            if voice and edge_available():
                try:
                    _edge_say(text, voice, rate)
                    played = True
                except Exception:
                    played = False
            if not played:
                cur = sapi()
                if cur is not None:
                    try:
                        _apply_sapi_rate(cur, rate)
                        _sapi_speak(cur, text)
                    except Exception:
                        pass
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def _enqueue(cleaned: str, on_done, voice: str, rate: int) -> None:
    _ensure()
    _queue.put((cleaned, on_done, voice, rate))


def speak(text: str) -> None:
    if not _enabled:
        return
    cleaned = _clean(text)
    if cleaned:
        _enqueue(cleaned, None, _voice, _rate)


def speak_one(text: str, on_done=None) -> None:
    """念单独一句，念完后回调 on_done()(在 TTS 线程内)。"""
    cleaned = _clean(text) if _enabled else ""
    if not _enabled or not cleaned:
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass
        return
    _enqueue(cleaned, on_done, _voice, _rate)


def preview(text: str, voice: str, rate, on_done=None) -> None:
    """试听：用指定音色/语速念一句，无视开关、也不改动当前设置。"""
    try:
        rate = max(-50, min(50, int(rate)))
    except (TypeError, ValueError):
        rate = 0
    cleaned = _clean(text)
    if not cleaned:
        if on_done is not None:
            on_done()
        return
    _enqueue(cleaned, on_done, voice or "", rate)


def flush() -> None:
    """置打断信号(停掉正在念的那句) + 清空待播队列，并补调被丢弃项的 on_done。"""
    _stop.set()
    drained = []
    try:
        while True:
            drained.append(_queue.get_nowait())
    except queue.Empty:
        pass
    for item in drained:
        on_done = item[1] if isinstance(item, tuple) and len(item) >= 2 else None
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def shutdown() -> None:
    """退出前调：停掉正在念的、清队列、让 worker 在自己的线程里 CoUninitialize 后退出。"""
    _shutdown.set()
    _stop.set()
    try:
        while True:
            _queue.get_nowait()
    except queue.Empty:
        pass
    try:
        _queue.put_nowait((None, None, "", 0))
    except Exception:
        pass
    t = _worker_thread
    if t is not None and t.is_alive():
        t.join(timeout=1.5)
