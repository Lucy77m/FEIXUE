# author: bdth
# email: 2074055628@qq.com
# 陪伴统计 记首次相遇时间和互动次数

from __future__ import annotations

import json
from datetime import date, datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "stats.json"


def _load() -> dict:
    """读统计 坏了当空字典"""
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
    """只在第一次写入相遇时间"""
    data = _load()
    if not data.get("first_seen"):  # 空字符串也算没记过
        data["first_seen"] = datetime.now().isoformat(timespec="seconds")
        _save(data)


def bump_interactions() -> None:
    """互动次数加一"""
    data = _load()
    data["interactions"] = int(data.get("interactions", 0) or 0) + 1
    _save(data)


def snapshot() -> dict:
    """给 ui 的汇总 days 现算不落盘"""
    data = _load()
    first = data.get("first_seen")
    days = 0
    if first:
        try:
            # 按日期算差 负数兜成 0
            days = max(0, (date.today() - datetime.fromisoformat(first).date()).days)
        except (ValueError, TypeError):
            days = 0
    return {"first_seen": first, "days": days, "interactions": int(data.get("interactions", 0) or 0)}


def clear() -> None:
    _save({})
