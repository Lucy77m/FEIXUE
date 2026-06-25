# 玩耍伴生 抓虫投球蹲守脚印物理反馈渔获

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, QPoint, QTimer, Signal, Slot

from desktop_pet import i18n, journal, occasions, presence, somatic, stats
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.companions.context_classifier import classify_window
from desktop_pet.emotion.state import emotion
from desktop_pet.pet import feeding
from desktop_pet.pet.behavior import selector

_AWAY_S = 150.0
_BUG_SCAN_MS = 45 * 60 * 1000
_BUG_TEMP_BYTES = 500 * 1024 * 1024  # temp堆到这么大就生虫
_CONTEXT_STABLE_S = 12.0
_CONTEXT_COOLDOWN_S = 600.0
_PERCH_MIN_S = 45.0
_PERCH_MAX_S = 120.0
_PERCH_POP_CHANCE = 0.20


class Playtime(QObject):
    _bug_found = Signal(int)
    _bug_cleaned = Signal(int, int)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._bug_timer = QTimer(self)
        self._bug_timer.timeout.connect(self._check_bugs)
        self._bug = None
        self._bug_scanning = False
        self._bug_found.connect(self._on_bug_found)
        self._bug_cleaned.connect(self._on_bug_cleaned)
        from desktop_pet.pet.footprints import FootprintLayer
        self._paws = FootprintLayer()
        self._paw_last = QPoint()
        self._host._pet.moved.connect(self._on_pet_moved_paws)
        self._ball = None  # 玩具球
        self._host._pet.bind_activity_done(self._on_activity_done)
        self._perch_hwnd = 0
        self._perch_timer = QTimer(self)
        self._perch_timer.timeout.connect(self._check_perch)
        self._perch_last = 0.0
        self._perch_started = 0.0
        self._perch_until = 0.0
        self._perch_kind = ""
        self._perch_offset = QPoint()
        self._context_candidate = 0
        self._context_since = 0.0
        self._context_timer = QTimer(self)
        self._context_timer.timeout.connect(self._observe_context)
        self._host._pet.grabbed.connect(self._perch_done)
        self._host._pet.tossed.connect(self._on_tossed)
        self._host._pet.tickled.connect(self._on_tickled)

    def start(self) -> None:
        self._bug_timer.start(_BUG_SCAN_MS)
        self._context_timer.start(3000)

    def stop(self) -> None:
        """退出前停轮询关掉所有玩耍小窗"""
        for t in (self._bug_timer, self._perch_timer, self._context_timer):
            try:
                t.stop()
            except Exception:
                logger.debug("playtime: timer stop failed", exc_info=True)
        for w in (self._bug, self._ball):
            if w is not None:
                try:
                    w._timer.stop()
                    w.close()
                except Exception:
                    logger.debug("playtime: window close failed", exc_info=True)
        self._bug = self._ball = None
        try:
            self._paws._timer.stop()
            self._paws.hide()
        except Exception:
            logger.debug("playtime: paws stop failed", exc_info=True)

    def apply_settings(self) -> None:
        if not getattr(self._host._settings, "context_perch_enabled", True):
            self._perch_done()

    @Slot(float)
    def _on_tossed(self, impact: float) -> None:
        """被重摔了 疼一下还要哄"""
        emotion.apply("hurt")
        selector.set_emotion(*emotion.snapshot())
        self._host._pet.set_expression("sad")
        somatic.note(agent_prompts.SOMA_TOSSED)
        somatic.set_state("grudge", agent_prompts.SOMA_GRUDGE)
        QTimer.singleShot(30 * 60 * 1000, lambda: somatic.set_state("grudge", None))
        self._host._feed_pop(i18n.t("toss_ouch"))

    @Slot()
    def _on_tickled(self) -> None:
        """被挠痒 开心计入互动"""
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        stats.bump_interactions()
        somatic.note(agent_prompts.SOMA_TICKLED)

    def _on_pet_moved_paws(self) -> None:
        """走动时心情好就留脚印 节日换花样"""
        try:
            _val, _aro, _r = emotion.snapshot()
            if _val < 0.25:
                return
            pos = self._host._pet.frameGeometry().center()
            d = pos - self._paw_last
            if (d.x() * d.x() + d.y() * d.y()) < 70 * 70:
                return
            import math as _m
            heading = _m.atan2(d.y(), d.x()) if self._paw_last != QPoint() else 0.0
            self._paw_last = QPoint(pos)
            kind = "paw"
            okey = occasions.today_key(datetime.now()) or ""
            if "spring" in okey or "newyear" in okey:
                kind = "flower"
            elif "christmas" in okey or "winter" in okey:
                kind = "snow"
            self._paws.add(pos.x(), pos.y() + self._host._pet.height() // 4, heading, kind)
        except Exception:
            logger.debug("playtime: paw print failed", exc_info=True)

    def _on_activity_done(self, name: str) -> None:
        """小品演完的彩蛋 钓鱼有渔获"""
        if name != "fish":
            return
        fishing = getattr(self._host, "_fishing", None)
        if fishing is not None and fishing.consume_activity(name):
            return
        catch = ""
        try:
            treasures = self._host._watchers._clip_treasures
            if treasures and random.random() < 0.5:
                _k, text, _ts = random.choice(list(treasures))
                catch = text.strip().replace("\n", " ")[:46]
            else:
                today_lines = [str(it.get("text", "")) for it in journal.recent(6)]
                if today_lines:
                    catch = random.choice(today_lines)[:46]
        except Exception:
            logger.debug("playtime: fishing catch pickup failed", exc_info=True)
        if catch:
            QTimer.singleShot(1200, lambda: self._host._feed_pop(i18n.t("fish_catch").format(thing=catch)))

    def throw_ball(self) -> None:
        """丢颗球给它玩"""
        if self._ball is not None or not self._host._pet.isVisible() or self._host._pet.is_asleep:
            return
        from desktop_pet.pet.ball import BallWindow
        from desktop_pet.eyes import capture
        ball = BallWindow()
        capture.register_own_window(int(ball.winId()))
        ball.caught.connect(self._on_ball_caught)
        ball.stopped.connect(self._on_ball_stopped)
        scr = self._host._app.primaryScreen().availableGeometry()
        ball.throw_from_top(scr, self._host._pet.frameGeometry())
        self._ball = ball
        self._host._feed_react("perk_up")

    @Slot()
    def _on_ball_caught(self) -> None:
        self._ball = None
        self._host._feed_react("jump_spin")
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        somatic.note(agent_prompts.SOMA_BALL)
        QTimer.singleShot(900, lambda: self._host._feed_pop(i18n.t("ball_caught")))

    @Slot()
    def _on_ball_stopped(self) -> None:
        self._ball = None
        self._host._feed_react("peek")

    def maybe_perch(self) -> bool:
        """Compatibility entry used by the slower autonomy poll."""
        return self._observe_context()

    @staticmethod
    def classify_context(process: str, title: str) -> str:
        return classify_window(title, process)

    def _foreground_snapshot(self):
        try:
            import psutil
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or hwnd == int(self._host._pet.winId()) or not win32gui.IsWindowVisible(hwnd):
                return None
            title = win32gui.GetWindowText(hwnd).strip()
            cls = win32gui.GetClassName(hwnd)
            if cls in {"Progman", "WorkerW", "Shell_TrayWnd", "Button"} or not title:
                return None
            _thread, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid).name()
            except Exception:
                logger.debug("playtime: process name lookup failed", exc_info=True)
                process = ""
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right - left < 420 or bottom - top < 260:
                return None
            kind = self.classify_context(process, title)
            return hwnd, (left, top, right, bottom), kind, title
        except Exception:
            return None

    def _observe_context(self) -> bool:
        if (not getattr(self._host._settings, "context_perch_enabled", True)
                or self._host._meeting_mode or self._perch_hwnd):
            return False
        if self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep:
            return False
        snapshot = self._foreground_snapshot()
        if snapshot is None:
            self._context_candidate = 0
            return False
        hwnd, rect, kind, _title = snapshot
        now = time.time()
        if hwnd != self._context_candidate:
            self._context_candidate = hwnd
            self._context_since = now
            return False
        if now - self._context_since < _CONTEXT_STABLE_S or now - self._perch_last < _CONTEXT_COOLDOWN_S:
            return False
        return self._start_context_perch(hwnd, rect, kind)

    def _start_context_perch(self, hwnd: int, rect: tuple[int, int, int, int], kind: str) -> bool:
        left, top, right, _bottom = rect
        if not self._host._pet.start_window_perch(rect, kind):
            return False
        self._perch_last = time.time()
        self._perch_started = self._perch_last
        self._perch_until = self._perch_started + random.uniform(_PERCH_MIN_S, _PERCH_MAX_S)
        self._perch_hwnd = hwnd
        self._perch_kind = kind
        self._perch_rect = rect
        pos = self._host._pet.frameGeometry().topLeft()
        self._perch_offset = QPoint(pos.x() - left, pos.y() - top)
        if random.random() < _PERCH_POP_CHANCE:
            self._host._feed_pop(i18n.t(f"context_perch_{kind}"))
        if random.random() < 0.25:
            self._host._pet.leave_life_trace("dot", 1)
        self._perch_timer.start(700)
        return True

    def _check_perch(self) -> None:
        """蹲守期间窗口动了就摔下来"""
        if not self._perch_hwnd:
            self._perch_timer.stop()
            return
        if self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep:
            self._perch_done("busy")
            return
        if time.time() >= self._perch_until:
            self._perch_done("settled")
            return
        try:
            import win32gui
            if not win32gui.IsWindowVisible(self._perch_hwnd) or win32gui.IsIconic(self._perch_hwnd):
                self._perch_done("hidden")
                return
            if win32gui.GetForegroundWindow() != self._perch_hwnd:
                self._perch_done("lost")
                return
            left, top, right, bottom = win32gui.GetWindowRect(self._perch_hwnd)
            old_left, old_top, _old_right, _old_bottom = self._perch_rect
            if left != old_left or top != old_top:
                self._host._pet.move(QPoint(left, top) + self._perch_offset)
                self._host._pet.moved.emit()
            # 窗口最大化时宠物被"弹"下去
            new_rect = win32gui.GetWindowRect(self._perch_hwnd)
            new_w = new_rect[2] - new_rect[0]
            old_w = self._perch_rect[2] - self._perch_rect[0]
            if new_w > old_w + 200:
                self._perch_fall()
                return
            self._perch_rect = (left, top, right, bottom)
        except Exception:
            self._perch_done("lost")

    def _perch_fall(self) -> None:
        """窗台塌了 摔下去气鼓鼓"""
        self._perch_hwnd = 0
        self._perch_timer.stop()
        self._perch_started = 0.0
        self._perch_until = 0.0
        self._host._pet._start_toss(random.uniform(-120, 120), 60.0)
        QTimer.singleShot(1400, lambda: self._host._feed_react("puff_up"))
        QTimer.singleShot(1700, lambda: self._host._feed_pop(i18n.t("perch_fall")))

    def _perch_done(self, reason: str = "settled") -> None:
        if not self._perch_hwnd:
            return
        duration = max(0.0, time.time() - self._perch_started) if self._perch_started else 0.0
        self._perch_hwnd = 0
        self._perch_kind = ""
        self._perch_started = 0.0
        self._perch_until = 0.0
        self._perch_timer.stop()
        if reason == "settled" and random.random() < 0.45:
            self._host._pet.leave_life_trace("dot", random.randint(1, 2))
        self._host._pet.end_window_perch(reason, duration)

    @property
    def context_kind(self) -> str:
        return self._perch_kind

    def _check_bugs(self) -> None:
        """定时扫temp 垃圾堆大了生一只虫"""
        if self._bug is not None or self._bug_scanning:
            return
        if not self._host._settings.proactive_enabled:
            return
        if self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep:
            return
        if presence.idle_seconds() >= _AWAY_S:
            return
        self._bug_scanning = True
        threading.Thread(target=self._scan_temp_thread, daemon=True).start()

    def _scan_temp_thread(self) -> None:
        try:
            size = feeding.temp_junk_size()
            if size >= _BUG_TEMP_BYTES:
                self._bug_found.emit(size)
        finally:
            self._bug_scanning = False

    @Slot(int)
    def _on_bug_found(self, size: int) -> None:
        if self._bug is not None or not self._host._pet.isVisible():
            return
        from desktop_pet.pet.bug import BugWindow
        from desktop_pet.eyes import capture
        bug = BugWindow()
        capture.register_own_window(int(bug.winId()))
        bug.squished.connect(self._on_bug_squished)
        bug.escaped.connect(self._on_bug_escaped)
        geo = self._host._pet.frameGeometry()
        screen = self._host._app.primaryScreen().availableGeometry()
        side = 1 if geo.center().x() < screen.center().x() else -1
        bug.spawn_near(geo.center().x() + side * (geo.width() // 2 + 70),
                       min(geo.bottom() + 10, screen.bottom() - 80), screen)
        self._bug = bug
        self._host._feed_react("double_take")
        self._host._feed_pop(i18n.t("bug_spotted").format(size=feeding.human_size(size)))

    @Slot()
    def _on_bug_squished(self) -> None:
        self._bug = None
        threading.Thread(target=self._clean_temp_thread, daemon=True).start()

    def _clean_temp_thread(self) -> None:
        try:
            freed, count = feeding.clean_temp()
            self._bug_cleaned.emit(freed, count)
        except Exception:
            self._bug_cleaned.emit(0, 0)

    @Slot(int, int)
    def _on_bug_cleaned(self, freed: int, count: int) -> None:
        if count <= 0:
            self._host._feed_pop(i18n.t("bug_nothing"))
            return
        stats.add_eaten(freed, 0)  # 算它吃的 但不算文件投喂数
        emotion.apply("fed")
        selector.set_emotion(*emotion.snapshot())
        self._host._feed_react("celebrate")
        somatic.note(agent_prompts.SOMA_BUG.format(n=count, size=feeding.human_size(freed)))
        self._host._feed_pop(i18n.t("bug_squished_msg").format(n=count, size=feeding.human_size(freed)))

    @Slot()
    def _on_bug_escaped(self) -> None:
        self._bug = None
