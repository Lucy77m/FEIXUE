# author: bdth
# email: 2074055628@qq.com
# kokoro 本地神经语音 模型按需下载 纯离线合成
# 按句子语言自动换嗓(中英日) 合成后按字符权重摊时间戳驱动字幕逐字同步

from __future__ import annotations

import os
import queue
import re
import tempfile
import threading
import wave

from desktop_pet.settings import DATA_DIR

_queue: "queue.Queue[tuple]" = queue.Queue()
_enabled = False
_started = False
_lock = threading.Lock()
_stop = threading.Event()
_shutdown = threading.Event()
_worker_thread: "threading.Thread | None" = None

_rate = 0
_file_seq = 0

VOICE_DIR = DATA_DIR / "voice"
_MODEL_PATH = VOICE_DIR / "kokoro-v1.0.onnx"
_VOICES_PATH = VOICE_DIR / "voices-v1.0.bin"
# 模型挂在仓库models release 一次下载永久离线
_DL_BASE = "https://github.com/dulaiduwang003/MOCHI/releases/download/models"
_DL_FILES = [  # (文件名, 目标路径, 进度权重≈字节占比)
    ("kokoro-v1.0.onnx", _MODEL_PATH, 0.92),
    ("voices-v1.0.bin", _VOICES_PATH, 0.08),
]
DOWNLOAD_SIZE_HINT = "340MB"

# 它的声音 每种语言固定一把嗓子 不给选
_VOICE = {"zh": "zf_xiaoxiao", "en": "af_heart", "ja": "jf_alpha"}
_ESPEAK_LANG = {"en": "en-us", "ja": "ja"}

_MAX_TOTAL = 30.0  # 单句音频硬上限秒 防失控

_kokoro = None
_zh_g2p = None

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
    """合成前洗掉 markdown emoji 和链接"""
    text = _LINK.sub(r"\1", text or "")
    text = _TAG.sub("", text)
    text = _MD.sub("", text)
    text = _EMOJI.sub("", text)
    return " ".join(text.split())[:600]


# ── 模型就绪与下载 ──────────────────────────────────────────────

def is_ready() -> bool:
    """模型文件都在才算就绪"""
    return _MODEL_PATH.exists() and _VOICES_PATH.exists()


_dl_lock = threading.Lock()
_dl_state = {"state": "idle", "pct": 0.0, "msg": ""}  # idle/downloading/error(+ready由is_ready算)


def download_status() -> dict:
    """给设置面板轮询的状态"""
    with _dl_lock:
        st = dict(_dl_state)
    if st["state"] != "downloading" and is_ready():
        st["state"] = "ready"
    return st


def start_download(proxy: str = "") -> None:
    """后台下载模型 幂等 已就绪或在下都不动"""
    with _dl_lock:
        if _dl_state["state"] == "downloading":
            return
        _dl_state.update(state="downloading", pct=0.0, msg="")
    if is_ready():
        with _dl_lock:
            _dl_state.update(state="idle", pct=0.0)
        return
    threading.Thread(target=_download, args=(proxy,), daemon=True, name="mochi-voice-dl").start()


def _download(proxy: str) -> None:
    try:
        from desktop_pet.settings import build_http_client

        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        done_w = 0.0
        with build_http_client(proxy) as client:
            for name, dest, weight in _DL_FILES:
                if dest.exists():
                    done_w += weight
                    continue
                tmp = dest.with_suffix(dest.suffix + ".part")
                with client.stream("GET", f"{_DL_BASE}/{name}", follow_redirects=True) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length") or 0)
                    got = 0
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_bytes(1024 * 256):
                            fh.write(chunk)
                            got += len(chunk)
                            frac = (got / total) if total else 0.0
                            with _dl_lock:
                                _dl_state["pct"] = min(0.999, done_w + weight * frac)
                tmp.replace(dest)
                done_w += weight
        with _dl_lock:
            _dl_state.update(state="idle", pct=1.0, msg="")
    except Exception as e:
        for _, dest, _w in _DL_FILES:
            part = dest.with_suffix(dest.suffix + ".part")
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
        with _dl_lock:
            _dl_state.update(state="error", msg=str(e)[:120])


# ── 开关与参数 ─────────────────────────────────────────────────

def is_enabled() -> bool:
    """开了且模型在 字幕配速依赖这个"""
    return _enabled and is_ready()


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)
    if _enabled:
        if is_ready():
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


# ── 合成 ──────────────────────────────────────────────────────

def _detect_lang(text: str) -> str:
    """假名→日 汉字→中 其余→英"""
    for ch in text:
        if 0x3040 <= ord(ch) <= 0x30FF:
            return "ja"
    for ch in text:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            return "zh"
    return "en"


def _ensure_model():
    global _kokoro
    if _kokoro is None and is_ready():
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(_MODEL_PATH), str(_VOICES_PATH))
    return _kokoro


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
        or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF
        or 0xF900 <= o <= 0xFAFF
    )


