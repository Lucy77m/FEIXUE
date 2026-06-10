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
    from desktop_pet.agent import prompts
    now = time.time()
    lines = list(_states.values())
    for ts, text in _events:
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
    _events.clear()
    _states.clear()
