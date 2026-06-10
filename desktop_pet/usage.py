# author: bdth
# email: 2074055628@qq.com
# token 用量计量 累计输入输出和缓存命中 按天落盘

from __future__ import annotations

import json
import threading
from datetime import date

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "usage.json"


class UsageMeter:
    """token 用量计量 session 和 today 两套桶"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session = {"input": 0, "output": 0, "cached": 0, "calls": 0}
        self._today = {"date": date.today().isoformat(), "input": 0, "output": 0, "cached": 0, "calls": 0}
        self._load()

    def _load(self) -> None:
        """捞回今天的累计 坏了当 0"""
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        # 隔天的丢掉 脏值挡掉
        if isinstance(data, dict) and data.get("date") == date.today().isoformat():
            for k in ("input", "output", "cached", "calls"):
                v = data.get(k)
                if isinstance(v, int) and v >= 0:
                    self._today[k] = v

    def _save(self) -> None:
        # 写不进去静默吞掉
        try:
            atomic_write_text(_PATH, json.dumps(self._today, ensure_ascii=False))
        except Exception:
            pass

    def add(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
        """一次调用的用量累加进两套桶"""
        with self._lock:
            today = date.today().isoformat()
            # 跨天把 today 翻篇 session 不动
            if self._today["date"] != today:
                self._today = {"date": today, "input": 0, "output": 0, "cached": 0, "calls": 0}
            for bucket in (self._session, self._today):
                bucket["input"] += max(0, int(input_tokens))
                bucket["output"] += max(0, int(output_tokens))
                bucket["cached"] += max(0, int(cached_tokens))
                bucket["calls"] += 1
            self._save()

    def snapshot(self) -> tuple[dict, dict]:
        """取 session 和 today 的拷贝给 ui"""
        with self._lock:
            return dict(self._session), dict(self._today)


meter = UsageMeter()
