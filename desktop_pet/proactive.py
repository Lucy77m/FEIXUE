# author: bdth
# email: 2074055628@qq.com
# 主动搭话调度 按档位控制每天搭话的时机和次数 状态落盘

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "proactive.json"

# 档位对应间隔上下限秒和每日上限
LEVELS: dict[str, tuple[float, float, int]] = {
    "安静": (90 * 60, 180 * 60, 2),
    "正常": (40 * 60, 90 * 60, 4),
    "话痨": (15 * 60, 35 * 60, 8),
}
_DEFAULT_LEVEL = "正常"

# 欢迎语最小间隔秒数
_WELCOME_MIN_S = 25 * 60.0


def _params(level: str) -> tuple[float, float, int]:
    return LEVELS.get(level, LEVELS[_DEFAULT_LEVEL])


@dataclass
class _State:
    last_at: str | None = None
    next_at: str | None = None
    day: str | None = None
    count: int = 0


class ProactiveTimer:

    def __init__(self) -> None:
        self._state = self._load()

    def ready(self, now: datetime, level: str) -> bool:
        """到点该不该主动搭话"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        if self._state.count >= cap:
            return False
        # 没排过时机就先排一次 这轮不触发
        if self._state.next_at is None:
            self.schedule_next(now, level)
            return False
        nxt = _parse(self._state.next_at)
        return nxt is not None and now >= nxt

    def welcome_ready(self, now: datetime, level: str) -> bool:
        """回到桌面该不该打招呼"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        if self._state.count >= cap:
            return False
        last = _parse(self._state.last_at) if self._state.last_at else None
        return last is None or (now - last).total_seconds() >= _WELCOME_MIN_S

    def record(self, now: datetime, level: str) -> None:
        """记一次搭话并重排下次时机"""
        self._roll_day(now)
        self._state.last_at = now.isoformat(timespec="seconds")
        self._state.count += 1
        self.schedule_next(now, level)

    def schedule_next(self, now: datetime, level: str) -> None:
        cmin, cmax, _cap = _params(level)
        self._state.next_at = (now + timedelta(seconds=random.uniform(cmin, cmax))).isoformat(timespec="seconds")
        self._save()

    def defer(self, now: datetime, level: str) -> None:
        """不计数 往后重排一轮"""
        self.schedule_next(now, level)

    def today(self, now: datetime, level: str) -> tuple[int, int]:
        """返回今日已搭话次数和上限"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        return self._state.count, cap

    def _roll_day(self, now: datetime) -> None:
        # 跨天清零计数
        today = now.date().isoformat()
        if self._state.day != today:
            self._state.day = today
            self._state.count = 0
            self._save()

    def _load(self) -> _State:
        # 状态文件坏了退回全新 _State
        if not _PATH.exists():
            return _State()
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _State()
        if not isinstance(data, dict):
            return _State()
        return _State(
            last_at=data.get("last_at"),
            next_at=data.get("next_at"),
            day=data.get("day"),
            # count 不合法就当 0
            count=int(data.get("count", 0)) if str(data.get("count", 0)).isdigit() else 0,
        )

    def _save(self) -> None:
        # 写盘失败静默吞掉
        try:
            atomic_write_text(_PATH, json.dumps(self._state.__dict__, ensure_ascii=False, indent=2))
        except OSError:
            pass


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


proactive = ProactiveTimer()
