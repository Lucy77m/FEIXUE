# author: bdth
# email: 2074055628@qq.com
# 玩耍伴生 抓虫捉迷藏投球蹲守脚印物理反馈渔获

from __future__ import annotations

import random
import threading
import time
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QTimer, Signal, Slot

from desktop_pet import i18n, journal, occasions, presence, somatic, stats
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.emotion.state import emotion
from desktop_pet.pet import feeding
from desktop_pet.pet.behavior import selector

_AWAY_S = 150.0
_BUG_SCAN_MS = 45 * 60 * 1000
_BUG_TEMP_BYTES = 500 * 1024 * 1024  # temp堆到这么大就生虫


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
        self._tail = None  # 捉迷藏的尾巴窗
        self._ball = None  # 玩具球
        self._host._pet.bind_activity_done(self._on_activity_done)
        self._perch_hwnd = 0
        self._perch_timer = QTimer(self)
        self._perch_timer.timeout.connect(self._check_perch)
        self._perch_last = 0.0
        self._host._pet.tossed.connect(self._on_tossed)
        self._host._pet.tickled.connect(self._on_tickled)

    def start(self) -> None:
        self._bug_timer.start(_BUG_SCAN_MS)

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
            pass

    def maybe_hide_seek(self) -> bool:
        """偶尔藏起来让用户找 一天最多一次"""
        if not self._host._settings.proactive_enabled or self._host._meeting_mode:
            return False
        if self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep or self._tail is not None:
            return False
        if presence.idle_seconds() >= 60:
            return False
        _val, _aro, rapport = emotion.snapshot()
        if rapport < 0.5:
            return False
        today = datetime.now().date().isoformat()
        if stats.get_note("hideseek") == today or random.random() > 0.12:
            return False
        stats.set_note("hideseek", today)
        self._host._feed_pop(i18n.t("hs_start"))
        QTimer.singleShot(1500, self._hs_hide)
        return True

    def _hs_hide(self) -> None:
        from desktop_pet.pet.hideseek import TailWindow
        from desktop_pet.eyes import capture
        if self._tail is not None or not self._host._pet.isVisible():
            return
        scr = self._host._app.primaryScreen().availableGeometry()
        x = random.randint(scr.left() + 120, scr.right() - 120)
        y = random.randint(scr.top() + 160, scr.bottom() - 120)
        tail = TailWindow()
        capture.register_own_window(int(tail.winId()))
        tail.found.connect(self._hs_found)
        tail.gave_up.connect(self._hs_gave_up)
        self._host._pet.setVisible(False)
        tail.appear_at(x, y)
        self._tail = tail

    def _hs_reveal(self, near: "QPoint | None") -> None:
        if near is not None:
            scr = self._host._app.primaryScreen().availableGeometry()
            nx = max(scr.left(), min(near.x() - self._host._pet.width() // 2, scr.right() - self._host._pet.width()))
            ny = max(scr.top(), min(near.y() - self._host._pet.height() // 2, scr.bottom() - self._host._pet.height()))
            self._host._pet.move(nx, ny)
        self._host._pet.setVisible(True)
        self._host._pet.wake()

    @Slot()
    def _hs_found(self) -> None:
        tail, self._tail = self._tail, None
        pos = tail.pos() if tail is not None else None
        self._hs_reveal(pos)
        self._host._pet.react("celebrate")
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        somatic.note(agent_prompts.SOMA_HS_FOUND)
        self._host._feed_pop(i18n.t("hs_found"))

    @Slot()
    def _hs_gave_up(self) -> None:
        self._tail = None
        self._hs_reveal(None)
        self._host._feed_pop(i18n.t("hs_giveup"))

    def hs_abort(self) -> None:
        """藏着的时候被召唤就直接现身"""
        if self._tail is not None:
            self._tail.stop()
            self._tail = None
            self._hs_reveal(None)

    def _on_activity_done(self, name: str) -> None:
        """小品演完的彩蛋 钓鱼有渔获"""
        if name != "fish":
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
            pass
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
        self._host._pet.react("perk_up")

    @Slot()
    def _on_ball_caught(self) -> None:
        self._ball = None
        self._host._pet.react("jump_spin")
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        somatic.note(agent_prompts.SOMA_BALL)
        QTimer.singleShot(900, lambda: self._host._feed_pop(i18n.t("ball_caught")))

    @Slot()
    def _on_ball_stopped(self) -> None:
        self._ball = None
        self._host._pet.react("peek")

    def maybe_perch(self) -> bool:
        """偶尔跳上前台窗口顶上待着 窗口一动摔下来"""
        if not self._host._settings.proactive_enabled or self._host._meeting_mode or self._perch_hwnd:
            return False
        if self._host._engaged() or not self._host._pet.isVisible() or self._host._pet.is_asleep or self._tail is not None:
            return False
        now = time.time()
        if now - self._perch_last < 7200 or random.random() > 0.15:
            return False
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or hwnd == int(self._host._pet.winId()):
                return False
            left, top, right, _bottom = win32gui.GetWindowRect(hwnd)
            scr = self._host._app.primaryScreen().availableGeometry()
            if right - left < 500 or top < scr.top() + self._host._pet.height() * 0.8:
                return False
            self._perch_last = now
            self._perch_hwnd = hwnd
            self._perch_rect = (left, top, right)
            x = left + int((right - left) * 0.30) - self._host._pet.width() // 2
            y = top - int(self._host._pet.height() * 0.72)
            self._host._pet.move(x, y)
            self._host._pet.react("peek")
            self._host._feed_pop(i18n.t("perch_up"))
            self._perch_timer.start(700)
            QTimer.singleShot(180_000, self._perch_done)  # 最多蹲三分钟
            return True
        except Exception:
            return False

    def _check_perch(self) -> None:
        """蹲守期间窗口动了就摔下来"""
        if not self._perch_hwnd:
            self._perch_timer.stop()
            return
        try:
            import win32gui
            if not win32gui.IsWindowVisible(self._perch_hwnd) or win32gui.IsIconic(self._perch_hwnd):
                self._perch_fall()
                return
            left, top, right, _b = win32gui.GetWindowRect(self._perch_hwnd)
            ol, ot, orr = self._perch_rect
            if abs(left - ol) > 8 or abs(top - ot) > 8 or abs(right - orr) > 8:
                self._perch_fall()
        except Exception:
            self._perch_done()

    def _perch_fall(self) -> None:
        """窗台塌了 摔下去气鼓鼓"""
        self._perch_hwnd = 0
        self._perch_timer.stop()
        self._host._pet._start_toss(random.uniform(-120, 120), 60.0)
        QTimer.singleShot(1400, lambda: self._host._pet.react("puff_up"))
        QTimer.singleShot(1700, lambda: self._host._feed_pop(i18n.t("perch_fall")))

    def _perch_done(self) -> None:
        if not self._perch_hwnd:
            return
        self._perch_hwnd = 0
        self._perch_timer.stop()
        self._host._pet.react("stretch")

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
        self._host._pet.react("double_take")
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
        self._host._pet.react("celebrate")
        somatic.note(agent_prompts.SOMA_BUG.format(n=count, size=feeding.human_size(freed)))
        self._host._feed_pop(i18n.t("bug_squished_msg").format(n=count, size=feeding.human_size(freed)))

    @Slot()
    def _on_bug_escaped(self) -> None:
        self._bug = None
