# author: bdth
# email: 2074055628@qq.com
# 后台任务注册表：让正在跑的后台任务可被列出、可被协作式停止

from __future__ import annotations

import threading
from datetime import datetime


class _BgRegistry:
    """后台任务登记处——register 拿自增 id，停止靠协作式 cancel 事件，不硬 kill 线程。"""

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
        """列表展示用，按 id 升序好让输出稳定。"""
        with self._lock:
            now = datetime.now()
            return [
                (tid, d["task"], (now - d["started"]).total_seconds())
                for tid, d in sorted(self._tasks.items())
            ]

    def stop(self, tid: int) -> bool:
        """id 不在(已结束/没这个)返回 False，给上层报错用。"""
        with self._lock:
            d = self._tasks.get(tid)
        # 取出后就放锁——set() 在锁外做，避免和任务回调里的 unregister 抢锁
        if d is None:
            return False
        try:
            d["cancel"].set()
        except Exception:
            return False
        return True


bg_tasks = _BgRegistry()
