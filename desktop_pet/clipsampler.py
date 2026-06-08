# author: bdth
# email: 2074055628@qq.com
# 剪贴板采样器：监听 QClipboard.dataChanged（UI 线程），对新复制的文本做本地分类、去重、节流，
# 把「最近一条有趣的剪贴板」留在内存里，并发 interesting 信号给「剪贴板炼金术」消费。
# 隐私红线：只在内存里留最近几条，进程退出即丢，绝不落盘、绝不进 reflect/journal/LLM 历史。

from __future__ import annotations

import hashlib
import time
from collections import deque

from PySide6.QtCore import QObject, Signal

from desktop_pet import clipclass

_MIN_LEN = 2
_MAX_LEN = 20000
_MIN_INTERVAL_S = 1.5
_RING = 8
_SEEN = 16


class Sampler(QObject):
    interesting = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._enabled = False
        self._ring: deque[tuple[str, str]] = deque(maxlen=_RING)
        self._interesting: tuple[str, str] | None = None
        self._seen: deque[str] = deque(maxlen=_SEEN)
        self._self_mark = ""
        self._last_t = 0.0

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def mark_self_write(self, text: str) -> None:
        """Mochi 自己写回剪贴板前调用，下一次 dataChanged 命中就跳过，防自采样回环。"""
        self._self_mark = self._hash((text or "").strip())

    def feed(self, text: str) -> None:
        """app 把 QClipboard 文本喂进来（UI 线程）。"""
        if not self._enabled:
            return
        s = (text or "").strip()
        if not (_MIN_LEN <= len(s) <= _MAX_LEN):
            return
        h = self._hash(s)
        if h == self._self_mark:
            self._self_mark = ""
            return
        if h in self._seen:
            return
        now = time.monotonic()
        if now - self._last_t < _MIN_INTERVAL_S:
            return
        self._last_t = now
        self._seen.append(h)
        kind, _conf = clipclass.classify(s)
        self._ring.append((kind, s))
        if clipclass.is_interesting(kind):
            self._interesting = (kind, s)
            self.interesting.emit(kind, s)

    def latest(self) -> tuple[str, str] | None:
        return self._ring[-1] if self._ring else None

    def latest_interesting(self) -> tuple[str, str] | None:
        """给 worker 线程读：返回的是不可变 tuple 快照，安全。"""
        return self._interesting

    def recent(self, n: int = _RING) -> list[tuple[str, str]]:
        return list(self._ring)[-n:]

    def reset(self) -> None:
        self._ring.clear()
        self._seen.clear()
        self._interesting = None

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


sampler = Sampler()
