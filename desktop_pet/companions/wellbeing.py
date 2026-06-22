# 数字陪伴伴生 读前台窗口判专注还是漂着 心流时身体安静不打扰
# 前台窗口标题读取会在前台卡死时阻塞 采样一律走daemon线程 绝不在UI线程裸调

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import presence, somatic
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.companions.context_classifier import classify_window

_POLL_MS = 25_000
_FLOW_MINUTES = 12.0      # 专注类窗口连续停留这么久才算进入心流
_DRIFT_MINUTES = 35.0     # 媒体类窗口连续这么久算漂着
_ACTIVE_IDLE_S = 90.0     # 超过这空闲当人不在键盘前 不判心流
_OFF_GRACE = 2            # 离开专注类窗口几次轮询后才退心流 防短暂alt-tab抖动

def _classify(title: str) -> str:
    """前台窗口标题归成 work drift other 三类"""
    cat = classify_window(title)
    if cat in ("code", "terminal", "document"):
        return "work"
    if cat in ("media", "social"):
        return "drift"
    return "other"


class Wellbeing(QObject):
    """读前台窗口映射成身体状态 心流就安静 漂着就陪着 只读不落盘不外发"""

    _sampled = Signal(str, float)  # 前台标题和空闲秒数 线程采完发回主线程

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
        """app 主动门控查这个 专注时一切打扰都让路"""
        return self._flow

    def _tick(self) -> None:
        """UI线程只做轻量门控判断 可能阻塞的窗口读取丢线程"""
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
        threading.Thread(target=self._probe, daemon=True, name="feixue-wellbeing").start()

    def _probe(self) -> None:
        """daemon线程读前台窗口标题和空闲时长 会阻塞绝不能在UI线程做"""
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
        """回到UI线程 拿采样结果跑状态机"""
        now = time.monotonic()
        cat = _classify(title)
        if cat != self._cat:  # 换了类别停留计时重置
            self._cat = cat
            self._since = now
        dwell_min = (now - self._since) / 60.0
        active = idle < _ACTIVE_IDLE_S

        # 心流要同时满足 专注类窗口 停留够久 人在键盘前
        if cat == "work" and active and dwell_min >= _FLOW_MINUTES:
            self._off_streak = 0
            self._set_flow(True)
        elif self._flow:
            if cat == "work" and active:
                self._off_streak = 0
            else:  # 离开专注类给几次轮询缓冲 防短暂切窗抖动
                self._off_streak += 1
                if self._off_streak >= _OFF_GRACE:
                    self._set_flow(False)

        # 漂着是媒体类窗口耗很久且人在 只让身体蔫一下不弹话
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
