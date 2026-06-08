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
_STALE_GRACE_S = 2 * 3600.0
_LATE_NOTE_AFTER_S = 120.0


@dataclass
class Reminder:
    id: int
    fire_at: str
    what: str
    created_at: str
    kind: str = "say"
    repeat: str = ""


def _step(fire: datetime, repeat: str) -> datetime:
    rep = (repeat or "").strip().lower()
    if rep == "weekly":
        return fire + timedelta(days=7)
    if rep.startswith("interval:"):
        try:
            mins = max(1, int(rep.split(":", 1)[1]))
        except (ValueError, IndexError):
            mins = 60
        return fire + timedelta(minutes=mins)
    return fire + timedelta(days=1)


def _occurrences(fire: datetime, repeat: str, now: datetime) -> tuple[datetime, datetime]:
    """返回 (≤now 的最近一次触发点, >now 的下一次触发点)。
    关机错过多次时：只投递「最近一次」(若仍在宽限内)，下次推进到未来——不把错过的全补(免刷屏)。"""
    rep = (repeat or "").strip().lower()
    if rep.startswith("interval:"):
        try:
            mins = max(1, int(rep.split(":", 1)[1]))
        except (ValueError, IndexError):
            mins = 60
        passed = max(0, int((now - fire).total_seconds() // (mins * 60)))
        last_fire = fire + timedelta(minutes=mins * passed)
        return last_fire, last_fire + timedelta(minutes=mins)
    last_fire, nxt = fire, _step(fire, repeat)
    guard = 0
    while nxt <= now and guard < 100000:
        last_fire, nxt = nxt, _step(nxt, repeat)
        guard += 1
    if nxt <= now:
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
        with self._lock:
            out: list[Reminder] = []
            survivors: list[Reminder] = []
            changed = False
            for r in self._items:
                fire = self._fire_at(r)
                if fire is None:
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
                    last_fire, nxt = _occurrences(fire, rep, now)
                    last_late = (now - last_fire).total_seconds()
                    if last_late <= _STALE_GRACE_S:
                        deliver = Reminder(**asdict(r))
                        if last_late > _LATE_NOTE_AFTER_S and r.kind != "do":
                            deliver.what = f"（这条提醒迟到了一会儿才说）{r.what}"
                        out.append(deliver)
                    r.fire_at = nxt.isoformat(timespec="seconds")
                    survivors.append(r)
                    changed = True
                else:
                    changed = True
                    if late > _STALE_GRACE_S:
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
        if not _PATH.exists():
            return []
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        items: list[Reminder] = []
        for entry in data if isinstance(data, list) else []:
            if not (isinstance(entry, dict) and _FIELDS <= entry.keys()):
                continue
            try:
                datetime.fromisoformat(str(entry["fire_at"]))
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
