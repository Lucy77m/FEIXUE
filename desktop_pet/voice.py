# author: bdth
# email: 2074055628@qq.com
# 语音朗读(TTS):用 Windows SAPI(经 pywin32，零新增依赖)在后台 COM 线程里念出来。
# 默认关闭；说话/提醒/主动消息时若开启则出声。失败一律静默降级。

from __future__ import annotations

import queue
import re
import threading

_queue: "queue.Queue[str]" = queue.Queue()
_enabled = False
_started = False
_lock = threading.Lock()

_TAG = re.compile(r"^\s*\[(\w+)\]\s*")          # 去掉开头的 [emotion] 标签
_MD = re.compile(r"[*#`>~_|]+")                 # 去掉常见 markdown 符号
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")  # [文字](链接) → 文字


def _clean(text: str) -> str:
    text = _LINK.sub(r"\1", text or "")
    text = _TAG.sub("", text)
    text = _MD.sub("", text)
    return " ".join(text.split())[:600]


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)
    if _enabled:
        _ensure()
    else:
        flush()


def _ensure() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_worker, daemon=True, name="mochi-tts").start()


def _select_voice(sp) -> None:
    # 尽量挑一个中文嗓子(系统装了的话)；挑不到就用默认嗓子
    try:
        for v in sp.GetVoices():
            desc = v.GetDescription() or ""
            if any(k in desc for k in ("Chinese", "中文", "Huihui", "Yaoyao", "Kangkang", "Xiaoxiao")):
                sp.Voice = v
                return
    except Exception:  # noqa: BLE001
        pass


def _worker() -> None:
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        _select_voice(sp)
    except Exception:  # noqa: BLE001 — SAPI 不可用就静默退出，等于没开声音
        return
    while True:
        item = _queue.get()
        try:
            sp.Speak(item)  # 阻塞到这句念完；flush() 只清队列、不强行打断当前句(避免跨线程 COM)
        except Exception:  # noqa: BLE001
            pass


def speak(text: str) -> None:
    if not _enabled:
        return
    cleaned = _clean(text)
    if cleaned:
        _ensure()
        _queue.put(cleaned)


def flush() -> None:
    """清掉待播队列(正在念的那句会自然念完)——打断/下线/退出时调。"""
    try:
        while True:
            _queue.get_nowait()
    except queue.Empty:
        pass
