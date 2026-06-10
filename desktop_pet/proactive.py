# author: bdth
# email: 2074055628@qq.com
# 主动搭话调度器：按活跃度等级控制桌宠每天主动发起对话的时机与次数，状态持久化到磁盘

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "proactive.json"

# 档位 → (间隔下限秒, 间隔上限秒, 每日上限)。下次时机在 [下限,上限] 里随机取，省得每天卡点搭话像闹钟。
LEVELS: dict[str, tuple[float, float, int]] = {
    "安静": (90 * 60, 180 * 60, 2),
    "正常": (40 * 60, 90 * 60, 4),
    "话痨": (15 * 60, 35 * 60, 8),
}
_DEFAULT_LEVEL = "正常"

# 刚说完话别立刻又"欢迎回来"——回到桌面这种触发至少隔 25 分钟才算一次新会面，否则烦人。
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
        """到点该主动搭话了没。次数到顶/没到时机都返回 False。"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        if self._state.count >= cap:
            return False
        # 冷启动/状态文件被删：先排一次下次时机再说，这轮不触发，免得刚开机就冒泡。
        if self._state.next_at is None:
            self.schedule_next(now, level)
            return False
        nxt = _parse(self._state.next_at)
        return nxt is not None and now >= nxt

    def welcome_ready(self, now: datetime, level: str) -> bool:
        """回到桌面时该不该打招呼。走的是 _WELCOME_MIN_S 冷却，跟 ready 的随机时机两套逻辑。"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        if self._state.count >= cap:
            return False
        last = _parse(self._state.last_at) if self._state.last_at else None
        return last is None or (now - last).total_seconds() >= _WELCOME_MIN_S

    def record(self, now: datetime, level: str) -> None:
        """每次搭完话调一下，计数才会涨；不调的话 defer/welcome 那套永远不到上限。"""
        self._roll_day(now)
        self._state.last_at = now.isoformat(timespec="seconds")
        self._state.count += 1
        self.schedule_next(now, level)

    def schedule_next(self, now: datetime, level: str) -> None:
        cmin, cmax, _cap = _params(level)
        self._state.next_at = (now + timedelta(seconds=random.uniform(cmin, cmax))).isoformat(timespec="seconds")
        self._save()

    def defer(self, now: datetime, level: str) -> None:
        """到点了但不方便搭话（用户在忙/全屏等），不计数，往后重排一轮。"""
        self.schedule_next(now, level)

    def today(self, now: datetime, level: str) -> tuple[int, int]:
        """给控制面板显示用，(已搭话次数, 上限) —— 上限随档位变，所以连着一起返。"""
        self._roll_day(now)
        _cmin, _cmax, cap = _params(level)
        return self._state.count, cap

    def _roll_day(self, now: datetime) -> None:
        # 跨天就清零计数——每个公开方法进来都先滚一下，省得隔夜还卡在昨天的上限里。
        today = now.date().isoformat()
        if self._state.day != today:
            self._state.day = today
            self._state.count = 0
            self._save()

    def _load(self) -> _State:
        # 状态文件坏了/被手改/不是 dict，一律退回全新 _State，绝不让启动崩。
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
            # count 可能被写成字符串/负数/乱码，isdigit 兜一道，不合法就当 0。
            count=int(data.get("count", 0)) if str(data.get("count", 0)).isdigit() else 0,
        )

    def _save(self) -> None:
        # 写盘失败（磁盘满/权限）就静默吞掉——主动搭话的计时不值得为此报错打断用户。
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
