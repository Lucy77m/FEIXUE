# author: bdth
# email: 2074055628@qq.com
# 语音朗读 edge tts 和系统 sapi 两种后端

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
_file_seq = 0
_EDGE_SYNTH_TIMEOUT = 25.0

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


def set_voice(voice_id: str) -> None:
    global _voice
    _voice = voice_id or ""


def set_rate(percent) -> None:
    global _rate
    try:
        _rate = max(-50, min(50, int(percent)))
    except (TypeError, ValueError):
        _rate = 0


_edge_ok: "bool | None" = None


def edge_available() -> bool:
    """探一次 edge tts 装没装并缓存"""
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
    """给 sapi 挑一个中文嗓"""
    try:
        for v in sp.GetVoices():
            desc = v.GetDescription() or ""
            if any(k in desc for k in ("Chinese", "中文", "Huihui", "Yaoyao", "Kangkang", "Xiaoxiao")):
                sp.Voice = v
                return
    except Exception:
        pass


def _synth_edge(text: str, voice_id: str, rate: int) -> tuple[str, list[tuple[float, int]]] | None:
    """edge tts 合成 收音频和逐词时间戳"""
    import asyncio
    import edge_tts

    global _file_seq
    rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
    audio = bytearray()
    words: list[tuple[float, str]] = []

    async def _consume() -> None:
        comm = edge_tts.Communicate(text, voice_id, rate=rate_str)
        async for chunk in comm.stream():
            kind = chunk.get("type")
            if kind == "audio" and chunk.get("data"):
                audio.extend(chunk["data"])
            elif kind == "WordBoundary":
                # offset 单位 100ns 转毫秒
                words.append((chunk.get("offset", 0) / 10000.0, chunk.get("text", "")))

    async def _go() -> None:
        await asyncio.wait_for(_consume(), timeout=_EDGE_SYNTH_TIMEOUT)

    asyncio.run(_go())
    if not audio:
        return None
    with _lock:
        _file_seq += 1
        seq = _file_seq
    path = os.path.join(tempfile.gettempdir(), f"mochi_tts_{seq}.mp3")
    with open(path, "wb") as fh:
        fh.write(bytes(audio))

    # 按词长占比把进度摊回 text 字符数
    total_wlen = sum(len(w) for _, w in words) or 1
    n = len(text)
    cum = 0
    marks: list[tuple[float, int]] = []
    for off_ms, w in words:
        cum += len(w)
        marks.append((off_ms, min(n, round(n * cum / total_wlen))))
    return path, marks


def _chars_at(pos_ms: float, marks: list[tuple[float, int]], length_ms: int, n: int) -> int:
    """按播放位置算该显示到第几个字符"""
    if not marks:
        if length_ms <= 0:
            return n
        return min(n, round(n * pos_ms / length_ms))
    prev_off, prev_ch = 0.0, 0
    for off, ch in marks:
        if pos_ms < off:
            span = off - prev_off
            f = (pos_ms - prev_off) / span if span > 0 else 1.0
            return min(n, max(prev_ch, round(prev_ch + (ch - prev_ch) * f)))
        prev_off, prev_ch = off, ch
    return n


def _play_synced(text: str, path: str, marks, on_start, on_progress) -> None:
    """mci 播放音频并按位置驱动 on_progress"""
    import time as _t

    _mci_close()
    # 先用 mpegvideo 开 开不了退回默认设备
    if _mci(f'open "{path}" type mpegvideo alias mochitts') != 0:
        if _mci(f'open "{path}" alias mochitts') != 0:
            raise RuntimeError("MCI open failed")
    n = len(text)
    try:
        try:
            length_ms = int(_mci_status("length") or 0)
        except (ValueError, TypeError):
            length_ms = 0
        if on_start is not None:
            on_start()
        if _mci("play mochitts") != 0:
            raise RuntimeError("MCI play failed")
        last = -1
        while _mci_status("mode") == "playing":
            if _stop.is_set():
                _mci("stop mochitts")
                break
            try:
                pos = int(_mci_status("position") or 0)
            except (ValueError, TypeError):
                pos = 0
            shown = _chars_at(pos, marks, length_ms, n)
            if on_progress is not None and shown != last:
                last = shown
                on_progress(shown)
            _t.sleep(0.03)
        if on_progress is not None and not _stop.is_set():
            on_progress(n)
    finally:
        _mci_close()
        try:
            os.remove(path)
        except OSError:
            pass


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
        text, on_start, on_progress, on_done, voice, rate = _queue.get()
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
        started = False
        if text and not _stop.is_set():
            played = False
            # 优先 edge 失败回落 sapi
            if voice and edge_available():
                try:
                    synth = _synth_edge(text, voice, rate)
                    if synth is not None and _stop.is_set():
                        try:
                            os.remove(synth[0])
                        except OSError:
                            pass
                    elif synth is not None:
                        _play_synced(text, synth[0], synth[1], on_start, on_progress)
                        started = True
                        played = True
                except Exception:
                    played = False
            if not played:
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


def _enqueue(cleaned: str, on_start, on_progress, on_done, voice: str, rate: int) -> None:
    _ensure()
    _queue.put((cleaned, on_start, on_progress, on_done, voice, rate))


def speak(text: str) -> None:
    if not _enabled:
        return
    cleaned = _clean(text)
    if cleaned:
        _enqueue(cleaned, None, None, None, _voice, _rate)


def speak_one(text: str, on_start=None, on_progress=None, on_done=None) -> None:
    """念一句 带逐词跟随回调"""
    cleaned = _clean(text) if _enabled else ""
    if not _enabled or not cleaned:
        for cb in (on_start, on_done):
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
        return
    _enqueue(cleaned, on_start, on_progress, on_done, _voice, _rate)


def preview(text: str, voice: str, rate, on_done=None) -> None:
    """用指定音色语速试听一句"""
    try:
        rate = max(-50, min(50, int(rate)))
    except (TypeError, ValueError):
        rate = 0
    cleaned = _clean(text)
    if not cleaned:
        if on_done is not None:
            on_done()
        return
    _enqueue(cleaned, None, None, on_done, voice or "", rate)


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
        _queue.put_nowait((None, None, None, None, "", 0))
    except Exception:
        pass
    t = _worker_thread
    if t is not None and t.is_alive():
        t.join(timeout=1.5)
