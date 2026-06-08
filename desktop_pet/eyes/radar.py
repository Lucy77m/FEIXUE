# author: bdth
# email: 2074055628@qq.com
# 卡住雷达：证据驱动地判断用户是不是卡在某个窗口（标题报错 / 长时间盯同一窗口没进展），
# 取代「随机偷看」。只做 UI 线程的轻量探测(observe)；真正的 OCR 取证+诊断在 worker 线程（peek_screen）做。

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from desktop_pet import presence

_ERR_TITLE = re.compile(
    r"error|exception|failed|fail\b|not responding|crash|warning|"
    r"错误|失败|无法|未响应|异常|崩溃|警告",
    re.IGNORECASE,
)
_STUCK_DWELL_S = 240.0
_NORM = re.compile(r"\s+")


@dataclass(frozen=True)
class RadarSignal:
    title: str
    dwell_s: float
    title_hit: bool
    worth_peek: bool


class Radar:
    def __init__(self) -> None:
        self._title = ""
        self._since = 0.0

    def observe(self) -> RadarSignal:
        """UI 线程每个 presence tick 调一次：更新久驻计时并给出当前信号。"""
        title = presence.foreground_window_title()
        now = time.monotonic()
        norm = _NORM.sub(" ", title).strip().lower()
        if norm != self._title:
            self._title = norm
            self._since = now
        dwell = now - self._since
        hit = bool(title) and bool(_ERR_TITLE.search(title))
        return RadarSignal(
            title=title, dwell_s=dwell, title_hit=hit,
            worth_peek=hit or dwell >= _STUCK_DWELL_S,
        )

    def reset(self) -> None:
        self._title = ""
        self._since = 0.0


radar = Radar()
