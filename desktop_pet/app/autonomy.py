# author: bdth
# email: 2074055628@qq.com
# 自主行为mixin 在场感知 提醒 远程信箱 主动搭话 看屏幕

from __future__ import annotations

import random
import threading
from datetime import datetime


from desktop_pet import i18n, occasions, presence
from desktop_pet.emotion.state import emotion
from desktop_pet.eyes.radar import radar
from desktop_pet.proactive import proactive
from desktop_pet.reminders import reminders


_AWAY_S = 150.0
_AWAY_NIGHT_S = 75.0
_PROACTIVE_RAPPORT_GATE = {"安静": 0.45, "正常": 0.30, "话痨": 0.15}
_PROACTIVE_RAPPORT_GATE_DEFAULT = 0.30
_EXPLORE_CHANCE = 0.3
_PEEK_MIN_INTERVAL_S = 600.0


class AutonomyMixin:
    """不靠用户输入也会动起来的那部分"""

    def _on_presence(self) -> None:
        try:
            self._drain_pending_bg()
            radar.observe()
            self._poll_presence()
        except Exception:
            pass

    def _poll_presence(self) -> None:
        if self._engaged() or not self._pet.isVisible():   # 忙时不准睡
            return
        away = _AWAY_NIGHT_S if self._is_night() else _AWAY_S
        if presence.idle_seconds() >= away:
            if not self._pet.is_asleep:
                self._pet.fall_asleep()
        elif self._pet.is_asleep and not self._pet.is_catnapping:
            self._wake()
            self._just_returned = True

    def _check_reminders(self) -> None:
        try:
            self._drain_reminders()
        except Exception:
            pass

    @staticmethod
    def _foreground_is_fullscreen() -> bool:
        try:
            import win32api
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            cls = win32gui.GetClassName(hwnd)
            if cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Button"):
                return False   # 桌面任务栏不算全屏应用
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            sw = win32api.GetSystemMetrics(0)
            sh = win32api.GetSystemMetrics(1)
            return (right - left) >= sw - 2 and (bottom - top) >= sh - 2   # 留2px容差
        except Exception:
            return False

    def _in_scene(self) -> bool:
        return (self._shown and self._pet.isVisible()
                and not self._pet.is_asleep and not self._foreground_is_fullscreen())

    def _drain_reminders(self) -> None:
        # 不在场时只取提醒 do类任务压着等在场再领
        in_scene = self._in_scene()
        due = reminders.due(datetime.now(), take_do=in_scene)
        if not due:
            return
        says = [r.what for r in due if r.kind != "do"]
        tasks = [r.what for r in due if r.kind == "do"]
        if says:
            text = "；".join(says)
            if not self._shown or not self._pet.isVisible() or self._foreground_is_fullscreen():
                self._tray.notify(i18n.t("tray_tooltip"), text)
            else:
                self._pet.wake()
                self.request_reminder.emit(text)
        if tasks:
            self._timed_queue.extend(tasks)
            self._drain_timed()

    def _drain_timed(self) -> None:
        if self._timed_inflight or not self._timed_queue:
            return
        if self._engaged() or self._cancelling or not self._in_scene():
            return
        task = self._timed_queue.pop(0)
        self._timed_inflight = True
        self._inflight_timed = task
        self._pet.wake()
        self.request_timed_task.emit(task)

    def _requeue_timed(self) -> None:
        """没跑完的定时任务塞回reminders"""
        now = datetime.now()
        pending = list(self._timed_queue)
        if self._inflight_timed:   # 正在跑的排最前
            pending.insert(0, self._inflight_timed)
        for task in pending:
            try:
                reminders.add(now, task, kind="do")
            except Exception:
                pass
        self._timed_queue.clear()
        self._inflight_timed = None
        self._timed_inflight = False

    def _check_proactive(self) -> None:
        try:
            if self._meeting_mode:
                return  # 开会不主动出声
            if self._wellbeing.in_flow():
                return  # 你在心流里 一切打扰都让路
            if self._maybe_peek():
                return
            if self._maybe_occasion():
                return
            if self._playtime.maybe_hide_seek():
                return
            if self._playtime.maybe_perch():
                return
            if self._watchers.maybe_giveback():
                return
            self._maybe_speak_up()
        except Exception:
            pass

    def _on_wants_travel(self) -> None:
        """虫洞穿越前的全局闸门"""
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep:
            return
        self._pet.start_wormhole()

    def _maybe_peek(self) -> bool:
        s = self._settings
        if not s.watch_screen or not s.allow_control:
            return False
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep:
            return False
        if presence.idle_seconds() >= 60:
            return False
        _val, _aro, rapport = emotion.snapshot()
        if rapport < 0.35:
            return False
        now = datetime.now()
        if self._last_peek is not None and (now - self._last_peek).total_seconds() < _PEEK_MIN_INTERVAL_S:
            return False
        sig = radar.observe()
        if not sig.worth_peek:
            return False
        self._last_peek = now
        self.request_peek.emit(sig.title)
        return True

    def _check_watch(self) -> None:
        try:
            self._maybe_watch()
        except Exception:
            pass

    def _maybe_watch(self) -> None:
        from desktop_pet.watcher import watcher
        if not self._settings.allow_control:
            return
        if not self._shown or not self._pet.isVisible() or self._pet.is_asleep:
            return
        if self._watch_inflight or self._engaged():
            return
        focus = watcher.due(datetime.now())
        if not focus:
            return
        self._watch_inflight = True
        self._pet.wake()
        self.request_analyze.emit(focus)

    def _on_analysis(self, text: str) -> None:
        self._watch_inflight = False
        from desktop_pet.watcher import watcher, WATCH_FAIL
        if text == WATCH_FAIL:
            watcher.retry_soon()
            return
        if not text or not text.strip():
            return
        if (not watcher.enabled or not self._shown or not self._pet.isVisible()
                or self._pet.is_asleep or self._foreground_busy()):
            return
        self._on_reply(text)

    def _maybe_occasion(self) -> bool:
        if not self._settings.proactive_enabled:
            return False
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep:
            return False
        if presence.idle_seconds() >= _AWAY_S:
            return False
        key = occasions.today_key(datetime.now())
        if not key or key in self._fired_occasions:
            return False
        self._fired_occasions.add(key)
        ctx = (f"（{occasions.describe(key)}，用你自己的口吻、温暖自然地道一句应景的话，"
               "别太正式、也别照念。）")
        self._pet.perform("cheer")
        self.request_proactive.emit("share_day", ctx)
        return True

    def _maybe_speak_up(self) -> None:
        s = self._settings
        if not s.proactive_enabled:
            return
        if (self._worker.is_running or self._busy or self._lecturing
                or self._speech.is_speaking or self._input.isVisible()
                or not self._pet.isVisible() or self._pet.is_asleep):
            return
        if presence.idle_seconds() >= _AWAY_S:
            return
        level = s.proactive_level
        _val, _aro, rapport = emotion.snapshot()
        gate = _PROACTIVE_RAPPORT_GATE.get(level, _PROACTIVE_RAPPORT_GATE_DEFAULT)
        if rapport < gate:
            return
        now = datetime.now()
        context = self._proactive_context()
        if self._just_returned and proactive.welcome_ready(now, level):
            self._just_returned = False
            proactive.record(now, level)
            dream = self._dreams.take_dream_hint()  # 睡着时做了梦就迷糊提一句
            self.request_proactive.emit("welcome_back", (context + "\n" + dream) if dream else context)
            return
        self._just_returned = False
        if not proactive.ready(now, level):
            return
        proactive.record(now, level)
        if self._settings.allow_web and random.random() < _EXPLORE_CHANCE:
            self.request_explore.emit(self._pick_explore_topic())
        else:
            self.request_proactive.emit(self._pick_proactive_mode(now), context)

    @staticmethod
    def _pick_explore_topic() -> str:
        return random.choice((
            "今天的天气", "最近的新鲜事 / 热搜", "一条有意思的冷知识",
            "今天值得看的科技新闻", "一个冷门但有用的小技巧",
        ))

    @staticmethod
    def _proactive_context() -> str:
        title = presence.foreground_window_title()
        if not title or len(title) > 120:
            return ""
        return f"（此刻 ta 正在用的窗口是：「{title}」——可作为你搭话的由头，但别照念窗口标题。）"

    @staticmethod
    def _pick_proactive_mode(now: datetime) -> str:
        if (now.hour >= 23 or now.hour < 5) and random.random() < 0.7:
            return "late_care"
        return random.choice(("check_in", "follow_up", "share_day", "thought"))

    @staticmethod
    def _is_night() -> bool:
        hour = datetime.now().hour
        return hour >= 23 or hour < 6
