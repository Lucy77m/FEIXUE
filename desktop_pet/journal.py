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
_KEEP = 40  # 只留最近 40 条 —— 情景记忆不是档案，旧的让它自然滚掉
_CONTEXT_N = 6  # 喂给模型的默认条数，多了挤占上下文、还容易让它复读流水账
_DEDUP_RATIO = 0.86  # 相似度阈值：同一件事换种说法（例：「打开了 VSCode」「VSCode 开好了」）算重复
_DEDUP_LOOKBACK = 6  # 只跟最近 6 条比 —— 隔得远的就算字面像也是另一回事，没必要全表两两比
_LOCK = threading.RLock()  # add/clear 都读改写整个文件，可重入锁挡住并发互踩


def _load() -> list[dict]:
    """读全表 —— 文件不在/写坏(断电、半截 JSON)都当空记忆，绝不抛给上层"""
    if not _PATH.exists():
        return []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    # 手改过或旧版本格式：顶层不是 list、缺 text 的脏条目一律滤掉，别让下游崩
    return [e for e in data if isinstance(e, dict) and "text" in e] if isinstance(data, list) else []


def _save(entries: list[dict]) -> None:
    """落盘前裁到 _KEEP 条 —— 整文件原子覆写，写失败就算了，记忆丢一条不至于让程序挂"""
    try:
        atomic_write_text(_PATH, json.dumps(entries[-_KEEP:], ensure_ascii=False, indent=2))
    except OSError:
        pass


def add(text: str) -> None:
    """记一条事件，近似重复的直接丢 —— agent 循环里同一动作常被反复上报，不去重日志全是水"""
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:
        entries = _load()
        for prior in entries[-_DEDUP_LOOKBACK:]:
            if SequenceMatcher(None, text, prior.get("text", "")).ratio() >= _DEDUP_RATIO:
                return
        # 时间戳精确到分钟就够 —— 情景记忆用不上秒，也省得 JSON 里全是噪声
        entries.append({"at": datetime.now().isoformat(timespec="minutes"), "text": text})
        _save(entries)


def recent(n: int = _CONTEXT_N) -> list[dict]:
    return _load()[-n:]


def as_context(n: int = _CONTEXT_N) -> str:
    """把最近 n 条拼成喂给模型的记忆段；没记录就回空串，让上层别白塞一截标题进 prompt"""
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
    """ISO 时间转口语：今天/昨天/N天前/月-日 —— 给模型看的，越像人说话越好"""
    try:
        when = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""  # 时间戳坏了就只留正文，不带前缀，别让一条脏数据噎住整段
    today = datetime.now().date()
    days = (today - when.date()).days
    if days <= 0:  # <0 兜底：改过系统时间/时钟跳到记录之前，仍当「今天」别冒出负数天
        return "今天 "
    if days == 1:
        return "昨天 "
    if days <= 6:
        return f"{days}天前 "
    return f"{when:%m-%d} "  # 过一周再数「N天前」就没意义了，回月-日
