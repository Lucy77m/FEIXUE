# 后台任务注册表 可列出可协作式停止

from __future__ import annotations

import threading
from datetime import datetime


class _BgRegistry:
    """后台任务登记处"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[int, dict] = {}
        self._seq = 0

    def register(self, task: str, cancel: threading.Event) -> int:
        # started 先留空 任务可能还卡在并发信号量上排队 真正开跑才盖时间戳
        # 登记早于信号量 排队期间也能 stop 别把排队时间算进已跑
        with self._lock:
            self._seq += 1
            tid = self._seq
            self._tasks[tid] = {"task": task, "started": None, "cancel": cancel}
            return tid

    def mark_started(self, tid: int) -> None:
        """抢到并发槽真正开跑时盖时间戳"""
        with self._lock:
            d = self._tasks.get(tid)
            if d is not None:
                d["started"] = datetime.now()

    def unregister(self, tid: int) -> None:
        with self._lock:
            self._tasks.pop(tid, None)

    def snapshot(self) -> list[tuple[int, str, float]]:
        """返回任务快照 按id升序 还在排队未开跑的已跑时长记 0"""
        with self._lock:
            now = datetime.now()
            return [
                (tid, d["task"], (now - d["started"]).total_seconds() if d["started"] else 0.0)
                for tid, d in sorted(self._tasks.items())
            ]

    def stop(self, tid: int) -> bool:
        """停止任务 不存在返回False"""
        with self._lock:
            d = self._tasks.get(tid)
        # set在锁外做
        if d is None:
            return False
        try:
            d["cancel"].set()
        except Exception:
            return False
        return True


bg_tasks = _BgRegistry()
