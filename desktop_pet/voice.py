# author: bdth
# email: 2074055628@qq.com
# 语音朗读 本机系统嗓子(Windows SAPI) 离线零依赖
# 不带逐字时间戳 字幕由气泡端打字机自己走

from __future__ import annotations

import queue
import re
import threading

_queue: "queue.Queue[tuple]" = queue.Queue()
_enabled = False
_started = False
_lock = threading.Lock()
_stop = threading.Event()
_shutdown = threading.Event()
_worker_thread: "threading.Thread | None" = None

_rate = 0

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
    """念之前洗掉 markdown emoji 和链接"""
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


def set_rate(percent) -> None:
    global _rate
    try:
        _rate = max(-50, min(50, int(percent)))
    except (TypeError, ValueError):
        _rate = 0


def _ensure() -> None:
    global _started, _worker_thread
    with _lock:
        if _started:
            return
        _started = True
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="mochi-tts")
    _worker_thread.start()


def _select_voice(sp) -> None:
    """给 sapi 挑一个中文嗓"""
    try:
        for v in sp.GetVoices():
            desc = v.GetDescription() or ""
            if any(k in desc for k in ("Chinese", "中文", "Huihui", "Yaoyao", "Kangkang", "Xiaoxiao")):
                sp.Voice = v
                return
    except Exception:
        pass


def _apply_sapi_rate(sp, percent: int) -> None:
    try:
        sp.Rate = max(-10, min(10, round(percent / 5)))
    except Exception:
        pass


_SVSF_ASYNC = 1
_SVSF_PURGE = 3


def _sapi_speak(sp, text: str) -> None:
    """异步念加轮询 支持中途打断"""
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
    """tts 工作线程 串行消费队列逐句念"""
    sp = None
    sapi_ready = False

    def sapi():
        nonlocal sp, sapi_ready
        if not sapi_ready:
            sapi_ready = True  # 失败也置位 不每句重试
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
        text, on_start, on_progress, on_done, rate = _queue.get()
        if _shutdown.is_set():
            try:
                if sp is not None:
                    sp.Speak("", _SVSF_PURGE)
            except Exception:
                pass
            if sapi_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            return
        _stop.clear()
        started = False
        if text and not _stop.is_set():
            cur = sapi()
            if cur is not None:
                try:
                    _apply_sapi_rate(cur, rate)
                    if on_start is not None:
                        on_start()
                        started = True
                    _sapi_speak(cur, text)
                except Exception:
                    pass
        if not started and on_start is not None:
            try:
                on_start()
            except Exception:
                pass
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def _enqueue(cleaned: str, on_start, on_progress, on_done, rate: int) -> None:
    _ensure()
    _queue.put((cleaned, on_start, on_progress, on_done, rate))


def speak(text: str) -> None:
    if not _enabled:
        return
    cleaned = _clean(text)
    if cleaned:
        _enqueue(cleaned, None, None, None, _rate)


def speak_one(text: str, on_start=None, on_progress=None, on_done=None) -> None:
    """念一句 开口和念完回调驱动气泡翻页 字幕由打字机自己走"""
    cleaned = _clean(text) if _enabled else ""
    if not _enabled or not cleaned:
        for cb in (on_start, on_done):
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
        return
    _enqueue(cleaned, on_start, on_progress, on_done, _rate)


def preview(text: str, rate, on_done=None) -> None:
    """按指定语速试听一句"""
    try:
        rate = max(-50, min(50, int(rate)))
    except (TypeError, ValueError):
        rate = 0
    cleaned = _clean(text)
    if not cleaned:
        if on_done is not None:
            on_done()
        return
    _enqueue(cleaned, None, None, on_done, rate)


def flush() -> None:
    """打断当前句并清空队列"""
    _stop.set()
    drained = []
    try:
        while True:
            drained.append(_queue.get_nowait())
    except queue.Empty:
        pass
    for item in drained:
        on_done = item[3] if isinstance(item, tuple) and len(item) >= 4 else None
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def shutdown() -> None:
    """退出前停掉朗读并收掉 worker"""
    _shutdown.set()
    _stop.set()
    try:
        while True:
            _queue.get_nowait()
    except queue.Empty:
        pass
    try:
        _queue.put_nowait((None, None, None, None, 0))
    except Exception:
        pass
    t = _worker_thread
    if t is not None and t.is_alive():
        t.join(timeout=1.5)
