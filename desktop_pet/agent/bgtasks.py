# author: bdth
# email: 2074055628@qq.com
# 后台任务注册表：让正在跑的后台任务可被列出、可被协作式停止

from __future__ import annotations

import threading
from datetime import datetime


class _BgRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[int, dict] = {}
        self._seq = 0

    def register(self, task: str, cancel: threading.Event) -> int:
        with self._lock:
            self._seq += 1
            tid = self._seq
            self._tasks[tid] = {"task": task, "started": datetime.now(), "cancel": cancel}
            return tid

    def unregister(self, tid: int) -> None:
        with self._lock:
            self._tasks.pop(tid, None)

    def snapshot(self) -> list[tuple[int, str, float]]:
        """返回 [(id, task, 已运行秒数), ...]，按 id 升序。"""
        with self._lock:
            now = datetime.now()
            return [
                (tid, d["task"], (now - d["started"]).total_seconds())
                for tid, d in sorted(self._tasks.items())
            ]

    def stop(self, tid: int) -> bool:
        """置该任务的 cancel 事件。"""
        with self._lock:
            d = self._tasks.get(tid)
        if d is None:
            return False
        try:
            d["cancel"].set()
        except Exception:
            return False
        return True


bg_tasks = _BgRegistry()
