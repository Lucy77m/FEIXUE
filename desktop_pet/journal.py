# 情景记忆 事件去重存json 组织成聊天上下文

from __future__ import annotations

import json
import threading
from datetime import datetime
from difflib import SequenceMatcher

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "journal.json"
_KEEP = 40  # 只留最近条数
_CONTEXT_N = 6  # 喂给模型的默认条数
_DEDUP_RATIO = 0.86  # 去重相似度阈值
_DEDUP_LOOKBACK = 6  # 只跟最近几条比
_LOCK = threading.RLock()  # 挡并发读改写


def _load() -> list[dict]:
    """读全表 不在或写坏当空"""
    if not _PATH.exists():
        return []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    # 滤掉脏条目
    return [e for e in data if isinstance(e, dict) and "text" in e] if isinstance(data, list) else []


def _save(entries: list[dict]) -> None:
    """裁到上限后整文件原子覆写"""
    try:
        atomic_write_text(_PATH, json.dumps(entries[-_KEEP:], ensure_ascii=False, indent=2))
    except OSError:
        pass


def add(text: str) -> None:
    """记一条事件 近似重复直接丢"""
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:
        entries = _load()
        for prior in entries[-_DEDUP_LOOKBACK:]:
            if SequenceMatcher(None, text, prior.get("text", "")).ratio() >= _DEDUP_RATIO:
                return
        entries.append({"at": datetime.now().isoformat(timespec="minutes"), "text": text})
        _save(entries)


def recent(n: int = _CONTEXT_N) -> list[dict]:
    return _load()[-n:]


def diary(n: int = 20) -> list[dict]:
    """给控制面板翻的日记 最近n条 新的在上 带口语日期"""
    entries = _load()[-n:]
    return [{"when": _friendly(e.get("at", "")).strip(), "text": e.get("text", "")}
            for e in reversed(entries)]


def as_context(n: int = _CONTEXT_N) -> str:
    """最近n条拼成喂给模型的记忆段 没记录回空串"""
    entries = recent(n)
    if not entries:
        return ""
    lines = []
    for e in entries:
        when = _friendly(e.get("at", ""))
        lines.append(f"- {when}{e['text']}")
    body = "\n".join(lines)
    return (
        "【最近发生的事】这是你和用户近来一起经历/聊过的事（你的情景记忆，按时间）。"
        "聊天时可以自然带出来、做承接和回顾，但别生硬复述：\n" + body
    )


def count() -> int:
    return len(_load())


def clear() -> None:
    with _LOCK:
        _save([])


def _friendly(iso: str) -> str:
    """iso时间转口语"""
    try:
        when = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""  # 时间戳坏了回空
    today = datetime.now().date()
    days = (today - when.date()).days
    if days <= 0:  # 负数天当今天
        return "今天 "
    if days == 1:
        return "昨天 "
    if days <= 6:
        return f"{days}天前 "
    return f"{when:%m-%d} "  # 超一周回月日
