# 记忆天气伴生 把情绪/环境/状态信号合成天气种类 驱动粒子层

from __future__ import annotations

import random
import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Slot

from desktop_pet import i18n, somatic
from desktop_pet.emotion.state import emotion
from desktop_pet.pet.weather_overlay import WeatherOverlay

_POLL_MS = 45_000   # 天气变化慢 45 秒看一次够了
_POP_COOLDOWN = 300  # 气泡 5 分钟冷却

# 天气变化时触发的行为  None 表示不触发
_WEATHER_BEHAVIORS: dict[str, tuple[str, str] | None] = {
    "rain":    ("react", "sigh"),       # 叹气
    "fog":     ("react", "ponder"),     # 发呆
    "stars":   ("perform", "stars"),    # 望远镜观星
    "warm":    ("react", "happy_wiggle"),
    "static":  ("react", "wobble"),     # 不安
    "gentle":  None,
    "clear":   None,
}


class MemoryWeather(QObject):
    """读已有信号合成天气 操作 WeatherOverlay 画粒子"""

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._overlay = WeatherOverlay()
        self._current = "clear"
        self._last_pop_at = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        # 跟踪宠物位置
        host._pet.moved.connect(self._on_pet_moved)

    def start(self) -> None:
        self._timer.start(_POLL_MS)
        self._tick()                # 首次立即算一次

    def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self._overlay.hide_layer()

    def current_weather(self) -> str:
        """当前天气种类 供外部读取"""
        return self._current

    # ── 内部 ──────────────────────────────────────────────

    @Slot()
    def _on_pet_moved(self) -> None:
        pet = self._host._pet
        if pet.isVisible():
            self._overlay.track_pet(pet.frameGeometry().center())

    def _tick(self) -> None:
        kind = self._compute_weather()
        if kind == self._current and self._overlay.isVisible():
            return
        self._apply(kind)

    def _compute_weather(self) -> str:
        valence, arousal, rapport = emotion.snapshot()
        anim = emotion.animation_state()

        now = datetime.now()
        is_late = (now.hour == 23 and now.minute >= 30) or 0 <= now.hour < 5

        # 优先级匹配 先命中先返回
        # 1. 深夜 + 有感情基础 → 星空
        if is_late and rapport >= 0.45:
            return "stars"

        # 2. 系统压力 → 静电
        if somatic.has_state("meeting") or (somatic.has_state("hot") and arousal >= 0.5):
            return "static"

        # 3. 专注流 → 安静陪伴
        try:
            if self._host._wellbeing.in_flow():
                return "gentle"
        except Exception:
            pass
        if somatic.has_state("flow"):
            return "gentle"

        # 3b. 长时间项目 + 正面情绪 → 安静陪伴
        tracker = getattr(self._host, '_project_tracker', None)
        if tracker is not None:
            try:
                project = tracker.current_project()
                session_min = tracker.current_session_minutes()
                if project and session_min >= 30 and valence >= 0.1:
                    return "gentle"
            except Exception:
                pass

        # 4. 正面高唤醒 → 暖意
        if valence >= 0.3 and arousal >= 0.4:
            return "warm"

        # 5. 低落 → 雨
        if anim == "down" or valence <= -0.2:
            return "rain"

        # 6. 焦虑/低迷 → 雾
        if anim == "anxious" or (valence < 0.0 and arousal < 0.3):
            return "fog"

        # 7. 默认
        return "clear"

    def _apply(self, kind: str) -> None:
        old = self._current
        self._current = kind
        pet = self._host._pet
        if kind == "clear" or not pet.isVisible():
            self._overlay.hide_layer()
        else:
            center = pet.frameGeometry().center()
            self._overlay.set_weather(kind, center)
        # 写入 somatic 供 LLM 上下文
        somatic.set_state("mweather", f"memory weather: {kind}")
        # 同步到宠物身体
        try:
            self._host._pet.set_mood_weather(kind if kind != "clear" else "")
        except Exception:
            pass
        # 天气种类真正变了才触发行为和气泡
        if kind != old:
            self._trigger_behavior(kind)
            self._maybe_pop(kind)

    def _trigger_behavior(self, kind: str) -> None:
        """天气变化时触发一次对应行为"""
        action = _WEATHER_BEHAVIORS.get(kind)
        if action is None:
            return
        mode, name = action
        try:
            if mode == "react":
                QTimer.singleShot(2500, lambda: self._host._feed_react(name))
            elif mode == "perform":
                QTimer.singleShot(3000, lambda: self._host._feed_perform(name))
        except Exception:
            pass

    def _maybe_pop(self, kind: str) -> None:
        """天气变化时偶尔弹一句气泡 低打扰"""
        now = time.monotonic()
        if now - self._last_pop_at < _POP_COOLDOWN:
            return
        if random.random() > 0.4:
            return
        self._last_pop_at = now
        try:
            text = i18n.t(f"mweather_{kind}")
            self._host._feed_pop(text)
        except Exception:
            pass
