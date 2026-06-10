# author: bdth
# email: 2074055628@qq.com
# 轻量陪伴统计:记录首次相遇时间与累计互动次数。

from __future__ import annotations

import json
from datetime import date, datetime

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "stats.json"


def _load() -> dict:
    """读 stats.json，文件缺失/损坏/被人手改成非 dict 都当空字典——统计坏了不能拖垮启动。"""
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
    """只在第一次写入相遇时间，之后不动——重装/清缓存别覆盖掉这天。"""
    data = _load()
    if not data.get("first_seen"):  # 空字符串也算没记过，重新落
        data["first_seen"] = datetime.now().isoformat(timespec="seconds")
        _save(data)


def bump_interactions() -> None:
    """互动次数 +1。int(... or 0) 兜旧档里被存成字符串/None 的脏值，免得 +1 炸。"""
    data = _load()
    data["interactions"] = int(data.get("interactions", 0) or 0) + 1
    _save(data)


def snapshot() -> dict:
    """给 UI 用的汇总，days 现算不落盘——存了反而要天天更新。"""
    data = _load()
    first = data.get("first_seen")
    days = 0
    if first:
        try:
            # 只按日期算差，跨时区/改系统时间也不至于出负数——max(0,...) 再兜一道
            days = max(0, (date.today() - datetime.fromisoformat(first).date()).days)
        except (ValueError, TypeError):
            days = 0
    return {"first_seen": first, "days": days, "interactions": int(data.get("interactions", 0) or 0)}


def clear() -> None:
    _save({})
