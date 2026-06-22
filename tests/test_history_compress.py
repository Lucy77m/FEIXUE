# 历史压缩异步化测试 裁剪同步生效 摘要后台做 换话题作废在途 不碰网络

from __future__ import annotations

import threading
import time

import pytest

from desktop_pet.agent.history import HistoryMixin


class _FakeMsg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeMsg(content)]
        self.usage = None


class _Harness(HistoryMixin):
    """只搭压缩需要的最小骨架 不起真Agent"""

    def __init__(self, summary_text="新备忘", block: threading.Event | None = None):
        self._compressed = ""
        self._compress_lock = threading.Lock()
        self._pending_compress = []
        self._compress_busy = False
        self._compress_gen = 0
        self._settings = type("S", (), {"subagent_model": "", "model": "m"})()
        self._summary_text = summary_text
        self._block = block  # 给测试卡住摘要调用 模拟慢LLM
        self._calls = 0

    def _client(self):
        harness = self

        class _C:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        harness._calls += 1
                        if harness._block is not None:
                            harness._block.wait(5)
                        return _FakeResp(harness._summary_text)
        return _C()

    def _meter_response(self, resp):
        pass


def _wait(cond, timeout=5.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_drop_is_sync_summary_is_async():
    gate = threading.Event()
    h = _Harness(summary_text="揉好的备忘", block=gate)
    # 队列里塞一段被裁对话 此调用必须立刻返回 不等LLM
    t0 = time.monotonic()
    h._queue_compression([{"role": "user", "content": "很久以前聊的内容"}])
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5, f"_queue_compression堵住了 用了{elapsed}s"
    assert h._compress_busy, "后台worker该在跑"
    assert h._compressed == "", "摘要还没回来前不该有内容"
    # 放行慢LLM 摘要落地
    gate.set()
    assert _wait(lambda: h._compressed == "揉好的备忘"), "异步摘要没写回"
    assert _wait(lambda: not h._compress_busy)


def test_multiple_overflows_accumulate():
    gate = threading.Event()
    h = _Harness(summary_text="合并后的", block=gate)
    h._queue_compression([{"role": "user", "content": "第一段"}])
    # worker已在第一段上忙着 再来两段应入队 不另起worker
    h._queue_compression([{"role": "user", "content": "第二段"}])
    h._queue_compression([{"role": "user", "content": "第三段"}])
    assert len(h._pending_compress) >= 1, "后续段该排队等worker消化"
    gate.set()
    assert _wait(lambda: not h._compress_busy and not h._pending_compress)
    assert h._compressed == "合并后的"


def test_reset_voids_inflight():
    gate = threading.Event()
    h = _Harness(summary_text="过期的摘要", block=gate)
    h._queue_compression([{"role": "user", "content": "旧话题"}])
    assert _wait(lambda: h._calls >= 1)  # worker已进LLM调用 卡在gate
    # 此刻换话题 在途摘要必须作废 不能回写
    h._reset_compressed()
    gate.set()
    time.sleep(0.3)  # 给worker机会尝试回写
    assert h._compressed == "", "换话题后在途摘要不该盖回内容"


def test_empty_dropped_noop():
    h = _Harness()
    h._queue_compression([])  # 渲染出来是空 直接返回
    assert not h._compress_busy
    assert h._compressed == ""
