# author: bdth
# email: 2074055628@qq.com
# 提醒事项的持久化存储：增删与到期检测，数据落盘到 reminders.json

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "reminders.json"
_FIELDS = {"id", "fire_at", "what", "created_at"}
_STALE_GRACE_S = 2 * 3600.0  # 迟到超过 2h 就直接丢弃——关机一整天再开机时，不该把一堆过期提醒一股脑全弹出来
_LATE_NOTE_AFTER_S = 120.0  # 迟到超过 2min 才加「迟到了」前缀；秒级误差/时钟跳秒别没事找事道歉


@dataclass
class Reminder:
    id: int
    fire_at: str
    what: str
    created_at: str
    kind: str = "say"
    repeat: str = ""


def _step(fire: datetime, repeat: str) -> datetime:
    """把一次触发时间推到下一次。repeat 不认得就当 daily。"""
    rep = (repeat or "").strip().lower()
    if rep == "weekly":
        return fire + timedelta(days=7)
    if rep.startswith("interval:"):
        try:
            mins = max(1, int(rep.split(":", 1)[1]))
        except (ValueError, IndexError):
            mins = 60  # 写坏的 interval: 兜底 1 小时，别崩
        return fire + timedelta(minutes=mins)
    return fire + timedelta(days=1)


def _occurrences(fire: datetime, repeat: str, now: datetime) -> tuple[datetime, datetime]:
    """重复提醒停机后补算用：前者判最近一次该不该补弹，后者拿来重置闹钟。"""
    rep = (repeat or "").strip().lower()
    if rep.startswith("interval:"):
        # 等间隔直接算 —— 别一步步 _step 爬，间隔 1min、停机一周那种能爬上万次
        try:
            mins = max(1, int(rep.split(":", 1)[1]))
        except (ValueError, IndexError):
            mins = 60
        passed = max(0, int((now - fire).total_seconds() // (mins * 60)))
        last_fire = fire + timedelta(minutes=mins * passed)
        return last_fire, last_fire + timedelta(minutes=mins)
    last_fire, nxt = fire, _step(fire, repeat)
    guard = 0
    while nxt <= now and guard < 100000:  # guard 防 _step 算出不前进时死循环
        last_fire, nxt = nxt, _step(nxt, repeat)
        guard += 1
    if nxt <= now:  # 真撞到 guard 上限了，强行从 now 重新起步，别返回过去的点
        last_fire, nxt = now, _step(now, repeat)
    return last_fire, nxt


class ReminderStore:

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: list[Reminder] = self._load()

    def add(self, fire_at: datetime, what: str, kind: str = "say", repeat: str = "") -> Reminder:
        with self._lock:
            reminder = Reminder(
                id=max((r.id for r in self._items), default=0) + 1,
                fire_at=fire_at.isoformat(timespec="seconds"),
                what=what.strip(),
                created_at=datetime.now().isoformat(timespec="seconds"),
                kind=kind if kind in ("say", "do") else "say",
                repeat=(repeat or "").strip(),
            )
            self._items.append(reminder)
            self._save()
            return reminder

    def due(self, now: datetime, take_do: bool = True) -> list[Reminder]:
        """取出到点该弹的提醒并就地消化：一次性的删掉，重复的把 fire_at 推到下次。
        take_do=False 时把 kind=="do"（要执行动作的）留到位 —— 调用方还没准备好执行时先攒着。"""
        with self._lock:
            out: list[Reminder] = []
            survivors: list[Reminder] = []
            changed = False
            for r in self._items:
                fire = self._fire_at(r)
                if fire is None:  # fire_at 烂掉无法解析的：直接交出去让上层删，别永远卡在库里
                    out.append(r)
                    changed = True
                    continue
                if fire > now:
                    survivors.append(r)
                    continue
                if r.kind == "do" and not take_do:
                    survivors.append(r)
                    continue
                late = (now - fire).total_seconds()
                rep = (r.repeat or "").strip()
                if rep:
                    # 重复提醒：算出 ≤now 最近一次有没有过期，再把闹钟重置到下一次，r 本身永不删
                    last_fire, nxt = _occurrences(fire, rep, now)
                    last_late = (now - last_fire).total_seconds()
                    if last_late <= _STALE_GRACE_S:
                        deliver = Reminder(**asdict(r))  # 拷一份交付，原件改 fire_at 接着循环，别污染本次输出
                        if last_late > _LATE_NOTE_AFTER_S and r.kind != "do":
                            deliver.what = f"（这条提醒迟到了一会儿才说）{r.what}"
                        out.append(deliver)
                    r.fire_at = nxt.isoformat(timespec="seconds")
                    survivors.append(r)
                    changed = True
                else:
                    changed = True
                    if late > _STALE_GRACE_S:  # 一次性 + 太老 → 静默丢弃，连「迟到」都不说了
                        continue
                    if late > _LATE_NOTE_AFTER_S and r.kind != "do":
                        r.what = f"（这条提醒迟到了一会儿才说）{r.what}"
                    out.append(r)
            if changed:
                self._items = survivors
                try:
                    self._save()
                except OSError:
                    pass
            return out

    def remove(self, rid: int) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [r for r in self._items if r.id != rid]
            if len(self._items) != before:
                self._save()
                return True
            return False

    def list_all(self) -> list[Reminder]:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._save()

    @staticmethod
    def _fire_at(reminder: Reminder) -> datetime | None:
        try:
            return datetime.fromisoformat(reminder.fire_at)
        except (ValueError, TypeError):
            return None

    def _load(self) -> list[Reminder]:
        """从 reminders.json 读回；文件不在/坏了/格式不对都当空处理，不让启动挂掉。"""
        if not _PATH.exists():
            return []
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        items: list[Reminder] = []
        for entry in data if isinstance(data, list) else []:  # 顶层不是 list 就当没有，逐条挑能用的
            if not (isinstance(entry, dict) and _FIELDS <= entry.keys()):  # 缺必填字段的旧/脏数据跳过
                continue
            try:
                datetime.fromisoformat(str(entry["fire_at"]))  # fire_at 解析不了的整条扔掉，别带病入库
            except ValueError:
                continue
            items.append(
                Reminder(
                    id=int(entry["id"]),
                    fire_at=str(entry["fire_at"]),
                    what=str(entry["what"]),
                    created_at=str(entry["created_at"]),
                    kind=str(entry.get("kind", "say")),
                    repeat=str(entry.get("repeat", "")),
                )
            )
        return items

    def _save(self) -> None:
        atomic_write_text(
            _PATH,
            json.dumps([asdict(r) for r in self._items], ensure_ascii=False, indent=2),
        )


reminders = ReminderStore()
