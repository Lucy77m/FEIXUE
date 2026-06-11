# 听觉全链路回归 假麦克风灌真语音 跑真模型
# 需要模型在 data/hearing 没下载就整组跳过
import queue
import threading
import time
import wave
from pathlib import Path

import pytest

from desktop_pet import hearing

pytestmark = pytest.mark.skipif(not hearing.is_ready(), reason="听觉模型未就位")

_WAV = Path(__file__).parent / "data" / "zh.wav"


class _FakeStream:
    """假麦克风 不碰真设备 音频由测试手动灌进_audio_q"""

    def __init__(self, **kw):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class _FakeKwsStream:
    def __init__(self):
        self.chunks = 0
        self.ready = 0

    def accept_waveform(self, sr, c):
        self.chunks += 1
        self.ready += 1


class _FakeKws:
    """确定性唤醒 喂够N块必命中 专测我们自己的门控和采集状态机"""

    def __init__(self, hit_after=5):
        self.hit_after = hit_after
        self.fired = False

    def create_stream(self):
        return _FakeKwsStream()

    def is_ready(self, s):
        return s.ready > 0

    def decode_stream(self, s):
        s.ready = 0

    def get_result(self, s):
        if not self.fired and s.chunks >= self.hit_after:
            self.fired = True
            return "墨池"
        return ""

    def reset_stream(self, s):
        pass


def _load_chunks():
    import numpy as np
    with wave.open(str(_WAV), "rb") as w:
        assert w.getframerate() == 16000
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return [pcm[i:i + 1600] for i in range(0, len(pcm), 1600)]


def _silence(seconds: float):
    import numpy as np
    n = int(seconds * 16000)
    return [np.zeros(1600, dtype=np.float32) for _ in range(n // 1600)]


def _wait(cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(autouse=True)
def mic(monkeypatch):
    import sounddevice
    monkeypatch.setattr(sounddevice, "InputStream", _FakeStream)
    hearing._shutdown.clear()
    hearing._talk_req.clear()
    hearing._talk_end.clear()
    hearing._capturing = False
    hearing._enabled = False
    hearing._wake_on = False
    hearing.cb_busy = None
    hearing.cb_wake_block = None
    hearing.cb_partial = hearing.cb_final = hearing.cb_state = hearing.cb_tick = None
    hearing._drain(hearing._audio_q)
    yield
    # 关掉并等线程退干净 再让monkeypatch还原
    hearing._enabled = False
    hearing._wake_on = False
    hearing._talk_end.set()
    t = hearing._loop_thread
    if t is not None:
        t.join(timeout=10)
    hearing.cb_busy = None
    hearing.cb_wake_block = None


def test_hotkey_full_path():
    """按住说话 灌真语音 松开 必须识别出北京时间"""
    finals, states = [], []
    hearing.cb_final = finals.append
    hearing.cb_state = states.append
    hearing._enabled = True
    hearing.start_talk()
    assert _wait(lambda: "listening" in states), "没进入采集"
    for c in _load_chunks():
        hearing._audio_q.put(c)
    time.sleep(1.0)  # 给实时识别一点消化时间
    hearing.stop_talk()
    assert _wait(lambda: bool(finals)), "松开后没出定稿"
    assert "时间" in finals[0], f"识别错了: {finals[0]}"


def test_wake_word_full_path(monkeypatch):
    """唤醒词链路真声学版 用音频里真实出现的'开放'当临时唤醒词"""
    monkeypatch.setattr(hearing, "_WAKE_KEYWORD", "k āi f àng @开放")
    monkeypatch.setattr(hearing, "_kws", None)  # 换关键词要重建
    finals, states = [], []
    hearing.cb_final = finals.append
    hearing.cb_state = states.append
    hearing._wake_on = True
    hearing._kick()
    for c in _load_chunks():
        hearing._audio_q.put(c)
    assert _wait(lambda: "wake_hit" in states), "唤醒词没命中"
    # 唤醒后接着说的内容 + 足够静音让vad收尾
    for c in _load_chunks() + _silence(2.0):
        hearing._audio_q.put(c)
    assert _wait(lambda: bool(finals)), "唤醒采集没出定稿"
    hearing._wake_on = False


def test_busy_ignores_wake(monkeypatch):
    """它正忙 唤醒词必命中(假kws)也得装没听见"""
    fake = _FakeKws(hit_after=3)
    monkeypatch.setattr(hearing, "_load_kws", lambda: fake)
    states = []
    hearing.cb_state = states.append
    hearing.cb_busy = lambda: True
    hearing._wake_on = True
    hearing._kick()
    for c in _load_chunks():
        hearing._audio_q.put(c)
    time.sleep(2.0)
    assert fake.fired, "假kws该命中"
    assert "wake_hit" not in states, "忙时不该被唤醒"
    hearing._wake_on = False


def test_meeting_blocks_wake(monkeypatch):
    """开会屏蔽唤醒词 音频根本不进kws"""
    fake = _FakeKws(hit_after=3)
    monkeypatch.setattr(hearing, "_load_kws", lambda: fake)
    states = []
    hearing.cb_state = states.append
    hearing.cb_wake_block = lambda: True
    hearing._wake_on = True
    hearing._kick()
    for c in _load_chunks():
        hearing._audio_q.put(c)
    time.sleep(2.0)
    assert not fake.fired, "开会时音频不该喂进kws"
    assert "wake_hit" not in states
    hearing._wake_on = False


def test_wake_noise_only_discarded(monkeypatch):
    """误唤醒后只有环境静音 不许把幻觉文本外发"""
    fake = _FakeKws(hit_after=3)
    monkeypatch.setattr(hearing, "_load_kws", lambda: fake)
    monkeypatch.setattr(hearing, "_WAKE_IDLE_S", 1.5)
    finals, states = [], []
    hearing.cb_final = finals.append
    hearing.cb_state = states.append
    hearing._wake_on = True
    hearing._kick()
    for c in _silence(1.0):  # 静音也会触发假kws
        hearing._audio_q.put(c)
    assert _wait(lambda: "wake_hit" in states), "假kws该唤醒"
    for c in _silence(3.0):
        hearing._audio_q.put(c)
    assert _wait(lambda: "idle" in states[states.index("wake_hit"):], timeout=15), "该超时收场"
    time.sleep(0.5)
    assert not finals, "纯噪音不该外发"
    hearing._wake_on = False


def test_disable_mid_capture_discards():
    """说一半把听觉关掉 这句作废不外发"""
    finals, states = [], []
    hearing.cb_final = finals.append
    hearing.cb_state = states.append
    hearing._enabled = True
    hearing.start_talk()
    assert _wait(lambda: "listening" in states)
    for c in _load_chunks()[:10]:
        hearing._audio_q.put(c)
    time.sleep(0.3)
    hearing._enabled = False  # 面板里关掉
    assert _wait(lambda: not hearing._capturing, timeout=10), "采集没结束"
    time.sleep(0.5)
    assert not finals, "作废的话不该外发"


def test_busy_ignores_hotkey():
    """忙时按住说话直接无视"""
    hearing.cb_busy = lambda: True
    hearing._enabled = True
    hearing.start_talk()
    assert not hearing._talk_req.is_set()
