# author: bdth
# email: 2074055628@qq.com
# 提醒事项的持久化存储：增删与到期检测，数据落盘到 reminders.json

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "reminders.json"
_FIELDS = {"id", "fire_at", "what", "created_at"}
# 过期宽限：原来 600s（10 分钟），一次午休/会议就把提醒静默丢了。放宽到 2 小时，
# 且过期但仍在宽限内的「说」类提醒会标注「迟到」如实告知，而不是默默消失。
_STALE_GRACE_S = 2 * 3600.0
_LATE_NOTE_AFTER_S = 120.0  # 晚于 2 分钟才算「明显迟到」，加标注


@dataclass
class Reminder:
    id: int
    fire_at: str
    what: str
    created_at: str
    kind: str = "say"


class ReminderStore:

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: list[Reminder] = self._load()

    def add(self, fire_at: datetime, what: str, kind: str = "say") -> Reminder:
        with self._lock:
            reminder = Reminder(
                id=max((r.id for r in self._items), default=0) + 1,
                fire_at=fire_at.isoformat(timespec="seconds"),
                what=what.strip(),
                created_at=datetime.now().isoformat(timespec="seconds"),
                kind=kind if kind in ("say", "do") else "say",
            )
            self._items.append(reminder)
            self._save()
            return reminder

    def due(self, now: datetime) -> list[Reminder]:
        with self._lock:
            past = [r for r in self._items if (self._fire_at(r) or now) <= now]
            if not past:
                return []
            fired = {r.id for r in past}
            self._items = [r for r in self._items if r.id not in fired]
            out = []
            for r in past:
                fire = self._fire_at(r)
                if fire is None:
                    out.append(r)  # 时间解析不出来：宁可送达也别静默吞掉
                    continue
                late = (now - fire).total_seconds()
                if late > _STALE_GRACE_S:
                    continue  # 真的太久了（机器关了好几小时）——这条才丢弃
                if late > _LATE_NOTE_AFTER_S and r.kind != "do":
                    # 「说」类标注迟到；「做」类是任务指令，不能往里塞这句免得污染执行
                    r.what = f"（这条提醒迟到了一会儿才说）{r.what}"
                out.append(r)
            # 先把要投递的 out 构造好，最后才写盘：原子写失败时(OSError)也不能把已到期提醒弄丢——
            # 磁盘旧文件因 os.replace 未成功而完好，宁可重启后重报，也绝不静默吞掉本次投递。
            try:
                self._save()
            except OSError:
                pass
            return out

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
                )
            )
        return items

    def _save(self) -> None:
        atomic_write_text(
            _PATH,
            json.dumps([asdict(r) for r in self._items], ensure_ascii=False, indent=2),
        )


reminders = ReminderStore()
