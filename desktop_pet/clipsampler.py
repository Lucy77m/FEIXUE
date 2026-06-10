# author: bdth
# email: 2074055628@qq.com
# 剪贴板采样 新复制文本分类去重节流后发interesting信号

from __future__ import annotations

import hashlib
import time
from collections import deque

from PySide6.QtCore import QObject, Signal

from desktop_pet import clipclass

_MIN_LEN = 2
_MAX_LEN = 20000  # 太长直接丢
_MIN_INTERVAL_S = 1.5  # 节流间隔
_RING = 8
_SEEN = 16  # 去重指纹窗口


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
        """标记自写内容下次跳过"""
        self._self_mark = self._hash((text or "").strip())

    def feed(self, text: str) -> None:
        """剪贴板变更入口 逐道过滤后分类"""
        if not self._enabled:
            return
        s = (text or "").strip()
        if not (_MIN_LEN <= len(s) <= _MAX_LEN):
            return
        h = self._hash(s)
        if h == self._self_mark:
            self._self_mark = ""  # 只挡一次
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
        return self._interesting

    def recent(self, n: int = _RING) -> list[tuple[str, str]]:
        return list(self._ring)[-n:]

    def reset(self) -> None:
        """清历史和去重指纹 节流时间戳不动"""
        self._ring.clear()
        self._seen.clear()
        self._interesting = None

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


sampler = Sampler()
