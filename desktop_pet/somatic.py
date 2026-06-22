# 身体感受 交互事件和持续状态 喂给每轮上下文让它知道自己身上发生了什么

from __future__ import annotations

import threading
import time
from collections import deque

_events: deque = deque(maxlen=8)
_states: dict[str, str] = {}
_LOOK_BACK = 15 * 60
# 主线程在写 worker 线程每轮 context 在读
# 不加锁 worker 迭代时撞上写会 changed size during iteration 整轮对话失败
_lock = threading.Lock()


def note(text: str) -> None:
    """记一件刚发生在身上的事"""
    with _lock:
        _events.append((time.time(), str(text)))


def set_state(key: str, text: str | None) -> None:
    """持续状态 传None清掉"""
    with _lock:
        if text:
            _states[key] = str(text)
        else:
            _states.pop(key, None)


def context() -> str:
    """拼身体近况注记 没东西给空串"""
    from desktop_pet.agent import prompts
    now = time.time()
    with _lock:  # 锁内只拍快照 拼字符串放锁外 别占着锁干慢活
        states = list(_states.values())
        events = list(_events)
    lines = states
    for ts, text in events:
        age = now - ts
        if age > _LOOK_BACK:
            continue
        mins = int(age // 60)
        when = prompts.SOMA_JUST_NOW if mins < 1 else prompts.SOMA_MIN_AGO.format(m=mins)
        lines.append(f"({when}) {text}")
    if not lines:
        return ""
    return prompts.SOMATIC_HEADER + "\n" + "\n".join("- " + ln for ln in lines)


def clear() -> None:
    with _lock:
        _events.clear()
        _states.clear()
