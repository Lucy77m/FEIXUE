# 陪伴统计 记首次相遇时间和互动次数

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "stats.json"
# 挡并发读改写 主线程和多个 daemon 线程都在改 没锁会丢更新
_LOCK = threading.RLock()


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
    with _LOCK:
        data = _load()
        if not data.get("first_seen"):  # 空字符串也算没记过
            data["first_seen"] = datetime.now().isoformat(timespec="seconds")
            _save(data)


def bump_interactions() -> None:
    """互动次数加一"""
    with _LOCK:
        data = _load()
        data["interactions"] = int(data.get("interactions", 0) or 0) + 1
        _save(data)


def get_note(key: str) -> str:
    """读杂项标记"""
    return str(_load().get("note_" + key, "") or "")


def set_note(key: str, value: str) -> None:
    """存杂项标记"""
    with _LOCK:
        data = _load()
        data["note_" + key] = value
        _save(data)


def mark_late_night() -> int:
    """记一次熬夜 返回连续熬了几天 当天重复调用不重计"""
    with _LOCK:
        data = _load()
        today = date.today().isoformat()
        if data.get("last_late") == today:
            return int(data.get("late_streak", 1) or 1)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        streak = int(data.get("late_streak", 0) or 0) + 1 if data.get("last_late") == yesterday else 1
        data["last_late"] = today
        data["late_streak"] = streak
        _save(data)
        return streak


def add_eaten(nbytes: int, nfiles: int = 1) -> None:
    """投喂吃掉的量记账"""
    with _LOCK:
        data = _load()
        data["bytes_eaten"] = int(data.get("bytes_eaten", 0) or 0) + max(0, int(nbytes))
        data["files_eaten"] = int(data.get("files_eaten", 0) or 0) + max(0, int(nfiles))
        _save(data)


def record_fishing(score: int, perfects: int, today: date | None = None) -> dict:
    """记录一局记忆钓鱼；每天仅第一局可获得羁绊。"""
    score = max(0, min(300, int(score)))
    perfects = max(0, min(3, int(perfects)))
    day = (today or date.today()).isoformat()
    with _LOCK:
        data = _load()
        previous = int(data.get("fishing_best", 0) or 0)
        new_best = score > previous
        data["fishing_runs"] = int(data.get("fishing_runs", 0) or 0) + 1
        data["fishing_best"] = max(previous, score)
        data["fishing_perfects"] = int(data.get("fishing_perfects", 0) or 0) + perfects
        bond_awarded = data.get("fishing_bond_date") != day
        if bond_awarded:
            data["fishing_bond_date"] = day
        _save(data)
    return {
        "score": score,
        "best": max(previous, score),
        "new_best": new_best,
        "bond_awarded": bond_awarded,
    }


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
    return {
        "first_seen": first, "days": days,
        "interactions": int(data.get("interactions", 0) or 0),
        "bytes_eaten": int(data.get("bytes_eaten", 0) or 0),
        "files_eaten": int(data.get("files_eaten", 0) or 0),
        "fishing_runs": int(data.get("fishing_runs", 0) or 0),
        "fishing_best": int(data.get("fishing_best", 0) or 0),
        "fishing_perfects": int(data.get("fishing_perfects", 0) or 0),
    }


def is_honeymoon(days_max: int = 3, inter_max: int = 20) -> bool:
    """新桌宠的蜜月期 头几天或互动还少时为真 让它先靠在场挣关系"""
    s = snapshot()
    return s["days"] <= days_max or s["interactions"] < inter_max


def clear() -> None:
    _save({})
