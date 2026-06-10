# author: bdth
# email: 2074055628@qq.com
# 身体感受 交互事件和持续状态 喂给每轮上下文让它知道自己身上发生了什么

from __future__ import annotations

import time
from collections import deque

_events: deque = deque(maxlen=8)
_states: dict[str, str] = {}
_LOOK_BACK = 15 * 60


def note(text: str) -> None:
    """记一件刚发生在身上的事"""
    _events.append((time.time(), str(text)))


def set_state(key: str, text: str | None) -> None:
    """持续状态 传None清掉"""
    if text:
        _states[key] = str(text)
    else:
        _states.pop(key, None)


def context() -> str:
    """拼身体近况注记 没东西给空串"""
    now = time.time()
    lines = list(_states.values())
    for ts, text in _events:
        age = now - ts
        if age > _LOOK_BACK:
            continue
        mins = int(age // 60)
        when = "刚刚" if mins < 1 else f"{mins}分钟前"
        lines.append(f"{when} {text}")
    if not lines:
        return ""
    return ("[身体近况——你的身体(桌宠本体)刚经历的事和正处的状态 聊天时可自然提起 不必每次都提]\n"
            + "\n".join("- " + ln for ln in lines))


def clear() -> None:
    _events.clear()
    _states.clear()
