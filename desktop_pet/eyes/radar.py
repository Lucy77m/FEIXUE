# author: bdth
# email: 2074055628@qq.com
# 卡住雷达：判断用户是不是卡在某个窗口。

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from desktop_pet import presence

# 标题里出这些词就当现场出事了，中英都收。fail 加 \b 只认整词，免得 failure 一类正常词也命中。
_ERR_TITLE = re.compile(
    r"error|exception|failed|fail\b|not responding|crash|warning|"
    r"错误|失败|无法|未响应|异常|崩溃|警告",
    re.IGNORECASE,
)
_STUCK_DWELL_S = 240.0  # 同一窗口黏够 4 分钟就算卡住了 —— 短了会把正常阅读/看视频也误判。
_NORM = re.compile(r"\s+")


@dataclass(frozen=True)
class RadarSignal:
    """一次观测的结论：worth_peek 为真才值得唤起后面那套重活去看一眼。"""
    title: str
    dwell_s: float
    title_hit: bool
    worth_peek: bool


class Radar:
    def __init__(self) -> None:
        self._title = ""
        self._since = 0.0

    def observe(self) -> RadarSignal:
        """每调一次都顺手推进计时，所以靠外面定时喊它，别乱调。"""
        title = presence.foreground_window_title()
        now = time.monotonic()  # monotonic 不会被对时/跳秒拨乱，dwell 才靠谱。
        # 折空白+转小写再比，标题里时钟秒数/大小写抖一下不至于被当成换了窗口、把计时白白清零。
        norm = _NORM.sub(" ", title).strip().lower()
        if norm != self._title:
            self._title = norm
            self._since = now
        dwell = now - self._since
        hit = bool(title) and bool(_ERR_TITLE.search(title))  # 空标题别让正则瞎命中。
        return RadarSignal(
            title=title, dwell_s=dwell, title_hit=hit,
            worth_peek=hit or dwell >= _STUCK_DWELL_S,
        )

    def reset(self) -> None:
        self._title = ""
        self._since = 0.0


radar = Radar()
