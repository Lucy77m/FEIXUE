"""Persistent physical objects that make up Xiaofeixue's workshop world."""

from __future__ import annotations

import json
import random
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from desktop_pet import keepsakes
from desktop_pet.settings import DATA_DIR, atomic_write_text


_PATH = DATA_DIR / "world.json"
_VERSION = 1
_SHELF_SLOTS = 15
_LOCK = threading.RLock()


@dataclass
class WorldObject:
    id: str
    kind: str
    title: str
    summary: str
    source: str
    project_key: str
    state: str
    zone: str
    slot: int | None
    placement: str
    origin_keepsake_id: str
    created_at: str
    updated_at: str
    last_revisited_at: str
    revisit_count: int

    @classmethod
    def from_dict(cls, raw: dict) -> WorldObject | None:
        if not isinstance(raw, dict) or not raw.get("id"):
            return None
        try:
            slot = raw.get("slot")
            slot = int(slot) if slot is not None else None
            return cls(
                id=str(raw["id"]), kind=str(raw.get("kind", "book"))[:24],
                title=str(raw.get("title", ""))[:120], summary=str(raw.get("summary", ""))[:1200],
                source=str(raw.get("source", ""))[:520], project_key=str(raw.get("project_key", ""))[:80],
                state=str(raw.get("state", "interrupted")), zone=str(raw.get("zone", "desk")),
                slot=slot, placement="manual" if raw.get("placement") == "manual" else "auto",
                origin_keepsake_id=str(raw.get("origin_keepsake_id", "")),
                created_at=str(raw.get("created_at", "")), updated_at=str(raw.get("updated_at", "")),
                last_revisited_at=str(raw.get("last_revisited_at", "")),
                revisit_count=max(0, int(raw.get("revisit_count", 0) or 0)),
            )
        except (TypeError, ValueError):
            return None


class WorldStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _PATH
        self._lock = _LOCK if path is None else threading.RLock()
        with self._lock:
            data = self._read()
            changed = False
            for item in data["objects"]:
                if item.state == "reading":
                    item.state = "interrupted"
                    item.zone = "desk"
                    item.slot = None
                    item.updated_at = _now()
                    changed = True
                elif item.state == "carried":
                    item.state = "shelved"
                    item.zone = "shelf"
                    item.updated_at = _now()
                    changed = True
            if changed:
                self._write(data)

    @staticmethod
    def project_key(source: str) -> str:
        raw = (source or "").split(";")[0].strip()
        if not raw:
            return "misc"
        try:
            path = Path(raw)
            return (path.parent.name or path.stem or "misc").strip().lower()[:80]
        except (OSError, ValueError):
            return "misc"

    def create_reading(self, title: str, source: str, project_key: str = "") -> WorldObject:
        now = _now()
        item = WorldObject(
            id=uuid.uuid4().hex, kind="book", title=" ".join((title or "document").split())[:120],
            summary="", source=(source or "")[:520],
            project_key=(project_key or self.project_key(source))[:80], state="reading",
            zone="desk", slot=None, placement="auto", origin_keepsake_id="",
            created_at=now, updated_at=now, last_revisited_at="", revisit_count=0,
        )
        with self._lock:
            data = self._read()
            data["objects"].append(item)
            self._write(data)
        return item

    def complete(self, item_id: str, summary: str, origin_keepsake_id: str) -> WorldObject | None:
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None:
                return None
            item.summary = " ".join((summary or "").split())[:1200]
            item.origin_keepsake_id = origin_keepsake_id
            item.state = "shelved"
            item.zone = "shelf"
            item.updated_at = _now()
            self._auto_arrange(data["objects"])
            self._write(data)
            return WorldObject(**asdict(item))

    def interrupt(self, item_id: str) -> WorldObject | None:
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None:
                return None
            item.state, item.zone, item.slot = "interrupted", "desk", None
            item.updated_at = _now()
            self._write(data)
            return WorldObject(**asdict(item))

    def get(self, item_id: str) -> WorldObject | None:
        with self._lock:
            item = _find(self._read()["objects"], item_id)
            return WorldObject(**asdict(item)) if item is not None else None

    def visible_books(self) -> list[WorldObject]:
        with self._lock:
            books = [item for item in self._read()["objects"]
                     if item.zone == "shelf" and item.slot is not None and item.state == "shelved"]
            return [WorldObject(**asdict(item)) for item in sorted(books, key=lambda x: x.slot)]

    def archived(self) -> list[WorldObject]:
        with self._lock:
            return [WorldObject(**asdict(item)) for item in self._read()["objects"]
                    if item.zone == "archived"]

    def desk_objects(self) -> list[WorldObject]:
        with self._lock:
            return [WorldObject(**asdict(item)) for item in self._read()["objects"]
                    if item.zone == "desk" and item.state in {"reading", "interrupted"}]

    def carry(self, item_id: str) -> WorldObject | None:
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None or item.state != "shelved":
                return None
            item.state, item.zone, item.updated_at = "carried", "carried", _now()
            self._write(data)
            return WorldObject(**asdict(item))

    def reshelve(self, item_id: str) -> WorldObject | None:
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None or item.state != "carried":
                return None
            item.state, item.zone, item.updated_at = "shelved", "shelf", _now()
            if item.slot is None:
                item.placement = "auto"
                self._auto_arrange(data["objects"])
            self._write(data)
            return WorldObject(**asdict(item))

    def move(self, item_id: str, slot: int) -> bool:
        if not 0 <= int(slot) < _SHELF_SLOTS:
            return False
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None or item.state != "shelved":
                return False
            old_slot = item.slot if item.zone == "shelf" else None
            occupant = next((obj for obj in data["objects"]
                             if obj.id != item.id and obj.zone == "shelf" and obj.slot == slot), None)
            if occupant is not None:
                if old_slot is None:
                    occupant.zone, occupant.slot = "archived", None
                else:
                    occupant.zone, occupant.slot, occupant.placement = "shelf", old_slot, "manual"
                occupant.updated_at = _now()
            item.zone, item.slot, item.placement = "shelf", int(slot), "manual"
            item.updated_at = _now()
            self._write(data)
            return True

    def choose_revisit(self, context: str, now: datetime | None = None) -> WorldObject | None:
        now = now or datetime.now()
        cutoff = now - timedelta(hours=24)
        low = (context or "").lower()
        with self._lock:
            candidates = []
            for item in self._read()["objects"]:
                if item.state != "shelved" or item.zone != "shelf":
                    continue
                last = _parse(item.last_revisited_at)
                if last is not None and last >= cutoff:
                    continue
                age_anchor = last or _parse(item.updated_at) or now
                age_hours = max(0.0, (now - age_anchor).total_seconds() / 3600)
                match = 1000.0 if item.project_key and item.project_key in low else 0.0
                score = match + min(age_hours, 720.0) - item.revisit_count * 18.0 + random.random()
                candidates.append((score, item))
            if not candidates:
                return None
            item = max(candidates, key=lambda pair: pair[0])[1]
            return WorldObject(**asdict(item))

    def revisit_allowed(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        with self._lock:
            meta = self._read()["meta"]
            if meta.get("revisit_day") == now.date().isoformat() and int(meta.get("revisit_count", 0)) >= 2:
                return False
            last = _parse(str(meta.get("last_revisit_at", "")))
            return last is None or now - last >= timedelta(hours=6)

    def ai_revisit_allowed(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        with self._lock:
            return self._read()["meta"].get("last_ai_revisit_day") != now.date().isoformat()

    def record_revisit(self, item_id: str, used_ai: bool, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        with self._lock:
            data = self._read()
            item = _find(data["objects"], item_id)
            if item is None:
                return False
            stamp = now.isoformat(timespec="seconds")
            item.last_revisited_at = stamp
            item.revisit_count += 1
            item.updated_at = stamp
            meta = data["meta"]
            day = now.date().isoformat()
            if meta.get("revisit_day") != day:
                meta["revisit_day"], meta["revisit_count"] = day, 0
            meta["revisit_count"] = int(meta.get("revisit_count", 0)) + 1
            meta["last_revisit_at"] = stamp
            if used_ai:
                meta["last_ai_revisit_day"] = day
            self._write(data)
            return True

    def migrate_keepsakes(self) -> int:
        with self._lock:
            data = self._read()
            known = {item.origin_keepsake_id for item in data["objects"] if item.origin_keepsake_id}
            added = 0
            for source in reversed(keepsakes.recent(64)):
                if source.get("kind") != "book" or source.get("id") in known:
                    continue
                at = str(source.get("at", "")) or _now()
                data["objects"].append(WorldObject(
                    id=uuid.uuid4().hex, kind="book", title=str(source.get("title", ""))[:120],
                    summary=str(source.get("detail", ""))[:1200], source=str(source.get("source", ""))[:520],
                    project_key=self.project_key(str(source.get("source", ""))), state="shelved",
                    zone="shelf", slot=None, placement="auto",
                    origin_keepsake_id=str(source.get("id", "")), created_at=at, updated_at=at,
                    last_revisited_at="", revisit_count=0,
                ))
                known.add(str(source.get("id", "")))
                added += 1
            if added:
                self._auto_arrange(data["objects"])
                self._write(data)
            return added

    def clear(self) -> None:
        with self._lock:
            self._write({"version": _VERSION, "objects": [], "meta": {}})

    @staticmethod
    def _auto_arrange(objects: list[WorldObject]) -> None:
        reserved = {item.slot for item in objects
                    if item.slot is not None and (
                        item.state == "carried" or (
                            item.state == "shelved" and item.zone == "shelf"
                            and item.placement == "manual"
                        )
                    )}
        free = [slot for slot in range(_SHELF_SLOTS) if slot not in reserved]
        auto = [item for item in objects if item.state == "shelved" and item.placement == "auto"]
        groups: dict[str, list[WorldObject]] = {}
        for item in auto:
            groups.setdefault(item.project_key or "misc", []).append(item)
        ordered_groups = sorted(
            groups.values(), key=lambda group: max(item.updated_at for item in group), reverse=True,
        )
        ordered = []
        for group in ordered_groups:
            ordered.extend(sorted(group, key=lambda item: item.created_at))
        for index, item in enumerate(ordered):
            if index < len(free):
                item.zone, item.slot = "shelf", free[index]
            else:
                item.zone, item.slot = "archived", None

    def _read(self) -> dict:
        if not self._path.exists():
            return {"version": _VERSION, "objects": [], "meta": {}}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": _VERSION, "objects": [], "meta": {}}
        objects = []
        for item in raw.get("objects", []) if isinstance(raw, dict) else []:
            parsed = WorldObject.from_dict(item)
            if parsed is not None:
                objects.append(parsed)
        meta = raw.get("meta", {}) if isinstance(raw, dict) and isinstance(raw.get("meta"), dict) else {}
        return {"version": _VERSION, "objects": objects, "meta": dict(meta)}

    def _write(self, data: dict) -> None:
        payload = {
            "version": _VERSION,
            "objects": [asdict(item) for item in data["objects"]],
            "meta": data.get("meta", {}),
        }
        atomic_write_text(self._path, json.dumps(payload, ensure_ascii=False, indent=2))


def _find(objects: list[WorldObject], item_id: str) -> WorldObject | None:
    return next((item for item in objects if item.id == item_id), None)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


_world: WorldStore | None = None
_world_lock = threading.Lock()


def get_world() -> WorldStore:
    """延迟初始化，避免 import 时触发文件 I/O。"""
    global _world
    if _world is None:
        with _world_lock:
            if _world is None:
                _world = WorldStore()
    return _world
