# author: bdth
# email: 2074055628@qq.com
# 定时看屏：「每隔一段时间截图分析某件事」的会话级状态(不落盘、跨线程共享)。

from __future__ import annotations

import threading
from datetime import datetime

# 下限 60s —— 拦住模型/手滑设出 5s 这种把屏幕截爆的间隔。
_MIN_INTERVAL_S = 60.0
# \x00 包边的哨兵：正常模型输出里不可能出现 NUL，拿它标「这一拍看屏失败」绝不会撞车。
WATCH_FAIL = "\x00WATCH_FAIL\x00"


class _Watcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.focus = ""
        self.interval_s = 0.0
        self._last: datetime | None = None

    def start(self, focus: str, interval_minutes: float) -> tuple[bool, str, float]:
        """开/改一次看屏任务 → 返回 (是否真开了, focus, 实际分钟数)。"""
        with self._lock:
            self.focus = (focus or "").strip()
            try:
                self.interval_s = max(_MIN_INTERVAL_S, float(interval_minutes) * 60.0)
            except (TypeError, ValueError):
                self.interval_s = 300.0  # 模型给了句废话/None，兜底 5 分钟
            # focus 空就当没开 —— 没目标的看屏没意义。
            self.enabled = bool(self.focus)
            self._last = None
            return self.enabled, self.focus, self.interval_s / 60.0

    def stop(self) -> None:
        with self._lock:
            self.enabled = False
            self.focus = ""
            self._last = None

    def retry_soon(self) -> None:
        """这拍失败别等满间隔，下一拍马上重看。"""
        with self._lock:
            self._last = None

    def due(self, now: datetime) -> str | None:
        """没到间隔就返回 None —— 调用方每秒来问，靠 _last 把频率压到 interval。"""
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
