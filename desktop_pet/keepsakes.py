"""Persistent keepsakes created from completed desktop-workflow tasks."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text


_PATH = DATA_DIR / "keepsakes.json"
_KEEP = 64
_LOCK = threading.RLock()


def _load() -> list[dict]:
    if not _PATH.exists():
        return []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("id")]


def _save(items: list[dict]) -> None:
    atomic_write_text(_PATH, json.dumps(items[-_KEEP:], ensure_ascii=False, indent=2))


def add(kind: str, title: str, detail: str, *, source: str = "", context: str = "") -> dict:
    item = {
        "id": uuid.uuid4().hex,
        "kind": (kind or "file")[:24],
        "title": " ".join((title or "完成了一件事").split())[:80],
        "detail": " ".join((detail or "任务已完成").split())[:600],
        "source": " ".join((source or "").split())[:260],
        "context": " ".join((context or "").split())[:120],
        "at": datetime.now().isoformat(timespec="minutes"),
    }
    with _LOCK:
        items = _load()
        items.append(item)
        _save(items)
    return item


def recent(n: int = 20) -> list[dict]:
    with _LOCK:
        return list(reversed(_load()[-max(0, n):]))


def get(item_id: str) -> dict | None:
    if not item_id:
        return None
    with _LOCK:
        return next((item for item in _load() if item.get("id") == item_id), None)


def count() -> int:
    with _LOCK:
        return len(_load())


def clear() -> None:
    with _LOCK:
        _save([])
