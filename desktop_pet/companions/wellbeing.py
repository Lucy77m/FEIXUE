# author: bdth
# email: 2074055628@qq.com
# 数字陪伴伴生 读前台窗口判专注/漂着 心流时身体安静且不打扰 —— 它替你感受你这一天的质地
# 注意：前台窗口标题读取(GetWindowText)在前台窗口卡死时会阻塞，所以采样一律走 daemon 线程，绝不在 UI 线程裸调

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import presence, somatic
from desktop_pet.agent import prompts as agent_prompts

_POLL_MS = 25_000
_FLOW_MINUTES = 12.0      # 专注类窗口连续停留这么久才算进入心流
_DRIFT_MINUTES = 35.0     # 媒体类窗口连续这么久算漂着
_ACTIVE_IDLE_S = 90.0     # 超过这空闲当人不在键盘前 不判心流
_OFF_GRACE = 2            # 离开专注类窗口几次轮询后才退心流 防短暂alt-tab抖动

# 标题关键词分类（小写子串匹配，宁可漏判不要误判）
_WORK_CUES = (
    "visual studio", "vs code", "vscode", " - code", "pycharm", "intellij", " idea",
    "sublime text", "neovim", " - cursor", "windsurf", "rider", "goland", "clion", "webstorm",
    "obsidian", "powershell", "windows terminal", "cmd.exe", "wsl", "- vim",
    "- word", "- excel", "- powerpoint", "overleaf", "jupyter",
)
_DRIFT_CUES = (
    "youtube", "bilibili", "哔哩哔哩", "netflix", "twitch", "tiktok", "抖音", "douyin",
    "reddit", "instagram", "facebook", "微博", " - vlc", "爱奇艺", "腾讯视频", "优酷",
)


def _classify(title: str) -> str:
    """前台窗口标题归类 work/drift/other"""
    t = title.lower()
    if not t:
        return "other"
    if any(c in t for c in _WORK_CUES):
        return "work"
    if any(c in t for c in _DRIFT_CUES):
        return "drift"
    return "other"


class Wellbeing(QObject):
    """读前台窗口的质地 → 身体状态。心流=安静不打扰，漂着=陪着但不说教。只读、不落盘、不外发。"""

    _sampled = Signal(str, float)  # (前台标题, 空闲秒数) —— 线程采完发回主线程

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._busy = False
        self._sampled.connect(self._on_sampled)
        self._cat = ""
        self._since = 0.0       # 当前类别起始时刻
        self._flow = False
        self._drift = False
        self._off_streak = 0

    def start(self) -> None:
        self._timer.start(_POLL_MS)

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self._set_flow(False)
        self._set_drift(False)

    def in_flow(self) -> bool:
        """app 主动门控查这个：专注时一切打扰都让路"""
        return self._flow

    def _tick(self) -> None:
        """UI 线程：只做轻量门控判断，可能阻塞的窗口读取丢线程"""
        if self._busy:
            return
        pet = self._host._pet
        if not pet.isVisible() or pet.is_asleep or self._host._meeting_mode:
            # 不在场景里 收起所有状态
            self._set_flow(False)
            self._set_drift(False)
            self._cat = ""
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True, name="mochi-wellbeing").start()

    def _probe(self) -> None:
        """daemon 线程：读前台窗口标题（前台卡死时 GetWindowText 会阻塞，绝不能在 UI 线程做）+ 空闲时长"""
        try:
            title = presence.foreground_window_title()
            idle = presence.idle_seconds()
            self._sampled.emit(title, idle)
        except Exception:
            pass
        finally:
            self._busy = False

    @Slot(str, float)
    def _on_sampled(self, title: str, idle: float) -> None:
        """UI 线程：拿到采样结果跑状态机"""
        now = time.monotonic()
        cat = _classify(title)
        if cat != self._cat:  # 换了类别 停留计时重置（这就是迟滞）
            self._cat = cat
            self._since = now
        dwell_min = (now - self._since) / 60.0
        active = idle < _ACTIVE_IDLE_S

        # 心流：专注类窗口 + 停留够久 + 人在键盘前
        if cat == "work" and active and dwell_min >= _FLOW_MINUTES:
            self._off_streak = 0
            self._set_flow(True)
        elif self._flow:
            if cat == "work" and active:
                self._off_streak = 0
            else:  # 离开专注类 给几次轮询缓冲 防短暂切窗抖动
                self._off_streak += 1
                if self._off_streak >= _OFF_GRACE:
                    self._set_flow(False)

        # 漂着：媒体类窗口 + 长时间 + 人在；只让身体蔫一下，不弹任何话（克制）
        self._set_drift(cat == "drift" and active and dwell_min >= _DRIFT_MINUTES)

    def _set_flow(self, on: bool) -> None:
        if on == self._flow:
            return
        self._flow = on
        somatic.set_state("flow", agent_prompts.SOMA_FLOW_STATE if on else None)

    def _set_drift(self, on: bool) -> None:
        if on == self._drift:
            return
        self._drift = on
        somatic.set_state("drift", agent_prompts.SOMA_DRIFT_STATE if on else None)
