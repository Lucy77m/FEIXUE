# author: bdth
# email: 2074055628@qq.com
# 轻量陪伴统计:记录首次相遇时间与累计互动次数。

from __future__ import annotations

import json
from datetime import date, datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "stats.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    try:
        atomic_write_text(_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    except OSError:
        pass


def mark_first_seen() -> None:
    data = _load()
    if not data.get("first_seen"):
        data["first_seen"] = datetime.now().isoformat(timespec="seconds")
        _save(data)


def bump_interactions() -> None:
    data = _load()
    data["interactions"] = int(data.get("interactions", 0) or 0) + 1
    _save(data)


def snapshot() -> dict:
    data = _load()
    first = data.get("first_seen")
    days = 0
    if first:
        try:
            days = max(0, (date.today() - datetime.fromisoformat(first).date()).days)
        except (ValueError, TypeError):
            days = 0
    return {"first_seen": first, "days": days, "interactions": int(data.get("interactions", 0) or 0)}


def clear() -> None:
    _save({})
