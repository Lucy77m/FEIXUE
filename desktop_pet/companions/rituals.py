# 仪式伴生 晨间预报纪念日蛋糕晚安告别番茄钟

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from desktop_pet import i18n, journal, somatic, stats
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.emotion.state import emotion
from desktop_pet.pet.behavior import selector

_FOCUS_MINUTES = 25


class Rituals(QObject):

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._focus_until = 0.0
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self._end_focus)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        try:
            self._focus_timer.stop()
        except Exception:
            pass

    def morning_ritual(self) -> None:
        """每天第一次见面 起床气加心情预报 纪念日端蛋糕"""
        today = datetime.now().date().isoformat()
        if stats.get_note("forecast") != today:
            stats.set_note("forecast", today)
            self._host._feed_react("yawn")
            val, _aro, _rapport = emotion.snapshot()
            rapport = emotion.unlocked_rapport()
            if val >= 0.25:
                key = "forecast_sunny"
            elif val >= -0.15:
                key = "forecast_cloudy"
            else:
                key = "forecast_rain"
            text = i18n.t(key)
            if rapport >= 0.6:
                text += i18n.t("forecast_close_suffix")
            QTimer.singleShot(1800, lambda: self._host._feed_pop(text))
        # 纪念日
        days = stats.snapshot()["days"]
        milestone = days in (7, 30, 100, 200, 520) or (days > 0 and days % 365 == 0)
        if milestone and stats.get_note("cake") != today:
            stats.set_note("cake", today)
            self._cake_on = True
            somatic.note(agent_prompts.SOMA_CAKE_OUT.format(days=days))
            QTimer.singleShot(4200, lambda: (
                self._host._pet.set_cake(True),
                self._host._feed_pop(i18n.t("cake_day").format(days=days)),
            ))
            QTimer.singleShot(10 * 60 * 1000, self._cake_timeout)
            # 里程碑纪念品
            try:
                from desktop_pet.world import get_world
                get_world().create_memento(
                    title=i18n.t("memento_day").format(days=days),
                    detail=i18n.t("memento_detail").format(days=days),
                )
            except Exception:
                pass

    def _cake_timeout(self) -> None:
        if getattr(self, "_cake_on", False):
            self._cake_on = False
            self._host._pet.set_cake(False)

    def on_pet_clicked_cake(self) -> None:
        """点宠物时蛋糕亮着就是吹蜡烛"""
        if not getattr(self, "_cake_on", False):
            return
        if self._host._pet.blow_cake():
            self._cake_on = False
            emotion.apply("praised")
            selector.set_emotion(*emotion.snapshot())
            somatic.note(agent_prompts.SOMA_CAKE_BLOWN)
            QTimer.singleShot(900, lambda: self._host._feed_react("celebrate"))
            QTimer.singleShot(1100, lambda: self._host._feed_pop(i18n.t("cake_blow")))
            QTimer.singleShot(2600, lambda: self._host._pet.set_cake(False))

    def farewell(self) -> bool:
        """退出前挥手告别 播了告别返回真 夜里道晚安白天说回头见"""
        if self._host._entered and self._host._pet.isVisible() and not getattr(self, "_farewell_done", False):
            # 走之前挥个手再真正退
            self._farewell_done = True
            self._host._feed_react("wave")
            line = ""
            try:
                today = datetime.now().date().isoformat()
                for it in reversed(journal.recent(6)):
                    if str(it.get("at", "")).startswith(today):  # journal 存的是 at 不是 ts 用错键带日记的告别永远不触发
                        line = str(it.get("text", ""))[:42]
                        break
            except Exception:
                pass
            hour = datetime.now().hour
            prefix = "bye" if (hour >= 21 or hour < 5) else "byeday"  # 深夜才晚安
            self._host._feed_pop(
                i18n.t(f"{prefix}_with_note").format(note=line) if line else i18n.t(f"{prefix}_plain"))
            QTimer.singleShot(1700, self._host._do_quit)
            return True
        return False

    def toggle_focus(self) -> None:
        """番茄钟 开一轮或提前结束"""
        if time.time() < self._focus_until:
            self._focus_timer.stop()
            self._focus_until = 0.0
            somatic.set_state("focus", None)
            self._host._feed_pop(i18n.t("focus_cancel"))
            return
        self._focus_until = time.time() + _FOCUS_MINUTES * 60
        self._focus_timer.start(_FOCUS_MINUTES * 60 * 1000)
        self._host._feed_perform("read")
        somatic.set_state("focus", agent_prompts.SOMA_FOCUS_STATE)
        self._host._feed_pop(i18n.t("focus_start").format(m=_FOCUS_MINUTES))

    def _end_focus(self) -> None:
        if self._focus_until <= 0:
            return
        self._focus_until = 0.0
        somatic.set_state("focus", None)
        somatic.note(agent_prompts.SOMA_FOCUS_DONE)
        self._host._feed_react("celebrate")
        emotion.apply("task_done")
        selector.set_emotion(*emotion.snapshot())
        self._host._feed_pop(i18n.t("focus_done").format(m=_FOCUS_MINUTES))
        # 每 5 次番茄钟创建一个专注纪念品
        try:
            count = int(stats.get_note("focus_count") or 0) + 1
        except (ValueError, TypeError):
            count = 1
        stats.set_note("focus_count", str(count))
        if count % 5 == 0:
            try:
                from desktop_pet.world import get_world
                get_world().create_memento(
                    title=i18n.t("memento_focus").format(n=count),
                    detail=i18n.t("memento_focus_detail").format(n=count),
                )
            except Exception:
                pass
