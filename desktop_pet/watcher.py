# author: bdth
# email: 2074055628@qq.com
# 定时看屏：用户让桌宠「每隔一段时间截图分析某件事(如游戏局势)」时的会话级状态。
# 故意不落盘——这是"这次游戏盯一会儿"的临时活动，不是永久设置（否则重启后还会每隔几分钟空耗一次模型调用）。
# 跨线程共享：工具(worker 线程)调 start/stop，app(主线程)定时器调 due。

from __future__ import annotations

import threading
from datetime import datetime

_MIN_INTERVAL_S = 60.0
WATCH_FAIL = "\x00WATCH_FAIL\x00"


class _Watcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.focus = ""
        self.interval_s = 0.0
        self._last: datetime | None = None

    def start(self, focus: str, interval_minutes: float) -> tuple[bool, str, float]:
        with self._lock:
            self.focus = (focus or "").strip()
            try:
                self.interval_s = max(_MIN_INTERVAL_S, float(interval_minutes) * 60.0)
            except (TypeError, ValueError):
                self.interval_s = 300.0
            self.enabled = bool(self.focus)
            self._last = None
            return self.enabled, self.focus, self.interval_s / 60.0

    def stop(self) -> None:
        with self._lock:
            self.enabled = False
            self.focus = ""
            self._last = None

    def retry_soon(self) -> None:
        """本次看屏硬失败(截图/模型失败)：清掉 _last，让下一拍立刻重试，别等满一个间隔白烧一个周期。"""
        with self._lock:
            self._last = None

    def due(self, now: datetime) -> str | None:
        """到点该看了就返回 focus 并记录本次时间；否则 None。调用方应先过完自己的门控再调本方法
        （本方法一旦返回非空就视为"这一拍已消费"，记 _last）。"""
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
