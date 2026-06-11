# author: bdth
# email: 2074055628@qq.com
# 守望伴生 后台shell播报和剪贴宝贝回赠

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from desktop_pet import i18n, presence
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.emotion.state import emotion
from desktop_pet.executor import shell as shell_exec
from desktop_pet.pet.behavior import selector

_AWAY_S = 150.0
_BGWATCH_POLL_MS = 5_000
_BGWATCH_MIN_RUNTIME_S = 10.0  # 秒退的任务agent当场看到 不播报
_GIVEBACK_MIN_INTERVAL_S = 4 * 3600
_GIVEBACK_MIN_AGE_H = 2.0  # 收藏攒够这么久才值得拿出来
_GIVEBACK_RAPPORT_GATE = 0.45


class Watchers(QObject):

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._bgwatch_timer = QTimer(self)
        self._bgwatch_timer.timeout.connect(self._scan_background_shells)
        self._bg_announced: set[int] = set()
        self._clip_treasures: deque = deque(maxlen=12)  # 帮用户收着的剪贴小宝贝 只在内存
        self._last_giveback: datetime | None = None

    def start(self) -> None:
        self._bgwatch_timer.start(_BGWATCH_POLL_MS)

    def stop(self) -> None:
        try:
            self._bgwatch_timer.stop()
        except Exception:
            pass

    def add_treasure(self, kind: str, text: str) -> None:
        """顺手收藏一份留着回赠 只进内存不落盘"""
        if all(text != t for _k, t, _ts in self._clip_treasures):
            self._clip_treasures.append((kind, text, datetime.now()))

    def _scan_background_shells(self) -> None:
        """守望后台shell 跑完庆祝 挂了安慰并叫agent看"""
        try:
            snap = shell_exec.background_snapshot()
        except Exception:
            return
        for t in snap:
            if t["running"] or t["id"] in self._bg_announced:
                continue
            self._bg_announced.add(t["id"])
            if time.time() - t["started"] < _BGWATCH_MIN_RUNTIME_S:
                continue
            if t["returncode"] == 0:
                self._host._feed_react("celebrate")
                self._host._feed_pop(i18n.t("bgwatch_ok").format(id=t["id"]))
                emotion.apply("task_done")
                selector.set_emotion(*emotion.snapshot())
            else:
                self._host._feed_react("droop")
                self._host._feed_pop(i18n.t("bgwatch_fail").format(id=t["id"], code=t["returncode"]))
                if not self._host._worker.is_running:
                    self._host.request_message.emit(agent_prompts.BGWATCH_ANALYZE_MSG.format(
                        id=t["id"], command=t["command"][:80], code=t["returncode"],
                        tail=t["tail"][-1200:]))

    def maybe_giveback(self) -> bool:
        """亲密度够了 把几小时前帮用户收着的剪贴宝贝拿出来提一嘴"""
        if not self._host._settings.proactive_enabled or not self._clip_treasures:
            return False
        if self._host._worker.is_running or self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep:
            return False
        if presence.idle_seconds() >= _AWAY_S:
            return False
        _val, _aro, rapport = emotion.snapshot()
        if rapport < _GIVEBACK_RAPPORT_GATE:
            return False
        now = datetime.now()
        if self._last_giveback is not None and (now - self._last_giveback).total_seconds() < _GIVEBACK_MIN_INTERVAL_S:
            return False
        kind, text, ts = self._clip_treasures[0]
        age_h = (now - ts).total_seconds() / 3600
        if age_h < _GIVEBACK_MIN_AGE_H:
            return False
        self._clip_treasures.popleft()
        self._last_giveback = now
        snippet = text.strip().replace("\n", " ")[:60]
        self._host._feed_react("peek")
        self._host.request_message.emit(agent_prompts.GIVEBACK_MSG.format(
            hours=f"{age_h:.0f}", kind=kind, snippet=snippet))
        return True
