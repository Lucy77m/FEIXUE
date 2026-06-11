# author: bdth
# email: 2074055628@qq.com
# 墨池语 不念内容 按字符合成叽里呱啦的小啁啾 同字同音像一门真的语言
# 纯numpy合成零依赖零联网 问号句尾上扬 叹号更亮更快 字幕跟着音节走

from __future__ import annotations

import os
import queue
import re
import tempfile
import threading
import wave

_queue: "queue.Queue[tuple]" = queue.Queue()
_enabled = False
_started = False
_lock = threading.Lock()
_stop = threading.Event()
_shutdown = threading.Event()
_worker_thread: "threading.Thread | None" = None

_rate = 0
_file_seq = 0

_SR = 22050
_BASE_FREQ = 440.0
_SCALE = (0, 2, 4, 7, 9)  # 五声音阶单八度 不往上蹿免得刺耳
_SYL_DUR = 0.072  # 字幕逐字跟着音节走 这也是阅读速度 别快过人眼
_MAX_TOTAL = 7.0  # 一句的音频硬上限秒 到点直接收声 字幕由结尾回调补完

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

_PAUSE_CH = "，、；：,;:"
_END_CH = "。．.！!？?…～~"


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
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="mochi-voice")
    _worker_thread.start()


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
        or 0x3040 <= o <= 0x30FF  # 假名
        or 0xAC00 <= o <= 0xD7AF  # 谚文
        or 0xF900 <= o <= 0xFAFF
    )


def _pitch(ch: str) -> float:
    """字符定音高 同字永远同音 这就是它的'词'"""
    h = (ord(ch) * 2654435761) & 0xFFFFFFFF
    return _BASE_FREQ * (2.0 ** (_SCALE[h % 5] / 12.0))


def _tokenize(text: str) -> list[dict]:
    """切音节 每项带结束字符位 标点变停顿 问叹回标到前面的音节"""
    toks: list[dict] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _PAUSE_CH:
            toks.append({"kind": "pause", "end": i + 1})
            i += 1
        elif ch in _END_CH:
            # 问号往前最多3个音节上扬 叹号往前最多4个加亮
            mark = "rise" if ch in "？?" else ("bright" if ch in "！!" else None)
            if mark:
                left = 3 if mark == "rise" else 4
                for t in reversed(toks):
                    if left == 0:
                        break
                    if t["kind"] == "syl":
                        t[mark] = True
                        left -= 1
            toks.append({"kind": "stop", "end": i + 1})
            i += 1
        elif ch.isspace():
            toks.append({"kind": "gap", "end": i + 1})
            i += 1
        elif _is_cjk(ch):
            toks.append({"kind": "syl", "end": i + 1, "ch": ch})
            i += 1
        elif ch.isalnum():
            j = i
            while j < n and text[j].isalnum() and not _is_cjk(text[j]):
                j += 1
            for k in range(i, j, 2):  # 拉丁词两字符一个音节
                toks.append({"kind": "syl", "end": min(k + 2, j), "ch": text[k]})
            i = j
        else:
            toks.append({"kind": "gap", "end": i + 1})
            i += 1
    return toks


def _chirp(np, freq: float, dur: float, vol: float, rise: bool, bright: bool):
    """一个音节 短促圆润的啁啾"""
    if bright:
        freq *= 1.06
        vol *= 1.2
        dur *= 0.88
    n = max(8, int(_SR * dur))
    t = np.arange(n) / _SR
    if rise:
        f = np.linspace(freq, freq * 1.22, n)
    else:
        f = freq * (1.0 - 0.06 * np.exp(-t * 70.0))  # 起音从下方滑进来 像开口
    f = f * (1.0 + 0.010 * np.sin(2 * np.pi * 6.0 * t))  # 一点颤音
    phase = 2 * np.pi * np.cumsum(f) / _SR
    w = np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.05 * np.sin(3 * phase)
    # 升余弦包络 圆头圆尾不咔哒
    a, d = max(2, int(n * 0.25)), max(2, int(n * 0.45))
    env = np.ones(n)
    env[:a] = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, a))
    env[-d:] = 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, d))
    return w * env * (vol / 1.23)


def _synth(text: str, rate: int) -> "tuple[str, list[tuple[float, int]]] | None":
    """整句合成墨池语 返回wav路径和逐音节字幕时间戳"""
    import numpy as np

    global _file_seq
    toks = _tokenize(text)
    if not any(t["kind"] == "syl" for t in toks):
        return None
    speed = 1.0 + rate / 100.0  # ±50%
    dur = _SYL_DUR / speed
    gaps = {"syl": 0.017 / speed, "gap": 0.06 / speed, "pause": 0.11 / speed, "stop": 0.16 / speed}
    # 偏长的句子温和加速 再长就到点收声 绝不无限叽歪
    syls = sum(1 for t in toks if t["kind"] == "syl")
    est = syls * (dur + gaps["syl"])
    if est > _MAX_TOTAL:
        squeeze = max(0.7, _MAX_TOTAL / est)
        dur *= squeeze
        gaps = {k: v * squeeze for k, v in gaps.items()}

    parts = []
    marks: list[tuple[float, int]] = []
    cum = 0.0
    for tk in toks:
        if cum >= _MAX_TOTAL:
            break  # 硬上限 剩下的字幕由播完回调一次性补完
        if tk["kind"] == "syl":
            seg = _chirp(np, _pitch(tk["ch"]), dur, 0.30,
                         tk.get("rise", False), tk.get("bright", False))
            parts.append(seg)
            cum += len(seg) / _SR
        g = gaps[tk["kind"]]
        parts.append(np.zeros(max(1, int(_SR * g))))
        cum += g
        marks.append((cum * 1000.0, tk["end"]))

    pcm = np.clip(np.concatenate(parts), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with _lock:
        _file_seq += 1
        seq = _file_seq
    path = os.path.join(tempfile.gettempdir(), f"mochi_voice_{seq}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(pcm.tobytes())
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
        # 看门狗 哪怕mci状态抽风也绝不困在这里
        deadline = _t.monotonic() + (length_ms / 1000.0 if length_ms > 0 else _MAX_TOTAL) + 2.0
        while _mci_status("mode") == "playing":
            if _stop.is_set() or _t.monotonic() > deadline:
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
            # 收尾发大哨兵不发n 这边和气泡端清洗规则不同 长度对不上会卡死字幕
            on_progress(10 ** 9)
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


def _worker() -> None:
    """合成播放工作线程 串行消费队列"""
    while True:
        text, on_start, on_progress, on_done, rate = _queue.get()
        if _shutdown.is_set():
            _mci_close()
            return
        _stop.clear()
        started = False
        if text and not _stop.is_set():
            try:
                synth = _synth(text, rate)
                if synth is not None and _stop.is_set():
                    try:
                        os.remove(synth[0])
                    except OSError:
                        pass
                elif synth is not None:
                    _play_synced(text, synth[0], synth[1], on_start, on_progress)
                    started = True
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
    """念一句 带逐音节字幕跟随回调
    文本不再清洗 原样进合成器 时间戳字符位和气泡显示文本一一对齐
    emoji和符号在合成端只当成小间隙 不发声但占字幕进度"""
    if not _enabled or not (text or "").strip():
        for cb in (on_start, on_done):
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
        return
    _enqueue(text[:600], on_start, on_progress, on_done, _rate)


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
    """退出前停掉发声并收掉 worker"""
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
