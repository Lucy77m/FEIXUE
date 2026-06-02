# author: bdth
# email: 2074055628@qq.com
# 情景记忆日志：把带时间戳的事件去重后存进 JSON，并组织成聊天上下文

from __future__ import annotations

import json
import threading
from datetime import datetime
from difflib import SequenceMatcher

from desktop_pet.settings import DATA_DIR, atomic_write_text

_PATH = DATA_DIR / "journal.json"
_KEEP = 40
_CONTEXT_N = 6
_DEDUP_RATIO = 0.86
_DEDUP_LOOKBACK = 6
# 写者有两个：反思 daemon 线程（add）与主线程（clear via forget_all）。
# add 是 load→去重→append→save 的读改写，不加锁两个并发 add 会丢条目。
_LOCK = threading.RLock()


def _load() -> list[dict]:
    if not _PATH.exists():
        return []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [e for e in data if isinstance(e, dict) and "text" in e] if isinstance(data, list) else []


def _save(entries: list[dict]) -> None:
    try:
        atomic_write_text(_PATH, json.dumps(entries[-_KEEP:], ensure_ascii=False, indent=2))
    except OSError:
        pass


def add(text: str) -> None:
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


def as_context(n: int = _CONTEXT_N) -> str:
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
    try:
        when = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    today = datetime.now().date()
    days = (today - when.date()).days
    if days <= 0:
        return "今天 "
    if days == 1:
        return "昨天 "
    if days <= 6:
        return f"{days}天前 "
    return f"{when:%m-%d} "
