# author: bdth
# email: 2074055628@qq.com
# 非语言小声音 —— 情绪标点(啁啾/呜咽/咕噜)。纯numpy合成、winsound内存异步播放：
# 不引入音频素材、不碰COM/设备句柄、fire-and-forget，从根上避开音频清理崩溃。默认关。

from __future__ import annotations

import io
import wave

try:
    import winsound  # Windows 自带
except ImportError:  # 非 Windows 直接退化成静音
    winsound = None

_SR = 22050
_enabled = False
_cache: dict[str, bytes] | None = None

# 动作/反应名 → 情绪音；不在表里的(喝咖啡、钓鱼这类)不出声
_REACT_CUE = {
    "celebrate": "happy", "cheer": "happy", "jump_spin": "happy", "dance": "happy",
    "hop2": "happy", "spin": "happy", "bounce": "happy", "boing": "happy",
    "droop": "sad", "wobble": "sad", "shake": "sad",
    "snuggle": "purr", "yawn": "soft", "stretch": "soft",
    "perk_up": "curious", "double_take": "curious", "peek": "curious", "nod": "curious",
    "puff_up": "grumpy", "recoil": "grumpy",
}


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)


def cue_for(name: str) -> str | None:
    return _REACT_CUE.get(name)


def _wav(samples) -> bytes:
    import numpy as np
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _glide(f0: float, f1: float, dur: float, vol: float = 0.32):
    """一段频率从f0滑到f1的音，带渐入渐出包络防爆音"""
    import numpy as np
    n = max(1, int(_SR * dur))
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / _SR
    tone = np.sin(phase)
    env = np.ones(n)
    a, d = max(1, int(n * 0.15)), max(1, int(n * 0.35))
    env[:a] = np.linspace(0.0, 1.0, a)
    env[-d:] = np.linspace(1.0, 0.0, d)
    return tone * env * vol


def _purr(dur: float = 0.42, vol: float = 0.28):
    """低频带颤音的咕噜"""
    import numpy as np
    n = max(1, int(_SR * dur))
    t = np.linspace(0.0, dur, n, endpoint=False)
    base = np.sin(2 * np.pi * 115 * t)
    tremolo = 0.55 + 0.45 * np.sin(2 * np.pi * 24 * t)
    env = np.ones(n)
    a, d = int(n * 0.1), int(n * 0.3)
    env[:a] = np.linspace(0.0, 1.0, a)
    env[-d:] = np.linspace(1.0, 0.0, d)
    return base * tremolo * env * vol


def _build() -> dict[str, bytes]:
    import numpy as np
    return {
        "happy": _wav(np.concatenate([_glide(720, 1040, 0.10), _glide(1040, 1320, 0.09)])),
        "sad": _wav(_glide(520, 300, 0.30, 0.30)),
        "curious": _wav(_glide(840, 980, 0.08, 0.30)),
        "purr": _wav(_purr()),
        "soft": _wav(_glide(600, 530, 0.20, 0.24)),
        "grumpy": _wav(_glide(320, 250, 0.16, 0.30)),
    }


def play(cue: str | None) -> None:
    """播一个情绪音。关了 / 非Windows / 没这个音 都安静返回。"""
    global _cache
    if not _enabled or winsound is None or not cue:
        return
    if _cache is None:
        try:
            _cache = _build()
        except Exception:
            _cache = {}
    data = _cache.get(cue)
    if not data:
        return
    try:
        winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass  # 播放失败绝不影响主流程
