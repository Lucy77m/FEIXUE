# author: bdth
# email: 2074055628@qq.com
# token 用量计量器：累计输入/输出/缓存命中，按天持久化——为大上下文（Claude 等）的成本可见性打底

from __future__ import annotations

import json
import threading
from datetime import date

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "usage.json"


class UsageMeter:
    """token 用量计量：session（本次进程）+ today（按天）两套桶，跨天自动归零，today 落盘 usage.json。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session = {"input": 0, "output": 0, "cached": 0, "calls": 0}
        self._today = {"date": date.today().isoformat(), "input": 0, "output": 0, "cached": 0, "calls": 0}
        self._load()

    def _load(self) -> None:
        """启动时只捞回今天的累计——文件缺失/损坏/隔天的一律当 0，不报错。"""
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        # 存的是昨天（或更早）的就丢掉，today 从 0 起；顺手挡掉负数/非 int 的脏值
        if isinstance(data, dict) and data.get("date") == date.today().isoformat():
            for k in ("input", "output", "cached", "calls"):
                v = data.get(k)
                if isinstance(v, int) and v >= 0:
                    self._today[k] = v

    def _save(self) -> None:
        # 计量是旁路——盘满/无权限写不进去也只能咽下，绝不能因为记账失败拖垮主流程
        try:
            atomic_write_text(_PATH, json.dumps(self._today, ensure_ascii=False))
        except Exception:
            pass

    def add(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
        """一次调用的用量累加进两套桶——多线程同时回调，全程持锁。"""
        with self._lock:
            today = date.today().isoformat()
            # 进程跨午夜还活着：第一笔新账就把 today 翻篇，session 不动（要看本次开机以来总量）
            if self._today["date"] != today:
                self._today = {"date": today, "input": 0, "output": 0, "cached": 0, "calls": 0}
            for bucket in (self._session, self._today):
                bucket["input"] += max(0, int(input_tokens))  # API 偶尔回 None/负数，max(0,) 兜底别污染累计
                bucket["output"] += max(0, int(output_tokens))
                bucket["cached"] += max(0, int(cached_tokens))
                bucket["calls"] += 1
            self._save()

    def snapshot(self) -> tuple[dict, dict]:
        """取 (session, today) 给 UI 显示——返回拷贝，别让面板拿着内部 dict 乱动。"""
        with self._lock:
            return dict(self._session), dict(self._today)


meter = UsageMeter()