def _marks_for(text: str, total_ms: float) -> list[tuple[float, int]]:
    """把音频总时长按字符权重摊回原文 字幕逐字跟着走
    汉字假名最重 标点当停顿 emoji给一点点 比例对了听感就同步"""
    ws = []
    for ch in text:
        if _is_cjk(ch):
            w = 1.0
        elif ch.isalnum():
            w = 0.42
        elif ch in "，。！？；：、,.!?;:…～~":
            w = 0.9
        elif ch.isspace():
            w = 0.35
        else:
            w = 0.15
        ws.append(w)
    total_w = sum(ws) or 1.0
    cum = 0.0
    marks: list[tuple[float, int]] = []
    for i, w in enumerate(ws):
        cum += w
        marks.append((total_ms * cum / total_w, i + 1))
    return marks


def _synth(text: str, rate: int) -> "tuple[str, float] | None":
    """kokoro 合成 返回wav路径和时长ms"""
    import numpy as np

    global _file_seq, _zh_g2p
    k = _ensure_model()
    if k is None:
        return None
    cleaned = _clean(text)
    if not re.search(r"[\w぀-ヿ一-鿿가-힯]", cleaned):
        return None  # 没有可念的内容
    speed = max(0.5, min(1.5, 1.0 + rate / 100.0))
    lang = _detect_lang(cleaned)
    if lang == "zh":
        # 中文走misaki注音 比espeak准得多
        if _zh_g2p is None:
            from misaki import zh as _zh
            _zh_g2p = _zh.ZHG2P()
        phonemes, _ = _zh_g2p(cleaned)
        samples, sr = k.create(phonemes, voice=_VOICE["zh"], speed=speed, is_phonemes=True)
    else:
        samples, sr = k.create(cleaned, voice=_VOICE[lang], speed=speed, lang=_ESPEAK_LANG[lang])
    if samples is None or not len(samples):
        return None
    n_cap = int(_MAX_TOTAL * sr)
    if len(samples) > n_cap:
        samples = samples[:n_cap]
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    with _lock:
        _file_seq += 1
        seq = _file_seq
    path = os.path.join(tempfile.gettempdir(), f"mochi_voice_{seq}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path, len(pcm) * 1000.0 / sr


# ── 播放 mci带位置轮询 驱动字幕 ─────────────────────────────────

def _chars_at(pos_ms: float, marks: list[tuple[float, int]], n: int) -> int:
    prev_off, prev_ch = 0.0, 0
    for off, ch in marks:
        if pos_ms < off:
            span = off - prev_off
            f = (pos_ms - prev_off) / span if span > 0 else 1.0
            return min(n, max(prev_ch, round(prev_ch + (ch - prev_ch) * f)))
        prev_off, prev_ch = off, ch
    return n


def _play_synced(text: str, path: str, dur_ms: float, on_start, on_progress) -> None:
    """mci 播放并按位置驱动字幕进度"""
    import time as _t

    marks = _marks_for(text, dur_ms)
    n = len(text)
    _mci_close()
    if _mci(f'open "{path}" alias mochitts') != 0:
        raise RuntimeError("MCI open failed")
    try:
        if on_start is not None:
            on_start()
        if _mci("play mochitts") != 0:
            raise RuntimeError("MCI play failed")
        last = -1
        # 看门狗 mci状态抽风也绝不困死
        deadline = _t.monotonic() + dur_ms / 1000.0 + 2.0
        while _mci_status("mode") == "playing":
            if _stop.is_set() or _t.monotonic() > deadline:
                _mci("stop mochitts")
                break
            try:
                pos = int(_mci_status("position") or 0)
            except (ValueError, TypeError):
                pos = 0
            shown = _chars_at(pos, marks, n)
            if on_progress is not None and shown != last:
                last = shown
                on_progress(shown)
            _t.sleep(0.03)
        if on_progress is not None and not _stop.is_set():
            on_progress(n)  # 时间戳是按原文长度摊的 收尾对得上
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


def _enqueue(text: str, on_start, on_progress, on_done, rate: int) -> None:
    _ensure()
    _queue.put((text, on_start, on_progress, on_done, rate))


# ── 对外接口 ──────────────────────────────────────────────────

def speak(text: str) -> None:
    if not is_enabled():
        return
    if (text or "").strip():
        _enqueue(text[:600], None, None, None, _rate)


def speak_one(text: str, on_start=None, on_progress=None, on_done=None) -> None:
    """念一句 进度回调按原文字符位驱动气泡逐字同步"""
    if not is_enabled() or not (text or "").strip():
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
    if not is_ready() or not (text or "").strip():
        if on_done is not None:
            on_done()
        return
    _enqueue(text[:600], None, None, on_done, rate)


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
