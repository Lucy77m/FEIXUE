# author: bdth
# email: 2074055628@qq.com
# 定时看屏的会话级状态 不落盘 跨线程共享

from __future__ import annotations

import threading
from datetime import datetime

_MIN_INTERVAL_S = 60.0
# 看屏失败的哨兵值
WATCH_FAIL = "\x00WATCH_FAIL\x00"


class _Watcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.focus = ""
        self.interval_s = 0.0
        self._last: datetime | None = None

    def start(self, focus: str, interval_minutes: float) -> tuple[bool, str, float]:
        """开或改一次看屏任务"""
        with self._lock:
            self.focus = (focus or "").strip()
            try:
                self.interval_s = max(_MIN_INTERVAL_S, float(interval_minutes) * 60.0)
            except (TypeError, ValueError):
                self.interval_s = 300.0  # 兜底 5 分钟
            self.enabled = bool(self.focus)
            self._last = None
            return self.enabled, self.focus, self.interval_s / 60.0

    def stop(self) -> None:
        with self._lock:
            self.enabled = False
            self.focus = ""
            self._last = None

    def retry_soon(self) -> None:
        """下一拍马上重看"""
        with self._lock:
            self._last = None

    def due(self, now: datetime) -> str | None:
        """到点返回 focus 没到返回 None"""
        with self._lock:
            if not self.enabled or not self.focus:
                return None
            if self._last is not None and (now - self._last).total_seconds() < self.interval_s:
                return None
            self._last = now
            return self.focus

    def snapshot(self) -> tuple[bool, str, float]:
        with self._lock:
            return self.enabled, self.focus, (self.interval_s / 60.0)


watcher = _Watcher()
