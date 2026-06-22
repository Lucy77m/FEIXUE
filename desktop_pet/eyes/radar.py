# 卡住雷达 判断用户是不是卡在某个窗口

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from desktop_pet import presence

# 标题命中这些词就当出事了
_ERR_TITLE = re.compile(
    r"error|exception|failed|fail\b|not responding|crash|warning|"
    r"错误|失败|无法|未响应|异常|崩溃|警告",
    re.IGNORECASE,
)
_STUCK_DWELL_S = 240.0  # 同一窗口黏够4分钟算卡住
_NORM = re.compile(r"\s+")


@dataclass(frozen=True)
class RadarSignal:
    """一次观测的结论"""
    title: str
    dwell_s: float
    title_hit: bool
    worth_peek: bool


class Radar:
    def __init__(self) -> None:
        self._title = ""
        self._since = 0.0

    def observe(self) -> RadarSignal:
        """观测一次并推进计时"""
        title = presence.foreground_window_title()
        now = time.monotonic()
        # 折空白转小写再比
        norm = _NORM.sub(" ", title).strip().lower()
        if norm != self._title:
            self._title = norm
            self._since = now
        dwell = now - self._since
        hit = bool(title) and bool(_ERR_TITLE.search(title))  # 空标题不算命中
        return RadarSignal(
            title=title, dwell_s=dwell, title_hit=hit,
            worth_peek=hit or dwell >= _STUCK_DWELL_S,
        )

    def reset(self) -> None:
        self._title = ""
        self._since = 0.0


radar = Radar()
