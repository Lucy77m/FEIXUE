# author: bdth
# email: 2074055628@qq.com
# 桌宠主控 装配ui agent线程和各类定时器

from __future__ import annotations

import os
import random
import re
import sys
import threading
import time
import traceback
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QColor, QCursor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from pathlib import Path

from desktop_pet import i18n, journal, occasions, persona, presence, somatic, stats, voice
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.audit import audit
from desktop_pet.docs import docs
from desktop_pet.memory.store import store
from desktop_pet.skills import skills
from desktop_pet.hotkeys import GlobalHotkeys
from desktop_pet.emotion.state import appraise_user_message, emotion
from desktop_pet.clipsampler import sampler
from desktop_pet.eyes.radar import radar
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.blackboard import BlackBoard, has_board, parse_segments
from desktop_pet.pet.chat import InputBox, SpeechText, ThoughtBubble, ThoughtBubbles
from desktop_pet.pet.todo_board import TodoBoard
from desktop_pet.pet.control_panel import ControlPanel
from desktop_pet.pet.media import MediaFrame
from desktop_pet.executor import shell as shell_exec
from desktop_pet.pet import feeding
from desktop_pet.pet.confirm import ConfirmBox
from desktop_pet.pet.entrance import next_entrance_kind
from desktop_pet.pet.tray import Tray
from desktop_pet.pet.window import PetWindow
from desktop_pet.proactive import proactive
from desktop_pet.reminders import reminders
from desktop_pet.remote import remote_inbox
from desktop_pet.settings import Settings

_EMOTION_RE = re.compile(r"^\s*\[(\w+)\]\s*")
_SPLIT_AFTER = frozenset("。！？!?，、；,;")
_BRACKETS = {"（": "）", "(": ")", "「": "」", "『": "』", "【": "】", "《": "》", "〈": "〉",
             "[": "]", "{": "}", "“": "”", "‘": "’"}

_PRESENCE_POLL_MS = 12_000
_AWAY_S = 150.0
_AWAY_NIGHT_S = 75.0
_REMINDER_POLL_MS = 15_000
_PROACTIVE_POLL_MS = 60_000
_WATCH_POLL_MS = 15_000
_REMOTE_POLL_MS = 8_000
_BGWATCH_POLL_MS = 5_000
_BGWATCH_MIN_RUNTIME_S = 10.0  # 秒退的任务agent当场看到 不播报
_GIVEBACK_MIN_INTERVAL_S = 4 * 3600
_GIVEBACK_MIN_AGE_H = 2.0  # 收藏攒够这么久才值得拿出来
_GIVEBACK_RAPPORT_GATE = 0.45
_BUG_SCAN_MS = 45 * 60 * 1000
_BUG_TEMP_BYTES = 500 * 1024 * 1024  # temp堆到这么大就生虫
_SHY_POLL_MS = 2500
_SHY_POP_COOLDOWN_S = 120.0
_VITALS_POLL_MS = 10_000
_HOT_POP_COOLDOWN_S = 600.0
_MEM_POP_COOLDOWN_S = 900.0
_SNUGGLE_COOLDOWN_S = 3600.0
_DL_POLL_MS = 30_000
_MIC_POLL_MS = 30_000
_DESK_POLL_MS = 3600_000
_DESK_LIMIT = 40
_FOCUS_MINUTES = 25
_SHOT_COOLDOWN_S = 300.0
_PROACTIVE_RAPPORT_GATE = {"安静": 0.45, "正常": 0.30, "话痨": 0.15}
_PROACTIVE_RAPPORT_GATE_DEFAULT = 0.30
_CELEBRATE_CHANCE = 0.25
_EXPLORE_CHANCE = 0.3
_PEEK_MIN_INTERVAL_S = 600.0
_PET_MARGIN = 60

_SUPPRESSED_QT_WARNINGS = ("UpdateLayeredWindowIndirect", "iCCP")
_prev_qt_handler = None


def _install_qt_message_filter() -> None:
    global _prev_qt_handler

    def _filter(mode, context, message) -> None:
        if any(token in message for token in _SUPPRESSED_QT_WARNINGS):
            return
        if _prev_qt_handler is not None:
            _prev_qt_handler(mode, context, message)
        else:
            sys.stderr.write(message + "\n")

    _prev_qt_handler = qInstallMessageHandler(_filter)


def _light_palette() -> QPalette:
    """qt部件统一浅色"""
    p = QPalette()
    base = QColor("#ffffff")
    text = QColor("#3b3a4d")
    p.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f3fc"))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor("#f5f3fc"))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Highlight, QColor("#efecff"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#6a59f5"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#a8a6bc"))
    return p


def _parse_emotion(text: str) -> tuple[str, str]:
    match = _EMOTION_RE.match(text)
    if match:
        return match.group(1).lower(), text[match.end():].strip()
    return "neutral", text.strip()


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    stack: list[str] = []
    for ch in text:
        if ch == "\n":
            if buf:
                out.append("".join(buf))
                buf = []
            stack.clear()
            continue
        buf.append(ch)
        if ch in _BRACKETS:
            stack.append(_BRACKETS[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
        elif ch in _SPLIT_AFTER and not stack:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    sentences = [s.strip() for s in out if s.strip()]
    return sentences or [text.strip()]


def _friendly_error(exc: Exception) -> str:
    """异常转成一句人话"""
    name = type(exc).__name__
    nlow = name.lower()
    msg = str(exc)
    low = msg.lower()
    if "authentication" in nlow or "401" in msg or "invalid api key" in low or "incorrect api key" in low or "unauthorized" in low:
        return "诶…我连不上大脑：API key 好像不对或没权限。打开控制面板检查下密钥吧。"
    if "permission" in nlow or "403" in msg:
        return "这个 key 没访问权限（403）——确认下密钥对应的服务开通了没。"
    if "notfound" in nlow or ("404" in msg and "model" in low):
        return "模型名字我这边没找到（404），去控制面板核对下模型名。"
    if "connection" in nlow or "timeout" in nlow or any(
        k in low for k in ("timed out", "connect", "getaddrinfo", "ssl", "proxy", "failed to establish")
    ):
        return "网络连不上或超时了——检查下网络 / 代理设置？"
    if "ratelimit" in nlow or "429" in msg or "quota" in low or "rate limit" in low:
        return "请求太频繁或额度用完了（429），缓一下再试～"
    short = msg if len(msg) <= 200 else msg[:200] + "…"
    return f"出了点状况：{name}: {short}"


class AgentWorker(QObject):

    reply_ready = Signal(str)
    proactive_reply = Signal(str)
    busy_changed = Signal(bool)
    task_finished = Signal(bool)
    step = Signal(str)
    think_text = Signal(str)
    plan_changed = Signal(str)
    media_requested = Signal(str, str, str)
    perform_requested = Signal(str)
    background_done = Signal(str, str)
    rewrite_ready = Signal(str)
    analysis_ready = Signal(str)

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self._agent = agent
        self._running = False
        self._agent.set_notify(self.background_done.emit)

    @property
    def is_running(self) -> bool:
        return self._running

    @Slot(str, object)
    def handle(self, text: str, attachments: object = None) -> None:
        self._running = True
        self.busy_changed.emit(True)
        ok = True
        try:
            try:
                reply = self._agent.run(
                    text, attachments=attachments,
                    on_step=self.step.emit, on_think=self.think_text.emit,
                    on_plan=self.plan_changed.emit, on_media=self.media_requested.emit,
                    on_perform=self.perform_requested.emit,
                )
            except Exception as exc:
                reply = _friendly_error(exc)
                ok = False
                audit.reply(f"{reply}\n{traceback.format_exc()}")
            if self._agent.was_cancelled(reply) or self._agent.is_cancelled:
                self.busy_changed.emit(False)
                return   # 被取消时丢掉回复
            self.reply_ready.emit(reply)
            self.busy_changed.emit(False)
            self.task_finished.emit(ok and not self._agent.hit_step_limit)
            if ok:
                try:
                    self._agent.reflect()
                except Exception:
                    pass
        finally:
            self._running = False

    def cancel(self) -> None:
        self._agent.cancel()

    def set_confirm(self, on_confirm) -> None:
        self._agent.set_confirm(on_confirm)

    def shutdown(self) -> None:
        self._agent.close()

    @Slot(str)
    def deliver_reminder(self, what: str) -> None:
        try:
            reply = self._agent.deliver_reminder(what)
            if reply.strip():
                self.reply_ready.emit(reply)
        except Exception as exc:
            audit.system("deliver_reminder failed", error=repr(exc))

    @Slot(str)
    def run_task(self, task: str) -> None:
        try:
            self._agent.run_background(task)
        except Exception as exc:
            audit.system("run_task dispatch failed", error=repr(exc))

    @Slot(str)
    def run_timed_task(self, task: str) -> None:
        self._running = True
        self.busy_changed.emit(True)
        try:
            try:
                reply = self._agent.run_timed_task(
                    task, on_step=self.step.emit, on_think=self.think_text.emit,
                    on_plan=self.plan_changed.emit, on_media=self.media_requested.emit,
                    on_perform=self.perform_requested.emit,
                )
            except Exception as exc:
                reply = _friendly_error(exc)
            if reply.strip() and not (self._agent.was_cancelled(reply) or self._agent.is_cancelled):
                self.reply_ready.emit(reply)
        finally:
            self.busy_changed.emit(False)
            self._running = False

    @Slot(str, str)
    def speak_spontaneously(self, mode: str, context: str) -> None:
        try:
            reply = self._agent.speak_spontaneously(mode, context)
            if reply.strip():
                self.proactive_reply.emit(reply)
        except Exception as exc:
            audit.system("speak_spontaneously failed", error=repr(exc))

    @Slot(str)
    def explore(self, topic: str) -> None:
        # 慢活开daemon线程跑 不占worker事件循环 下面几个同理
        def work() -> None:
            try:
                reply = self._agent.explore_topic(topic)
            except Exception as exc:
                audit.system("explore failed", error=repr(exc))
                reply = ""
            if reply and reply.strip():
                self.proactive_reply.emit(reply)
        threading.Thread(target=work, daemon=True, name="mochi-explore").start()

    @Slot(str)
    def peek_screen(self, trigger: str = "") -> None:
        def work() -> None:
            try:
                reply = self._agent.peek_screen(trigger)
            except Exception as exc:
                audit.system("peek_screen failed", error=repr(exc))
                reply = ""
            if reply and reply.strip():
                self.proactive_reply.emit(reply)
        threading.Thread(target=work, daemon=True, name="mochi-peek").start()

    @Slot(str)
    def analyze_screen(self, focus: str) -> None:
        def work() -> None:
            try:
                reply = self._agent.analyze_screen(focus)
            except Exception as exc:
                audit.system("analyze_screen failed", error=repr(exc))
                reply = ""
            self.analysis_ready.emit(reply or "")
        threading.Thread(target=work, daemon=True, name="mochi-watch").start()

    @Slot(str)
    def rewrite(self, text: str) -> None:
        def work() -> None:
            try:
                out = self._agent.rewrite_text(text)
            except Exception as exc:
                audit.system("rewrite failed", error=repr(exc))
                out = ""
            self.rewrite_ready.emit(out)
        threading.Thread(target=work, daemon=True, name="mochi-rewrite").start()

    @Slot(str, str)
    def clip_alchemy(self, kind: str, text: str) -> None:
        def work() -> None:
            try:
                out = self._agent.transform_clipboard(kind, text)
            except Exception as exc:
                audit.system("clip_alchemy failed", error=repr(exc))
                out = ""
            if out and out.strip():
                self.proactive_reply.emit(out)
        threading.Thread(target=work, daemon=True, name="mochi-alchemy").start()

    def forget_all(self) -> None:
        self._agent.forget_all()

    def new_topic(self) -> None:
        self._agent.new_topic()


_ALCHEMY_MIN_INTERVAL_S = 45.0


class PetApp(QObject):
    request_reminder = Signal(str)
    request_task = Signal(str)
    request_timed_task = Signal(str)
    request_proactive = Signal(str, str)
    request_explore = Signal(str)
    request_peek = Signal(str)
    request_analyze = Signal(str)
    request_message = Signal(str)
    _remote_action = Signal(str, str)
    request_confirm = Signal(str)
    request_rewrite = Signal(str)
    request_clip_alchemy = Signal(str, str)
    _feed_note = Signal(str)
    _bug_found = Signal(int)
    _bug_cleaned = Signal(int, int)
    _shy_changed = Signal(bool)
    _vitals_ready = Signal(object)
    _dl_found = Signal(str)
    _mic_changed = Signal(bool)
    _desk_crowded = Signal(int)
    _weather_ready = Signal(str)
    _voice_chunk_done = Signal(int)
    _voice_chunk_start = Signal(int)
    _voice_chunk_progress = Signal(int, int)

    def __init__(self) -> None:
        _install_qt_message_filter()
        self._app = QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._app.setPalette(_light_palette())
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setFont(QFont("Microsoft YaHei UI", 10))
        from desktop_pet.pet.icon import mochi_icon
        self._app.setWindowIcon(mochi_icon())
        super().__init__()

        self._busy = False
        self._shown = False
        self._entered = False
        self._panel = None
        self._relang = False
        self._relang_intro = None
        self._speak_gen = 0
        self._fired_occasions: set[str] = set()
        self._last_peek: datetime | None = None
        self._watch_inflight = False
        self._inbox_inflight = False
        self._cancelling = False
        self._pending_quit = False
        self._pending_bg: list[tuple[str, str]] = []
        self._timed_queue: list[str] = []
        self._timed_inflight = False
        self._inflight_timed: str | None = None
        self._confirm_event = threading.Event()
        self._confirm_result = False
        self._confirm_pending = False
        self._feed_pending: tuple[list, int] | None = None
        self._feed_doc: str | None = None

        from desktop_pet.agent.loop import Agent

        self._settings = Settings.load()
        i18n.set_language(self._settings.ui_language)
        emotion.apply("returned")
        selector.set_emotion(*emotion.snapshot())

        self._pet = PetWindow()
        self._speech = SpeechText()
        self._input = InputBox()
        self._board = BlackBoard()
        self._todo = TodoBoard()
        self._media = MediaFrame()
        self._confirm_box = ConfirmBox()
        self._feed_confirm = ConfirmBox()
        self._thought = ThoughtBubble()
        self._think = ThoughtBubbles()

        from desktop_pet.eyes import capture
        for _w in (self._pet, self._speech, self._input, self._board, self._todo, self._media, self._confirm_box, self._feed_confirm, self._thought, self._think):
            capture.register_own_window(int(_w.winId()))

        self._lecturing = False
        self._segments: list[tuple[str, str]] = []
        self._seg_i = 0
        self._board_dismiss = QTimer(self)
        self._board_dismiss.setSingleShot(True)
        self._board_dismiss.timeout.connect(self._end_lecture)
        self._board_next = QTimer(self)
        self._board_next.setSingleShot(True)
        self._board_next.timeout.connect(self._advance_lecture)

        mcp_hub.start()
        self._thread = QThread()
        self._worker = AgentWorker(Agent(self._settings))
        self._worker.set_confirm(self._confirm)
        self._worker.moveToThread(self._thread)

        self._presence_timer = QTimer(self)
        self._presence_timer.timeout.connect(self._on_presence)
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._proactive_timer = QTimer(self)
        self._proactive_timer.timeout.connect(self._check_proactive)
        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._check_watch)
        self._remote_timer = QTimer(self)
        self._remote_timer.timeout.connect(self._check_inbox)
        self._bgwatch_timer = QTimer(self)
        self._bgwatch_timer.timeout.connect(self._scan_background_shells)
        self._bg_announced: set[int] = set()
        self._bug_timer = QTimer(self)
        self._bug_timer.timeout.connect(self._check_bugs)
        self._bug = None
        self._bug_scanning = False
        self._bug_found.connect(self._on_bug_found)
        self._bug_cleaned.connect(self._on_bug_cleaned)
        self._shy_timer = QTimer(self)
        self._shy_timer.timeout.connect(self._check_password_focus)
        self._shy_now = False
        self._shy_checking = False
        self._shy_last_pop = 0.0
        self._shy_changed.connect(self._on_shy_changed)
        self._vitals_timer = QTimer(self)
        self._vitals_timer.timeout.connect(self._check_vitals)
        self._vitals_busy = False
        self._vitals_ready.connect(self._on_vitals)
        self._dl_timer = QTimer(self)
        self._dl_timer.timeout.connect(self._check_downloads)
        self._dl_busy = False
        self._dl_seen: set[str] = set()
        self._dl_baseline = time.time()
        self._dl_found.connect(self._on_dl_found)
        self._mic_timer = QTimer(self)
        self._mic_timer.timeout.connect(self._check_mic)
        self._mic_busy = False
        self._meeting_mode = False
        self._mic_changed.connect(self._on_mic_changed)
        self._desk_timer = QTimer(self)
        self._desk_timer.timeout.connect(self._check_desktop)
        self._desk_busy = False
        self._desk_crowded.connect(self._on_desk_crowded)
        self._focus_until = 0.0
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self._end_focus)
        self._shot_last = 0.0
        from desktop_pet.pet.footprints import FootprintLayer
        self._paws = FootprintLayer()
        self._paw_last = QPoint()
        self._pet.moved.connect(self._on_pet_moved_paws)
        self._tail = None  # 捉迷藏的尾巴窗
        self._ball = None  # 玩具球
        self._pet.bind_activity_done(self._on_activity_done)
        self._perch_hwnd = 0
        self._perch_timer = QTimer(self)
        self._perch_timer.timeout.connect(self._check_perch)
        self._perch_last = 0.0
        self._weather_timer = QTimer(self)
        self._weather_timer.timeout.connect(self._check_weather)
        self._weather_busy = False
        self._weather_kind = ""
        self._weather_ready.connect(self._on_weather)
        QTimer.singleShot(60_000, self._check_weather)
        self._hot_on = False
        self._cpu_high_n = 0
        self._hot_last_pop = 0.0
        self._squeeze_on = False
        self._mem_last_pop = 0.0
        self._lowbatt_on = False
        self._blanket_on = False
        self._late_popped_date = ""
        self._cpu_idle_n = 0
        self._cpu_warm_n = 0
        self._snuggle_last = 0.0
        from collections import deque
        self._clip_treasures: deque = deque(maxlen=12)  # 帮用户收着的剪贴小宝贝 只在内存
        self._last_giveback: datetime | None = None
        self._just_returned = False

        self._tray = Tray(
            on_open_panel=self._open_panel,
            on_quit=self._quit,
            on_talk=self._summon,
            on_peek=self._peek_now,
            on_new_topic=self._new_topic,
            on_toggle_show=self._toggle_power,
            is_shown=lambda: self._shown,
            on_focus=self._toggle_focus,
            on_ball=self._throw_ball,
            on_perform=self._on_perform,
        )
        self._hotkeys = GlobalHotkeys({
            "summon": self._settings.hotkey_summon,
            "ask": self._settings.hotkey_ask,
            "quick": self._settings.hotkey_quick,
        })
        self._hotkey_status: dict = {}
        self._connect()

    def _connect(self) -> None:
        self._pet.clicked.connect(self._toggle_input)
        self._pet.clicked.connect(self._on_pet_clicked_cake)
        self._pet.moved.connect(self._follow)
        self._pet.grabbed.connect(self._wake)
        self._pet.hid.connect(self._on_hide)
        self._pet.wants_travel.connect(self._on_wants_travel)
        self._pet.context_requested.connect(self._show_quick_menu)
        self._speech.talking.connect(self._on_speech_talking)
        self._speech.finished.connect(self._on_speech_finished)
        # 藏边时整只露出的判据 说话中或讲课中
        self._pet.bind_speaking(lambda: self._speech.is_speaking or self._lecturing)
        self._speech.chunk_shown.connect(self._on_chunk_shown)
        self._voice_chunk_done.connect(self._on_voice_chunk_done)
        self._voice_chunk_start.connect(self._on_voice_chunk_start)
        self._voice_chunk_progress.connect(self._on_voice_chunk_progress)
        self._input.submitted.connect(self._worker.handle)
        self._input.submitted.connect(self._on_submit)
        self._worker.reply_ready.connect(self._on_reply)
        self._worker.proactive_reply.connect(self._on_proactive_reply)
        self._worker.busy_changed.connect(self._on_busy)
        self._worker.task_finished.connect(self._on_task_finished)
        self._worker.step.connect(self._on_step)
        self._worker.think_text.connect(self._on_think_text)
        self._worker.plan_changed.connect(self._on_plan)
        self._worker.media_requested.connect(self._on_media)
        self._worker.perform_requested.connect(self._on_perform)
        self._worker.background_done.connect(self._on_background_done)
        self.request_reminder.connect(self._worker.deliver_reminder)
        self.request_task.connect(self._worker.run_task)
        self.request_timed_task.connect(self._worker.run_timed_task)
        self.request_proactive.connect(self._worker.speak_spontaneously)
        self.request_explore.connect(self._worker.explore)
        self.request_peek.connect(self._worker.peek_screen)
        self.request_analyze.connect(self._worker.analyze_screen)
        self.request_message.connect(self._worker.handle)
        self._worker.analysis_ready.connect(self._on_analysis)
        self._remote_action.connect(self._on_remote_action)
        self.request_confirm.connect(self._on_confirm_requested)
        self._confirm_box.answered.connect(self._on_confirm_answered)
        self._pet.fed.connect(self._on_fed)
        self._feed_confirm.answered.connect(self._on_feed_answer)
        self._feed_note.connect(self._on_feed_note)
        self._pet.tossed.connect(self._on_tossed)
        self._pet.tickled.connect(self._on_tickled)
        self._hotkeys.summon.connect(self._summon)
        self._hotkeys.ask_selection.connect(self._ask_selection)
        self._hotkeys.quick_rewrite.connect(self._quick_rewrite)
        self._hotkeys.status.connect(self._on_hotkey_status)
        self.request_rewrite.connect(self._worker.rewrite)
        self._worker.rewrite_ready.connect(self._on_rewrite_done)
        self._app.clipboard().dataChanged.connect(self._on_clipboard_changed)
        sampler.interesting.connect(self._on_clip_interesting)
        self.request_clip_alchemy.connect(self._worker.clip_alchemy)
        sampler.set_enabled(self._settings.clip_sampler or self._settings.clip_alchemy)

    def _cancel_active_task(self, *, notify: bool = True) -> bool:
        """停掉正在跑的任务和发言 返回是否确实停了"""
        busy = self._worker.is_running or self._busy or self._speech.is_speaking or self._lecturing
        if not busy or self._cancelling:
            return False
        self._cancelling = True
        self._worker.cancel()
        self._confirm_result = False
        self._confirm_event.set()
        self._confirm_box.close_box()
        self._on_busy(False)
        self._speech.interrupt()
        voice.flush()
        self._reset_lecture()
        self._todo.dismiss()
        self._requeue_timed()
        self._pet.clear_pending()
        if notify:
            self._thought.pop(i18n.t("ui_stopped"), self._pet)
        return True

    @Slot()
    def _toggle_input(self) -> None:
        self._wake()
        if self._cancel_active_task():
            return
        if self._input.isVisible():
            self._input.fade_out()
        else:
            self._input.popup(self._pet)

    @Slot()
    def _peek_now(self) -> None:
        """手动触发看一眼屏幕"""
        if self._worker.is_running or self._busy:
            return
        if not self._shown:
            self._power_on()
        if not self._pet.isVisible():
            self._pet.setVisible(True)
        self._pet.wake()
        self.request_message.emit(i18n.t("peek_request"))

    @Slot(QPoint)
    def _show_quick_menu(self, pos: QPoint) -> None:
        # 复用托盘菜单
        self._tray.context_menu().popup(pos)

    @Slot()
    def _summon(self) -> None:
        if not self._shown:
            self._power_on()
        self._hs_abort()
        if not self._pet.isVisible():
            self._pet.setVisible(True)
        self._pet.summon_front()
        if not self._input.isVisible():
            self._input.popup(self._pet)
        else:
            self._input.place_below(self._pet)
        self._input.raise_()
        self._input.activateWindow()
        self._input.setFocus()

    @Slot()
    def _on_hotkey_status(self, status: object) -> None:
        if isinstance(status, dict):
            self._hotkey_status = status

    def _hotkey_status_snapshot(self) -> dict:
        return dict(self._hotkey_status)

    @Slot()
    def _ask_selection(self) -> None:
        if not self._shown:
            self._power_on()
        self._saved_clip = self._app.clipboard().text()   # 先存原剪贴板 复制完还回去
        try:
            import pyautogui
            # 先松开残留的修饰键再模拟复制
            for mod in ("alt", "ctrl", "shift"):
                pyautogui.keyUp(mod)
        except Exception:
            self._summon()
            return
        QTimer.singleShot(70, self._copy_selection)

    def _copy_selection(self) -> None:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "c")
        except Exception:
            self._summon()
            return
        QTimer.singleShot(200, self._after_copy)

    def _after_copy(self) -> None:
        text = self._app.clipboard().text().strip()
        saved = getattr(self, "_saved_clip", "")
        self._summon()
        if not text or text == saved.strip():   # 剪贴板没变当作无选区
            return
        self._app.clipboard().setText(saved)     # 还回原剪贴板
        snippet = text if len(text) <= 500 else text[:500] + "…"
        self._input.setText(f"关于这个：{snippet}")
        self._input.setFocus()

    @Slot()
    def _quick_rewrite(self) -> None:
        if not self._shown:
            self._power_on()
        self._saved_clip = self._app.clipboard().text()
        try:
            import pyautogui
            for mod in ("alt", "ctrl", "shift"):
                pyautogui.keyUp(mod)
        except Exception:
            return
        QTimer.singleShot(70, self._quick_copy)

    def _quick_copy(self) -> None:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "c")
        except Exception:
            return
        QTimer.singleShot(200, self._quick_after_copy)

    def _quick_after_copy(self) -> None:
        text = self._app.clipboard().text().strip()
        saved = getattr(self, "_saved_clip", "")
        if not self._pet.isVisible():
            self._pet.setVisible(True)
        self._pet.wake()
        if not text or text == saved.strip():
            self._thought.pop(i18n.t("quick_noselect"), self._pet)
            return
        self._thought.show_step(i18n.t("quick_working"), self._pet)
        self.request_rewrite.emit(text)

    @Slot(str)
    def _on_rewrite_done(self, result: str) -> None:
        if not result.strip():
            self._thought.pop(i18n.t("quick_failed"), self._pet)
            return
        sampler.mark_self_write(result)
        self._app.clipboard().setText(result)
        if self._settings.quick_paste_back:
            try:
                import pyautogui
                QTimer.singleShot(60, lambda: pyautogui.hotkey("ctrl", "v"))
            except Exception:
                pass
        self._thought.pop(i18n.t("quick_done"), self._pet)

    @Slot()
    def _on_clipboard_changed(self) -> None:
        try:
            cb = self._app.clipboard()
            # 剪贴板进了图多半是刚截图 凑过来搭把手
            if cb.mimeData().hasImage() and not cb.mimeData().hasText():
                now = time.time()
                if now - self._shot_last > _SHOT_COOLDOWN_S and not self._worker.is_running:
                    self._shot_last = now
                    self._pet.react("peek")
                    self._feed_pop(i18n.t("shot_offer"))
                return
            sampler.feed(cb.text())
        except Exception:
            pass

    @Slot(str, str)
    def _on_clip_interesting(self, kind: str, text: str) -> None:
        # 顺手收藏一份留着回赠 只进内存不落盘 胸前吊牌跟着变
        if all(text != t for _k, t, _ts in self._clip_treasures):
            self._clip_treasures.append((kind, text, datetime.now()))
            self._pet.set_pendant(len(self._clip_treasures))
        s = self._settings
        if not s.clip_alchemy:
            return
        allowed = {k.strip() for k in (s.clip_alchemy_kinds or "").split(",") if k.strip()}
        if allowed and kind not in allowed:
            return
        if (self._worker.is_running or self._busy or self._lecturing or self._speech.is_speaking
                or self._input.isVisible() or not self._pet.isVisible() or self._pet.is_asleep):
            return
        now = datetime.now()
        last = getattr(self, "_last_alchemy", None)
        if last is not None and (now - last).total_seconds() < _ALCHEMY_MIN_INTERVAL_S:
            return
        self._last_alchemy = now
        self.request_clip_alchemy.emit(kind, text)

    @Slot(str, object)
    def _on_submit(self, _text: str, _attachments: object = None) -> None:
        try:
            emotion.apply("interaction")
            tone = appraise_user_message(_text)
            if tone:
                emotion.apply(tone)
        except Exception:
            pass
        selector.set_emotion(*emotion.snapshot())
        self._wake()
        self._todo.dismiss()
        self._just_returned = False
        stats.bump_interactions()
        proactive.defer(datetime.now(), self._settings.proactive_level)
        self._input.fade_out()

    @Slot(str)
    @Slot(str)
    def _on_proactive_reply(self, raw: str) -> None:
        if self._foreground_busy() or self._lecturing:
            return
        self._on_reply(raw)

    def _on_reply(self, raw: str) -> None:
        tag, text = _parse_emotion(raw)
        self._pet.express(tag)
        self._reset_lecture()
        self._speech.interrupt()
        voice.flush()
        segments = parse_segments(text)
        self._speak_gen += 1   # 步进发言代次 作废上一轮tts回调
        if any(kind == "board" for kind, _ in segments):
            # 黑板走讲课逐段流 tts只念口语段
            voice.speak(" ".join(body for kind, body in segments if kind != "board"))
            self._start_lecture(segments)
        else:
            self._speech.place_below(self._pet)
            sents = _split_sentences(text)
            self._speech.speak(sents, paced=voice.is_enabled())

    @Slot(str, str)
    def _on_background_done(self, task: str, result: str) -> None:
        self._pending_bg.append((task, result))
        self._drain_pending_bg()

    def _engaged(self) -> bool:
        """是否正忙或用户交互中"""
        return (self._worker.is_running or self._busy or self._lecturing
                or self._speech.is_speaking or self._input.isVisible())

    def _foreground_busy(self) -> bool:
        return self._engaged() or self._cancelling

    def _drain_pending_bg(self) -> None:
        if not self._pending_bg:
            return
        if not self._shown or not self._pet.isVisible():
            for task, result in self._pending_bg:
                self._tray.notify(i18n.t("tray_tooltip"), f"{task[:24]}：{result[:200]}")
            self._pending_bg.clear()
            return
        if self._foreground_busy():
            return
        task, result = self._pending_bg.pop(0)
        self._pet.wake()
        self._on_reply("[happy]\n" + i18n.t("ui_bg_done").format(task=task[:24], result=result))

    def _start_lecture(self, segments: list[tuple[str, str]]) -> None:
        self._segments = segments
        self._seg_i = 0
        self._lecturing = True
        self._pet.set_lecturing(True)
        self._advance_lecture()

    def _advance_lecture(self) -> None:
        if self._seg_i >= len(self._segments):
            self._board_dismiss.start(self._board.suggested_linger_ms())
            return
        kind, body = self._segments[self._seg_i]
        self._seg_i += 1
        if kind == "board":
            self._board.present(body, self._pet, self._app.primaryScreen().availableGeometry())
            self._board_next.start(self._board.suggested_linger_ms())
        else:
            self._speech.place_below(self._pet)
            self._speech.speak(_split_sentences(body))

    def _end_lecture(self) -> None:
        self._board.dismiss()
        self._pet.set_lecturing(False)
        self._lecturing = False
        self._drain_pending_bg()

    def _reset_lecture(self) -> None:
        self._board_dismiss.stop()
        self._board_next.stop()
        if self._lecturing or self._board.isVisible():
            self._end_lecture()

    @Slot()
    def _on_speech_finished(self) -> None:
        self._pet.set_state("rest")
        if self._lecturing:
            self._advance_lecture()
        else:
            self._drain_pending_bg()

    @Slot(bool)
    def _on_speech_talking(self, on: bool) -> None:
        self._pet.set_state("speaking" if on else "rest")

    @Slot(str)
    def _on_chunk_shown(self, chunk: str) -> None:
        gen = self._speak_gen
        voice.speak_one(
            chunk,
            on_start=lambda g=gen: self._voice_chunk_start.emit(g),
            on_progress=lambda n, g=gen: self._voice_chunk_progress.emit(g, n),
            on_done=lambda g=gen: self._voice_chunk_done.emit(g),
        )

    @Slot(int)
    def _on_voice_chunk_start(self, gen: int) -> None:
        # gen对不上是上一轮残留回调 丢掉
        if gen != self._speak_gen:
            return
        self._speech.begin_chunk()

    @Slot(int, int)
    def _on_voice_chunk_progress(self, gen: int, shown: int) -> None:
        if gen != self._speak_gen:
            return
        self._speech.set_progress(shown)

    @Slot(int)
    def _on_voice_chunk_done(self, gen: int) -> None:
        if gen != self._speak_gen or not self._speech.is_speaking:
            return
        self._speech.advance()

    @Slot(str)
    def _on_step(self, label: str) -> None:
        if self._cancelling:
            return
        self._pet.note_think_step(label)
        if label == "思考中…":
            return
        self._thought.show_step(label, self._pet)

    @Slot(str)
    def _on_think_text(self, fragment: str) -> None:
        if self._cancelling:
            return
        self._think.feed(fragment)

    @Slot(str)
    def _on_plan(self, markdown: str) -> None:
        if self._cancelling or not self._pet.isVisible():
            return
        self._todo.set_markdown(markdown, self._pet, self._app.primaryScreen().availableGeometry())

    @Slot(str, str, str)
    def _on_media(self, kind: str, path: str, caption: str) -> None:
        if self._cancelling:
            return
        screen = self._app.primaryScreen().availableGeometry()
        if kind == "gif":
            self._media.play_gif(path, caption, self._pet, screen)
        else:
            self._media.show_image(path, caption, self._pet, screen)

    @Slot(str)
    def _on_perform(self, name: str) -> None:
        if self._cancelling:
            return
        self._wake()
        self._pet.perform(name)

    def _confirm(self, action: str) -> bool:
        # 工人线程里发信号让gui弹确认框 阻塞等回答 超时按否
        self._confirm_result = False
        self._confirm_event.clear()
        self._confirm_pending = True
        self.request_confirm.emit(action)
        try:
            self._confirm_event.wait(timeout=300)
            return self._confirm_result
        finally:
            self._confirm_pending = False

    @Slot(str)
    def _on_confirm_requested(self, action: str) -> None:
        if self._cancelling:
            self._confirm_event.set()
            return
        self._wake()
        screen = self._app.primaryScreen().availableGeometry()
        self._confirm_box.ask(action, self._pet, screen)

    @Slot(bool)
    def _on_confirm_answered(self, ok: bool) -> None:
        if not self._confirm_pending:
            return
        self._confirm_result = ok
        self._confirm_event.set()

    @Slot(list)
    def _on_fed(self, paths: list) -> None:
        """投喂入口 按类型分流"""
        kind = feeding.classify(paths)
        if kind == "missing":
            self._feed_pop(i18n.t("feed_missing"))
            return
        if kind == "protected":
            self._pet.react("recoil")
            self._feed_pop(i18n.t("feed_protected"))
            return
        if kind == "risky":
            self._pet.react("shake")
            self._feed_pop(i18n.t("feed_risky"))
            return
        if kind == "image":
            if self._worker.is_running:
                self._feed_pop(i18n.t("feed_busy"))
                return
            path = str(Path(paths[0]).expanduser().resolve())
            self._pet.react("perk_up")
            self.request_message.emit(agent_prompts.FEED_IMAGE_MSG.format(name=Path(path).name, path=path))
            return
        if kind == "doc":
            self._feed_doc = paths[0]
            screen = self._app.primaryScreen().availableGeometry()
            self._feed_confirm.ask(i18n.t("feed_doc_ask").format(name=Path(paths[0]).name), self._pet, screen)
            return
        total, truncated = feeding.total_size(paths)
        if total > feeding._BIG_BYTES or feeding.has_dir(paths) or truncated:
            self._feed_pending = (paths, total)
            name = Path(paths[0]).name + (f" +{len(paths) - 1}" if len(paths) > 1 else "")
            screen = self._app.primaryScreen().availableGeometry()
            self._feed_confirm.ask(
                i18n.t("feed_confirm").format(name=name, size=feeding.human_size(total)), self._pet, screen)
            return
        self._eat(paths, total)

    @Slot(bool)
    def _on_feed_answer(self, ok: bool) -> None:
        """投喂确认回来 文档和大餐两种等待"""
        if self._feed_doc is not None:
            path, self._feed_doc = self._feed_doc, None
            if not ok:
                return
            self._pet.react("eating")
            threading.Thread(target=self._ingest_doc, args=(path,), daemon=True).start()
            return
        if self._feed_pending is not None:
            (paths, total), self._feed_pending = self._feed_pending, None
            if ok:
                self._eat(paths, total)

    def _ingest_doc(self, path: str) -> None:
        """后台线程读文档进知识库"""
        try:
            docs.ingest(path)
            self._feed_note.emit(i18n.t("feed_doc_done"))
        except Exception:
            self._feed_note.emit(i18n.t("feed_doc_fail"))

    def _eat(self, paths: list, total: int) -> None:
        """播吃动画 咽下去时真删"""
        self._pet.react("eating")
        QTimer.singleShot(1700, lambda: self._finish_eat(paths, total))

    def _finish_eat(self, paths: list, total: int) -> None:
        err = feeding.recycle(paths)
        if err:
            self._pet.react("droop")
            self._feed_pop(i18n.t("feed_eat_fail"))
            audit.reply(f"feed recycle failed: {err}")
            return
        stats.add_eaten(total, len(paths))
        emotion.apply("fed")
        selector.set_emotion(*emotion.snapshot())
        self._pet.set_expression("happy")
        names = Path(paths[0]).name + (f" +{len(paths) - 1}" if len(paths) > 1 else "")
        somatic.note(agent_prompts.SOMA_FED.format(names=names, size=feeding.human_size(total)))
        if total > 100 * 1024 * 1024:
            journal.add(f"主人喂我吃了 {feeding.human_size(total)} 的垃圾文件 饱了")
        self._feed_pop(i18n.t("feed_eaten").format(size=feeding.human_size(total)))

    @Slot(str)
    def _on_feed_note(self, text: str) -> None:
        self._feed_pop(text)

    def _feed_pop(self, text: str) -> None:
        if self._meeting_mode:
            return  # 开会静音 主动气泡全咽下去
        self._thought.pop(text, self._pet)

    @Slot(float)
    def _on_tossed(self, impact: float) -> None:
        """被重摔了 疼一下还要哄"""
        emotion.apply("hurt")
        selector.set_emotion(*emotion.snapshot())
        self._pet.set_expression("sad")
        somatic.note(agent_prompts.SOMA_TOSSED)
        somatic.set_state("grudge", agent_prompts.SOMA_GRUDGE)
        QTimer.singleShot(30 * 60 * 1000, lambda: somatic.set_state("grudge", None))
        self._feed_pop(i18n.t("toss_ouch"))

    @Slot()
    def _on_tickled(self) -> None:
        """被挠痒 开心计入互动"""
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        stats.bump_interactions()
        somatic.note(agent_prompts.SOMA_TICKLED)

    def _check_password_focus(self) -> None:
        """低频看一眼焦点是不是密码框 是就捂眼"""
        if self._shy_checking or not self._settings.allow_control:
            return
        if not self._pet.isVisible():
            return
        self._shy_checking = True
        threading.Thread(target=self._shy_probe_thread, daemon=True).start()

    def _shy_probe_thread(self) -> None:
        try:
            from desktop_pet.eyes import uia
            is_pwd = uia.focused_is_password()
            if is_pwd != self._shy_now:
                self._shy_changed.emit(is_pwd)
        except Exception:
            pass
        finally:
            self._shy_checking = False

    @Slot(bool)
    def _on_shy_changed(self, shy: bool) -> None:
        self._shy_now = shy
        self._pet.set_shy(shy)
        if shy:
            now = time.time()
            if now - self._shy_last_pop > _SHY_POP_COOLDOWN_S:
                self._shy_last_pop = now
                self._feed_pop(i18n.t("pwd_shy"))

    def _check_vitals(self) -> None:
        """十秒一次读机器体征 后台线程采"""
        if self._vitals_busy:
            return
        self._vitals_busy = True
        threading.Thread(target=self._vitals_thread, daemon=True).start()

    def _vitals_thread(self) -> None:
        try:
            import psutil
            cpu = psutil.cpu_percent(None)
            mem = psutil.virtual_memory().percent
            b = psutil.sensors_battery()
            batt = (b.percent, b.power_plugged) if b is not None else None
            self._vitals_ready.emit({"cpu": cpu, "mem": mem, "batt": batt})
        except Exception:
            pass
        finally:
            self._vitals_busy = False

    @Slot(object)
    def _on_vitals(self, v: dict) -> None:
        """体征状态机 拟态进退都带迟滞"""
        if not self._pet.isVisible():
            return
        now = time.time()
        cpu, mem, batt = v["cpu"], v["mem"], v["batt"]
        # cpu高烧 连续两次85进 70退
        self._cpu_high_n = self._cpu_high_n + 1 if cpu >= 85 else 0
        if not self._hot_on and self._cpu_high_n >= 2:
            self._hot_on = True
            self._pet.set_hot(True)
            somatic.set_state("hot", agent_prompts.SOMA_HOT_STATE)
            if now - self._hot_last_pop > _HOT_POP_COOLDOWN_S:
                self._hot_last_pop = now
                self._feed_pop(i18n.t("hot_cpu"))
        elif self._hot_on and cpu < 70:
            self._hot_on = False
            self._pet.set_hot(False)
            somatic.set_state("hot", None)
        # 内存挤压 88进 80退 95再喊
        if not self._squeeze_on and mem >= 88:
            self._squeeze_on = True
            self._pet.set_squeeze(True)
        elif self._squeeze_on and mem < 80:
            self._squeeze_on = False
            self._pet.set_squeeze(False)
        if self._squeeze_on and mem >= 95 and now - self._mem_last_pop > _MEM_POP_COOLDOWN_S:
            self._mem_last_pop = now
            self._feed_pop(i18n.t("mem_full"))
        # 低电量 20进 25或插电退
        if batt is not None:
            pct, plugged = batt
            if not self._lowbatt_on and pct <= 20 and not plugged:
                self._lowbatt_on = True
                self._pet.set_low_batt(True)
                self._feed_pop(i18n.t("low_batt").format(pct=int(pct)))
            elif self._lowbatt_on and (pct >= 25 or plugged):
                self._lowbatt_on = False
                self._pet.set_low_batt(False)
        # 深夜盖被子 23点半到凌晨5点
        dt_now = datetime.now()
        late = (dt_now.hour == 23 and dt_now.minute >= 30) or dt_now.hour < 5
        if late and not self._blanket_on:
            self._blanket_on = True
            self._pet.set_blanket(True)
            today = dt_now.date().isoformat()
            if self._late_popped_date != today and presence.idle_seconds() < _AWAY_S:
                self._late_popped_date = today
                streak = stats.mark_late_night()
                self._pet.react("yawn")
                if streak >= 3:
                    self._feed_pop(i18n.t("late_night_streak").format(n=streak))
                else:
                    self._feed_pop(i18n.t("late_night"))
        elif not late and self._blanket_on:
            self._blanket_on = False
            self._pet.set_blanket(False)
        # 冬天机器发热 凑过去蹭暖
        warm_month = dt_now.month in (12, 1, 2)
        self._cpu_warm_n = self._cpu_warm_n + 1 if cpu >= 55 else 0
        if (warm_month and self._cpu_warm_n >= 3 and not self._hot_on
                and now - self._snuggle_last > _SNUGGLE_COOLDOWN_S
                and not self._engaged() and not self._pet.is_asleep):
            self._snuggle_last = now
            self._pet.react("snuggle")
            self._feed_pop(i18n.t("snuggle_warm"))
        # 机器真闲了五分钟 拿毛线球出来玩
        self._cpu_idle_n = self._cpu_idle_n + 1 if cpu < 15 else 0
        if (self._cpu_idle_n >= 30 and now - getattr(self, "_yarn_last", 0.0) > 7200
                and not self._engaged() and not self._pet.is_asleep):
            self._yarn_last = now
            self._cpu_idle_n = 0
            self._pet.perform("yarn")

    def _check_downloads(self) -> None:
        """盯下载目录 新文件落地就提一嘴"""
        if self._dl_busy or self._meeting_mode or not self._pet.isVisible():
            return
        self._dl_busy = True
        threading.Thread(target=self._dl_thread, daemon=True).start()

    def _dl_thread(self) -> None:
        try:
            folder = Path.home() / "Downloads"
            if not folder.is_dir():
                return
            now = time.time()
            for p in folder.iterdir():
                try:
                    if not p.is_file() or p.suffix.lower() in (".crdownload", ".part", ".tmp", ".download"):
                        continue
                    st = p.stat()
                    # 启动之后新出现的 且写完稳定了几秒
                    if st.st_mtime > self._dl_baseline and 4 < now - st.st_mtime < 120 and p.name not in self._dl_seen:
                        self._dl_seen.add(p.name)
                        self._dl_found.emit(p.name)
                        return
                except OSError:
                    continue
        except Exception:
            pass
        finally:
            self._dl_busy = False

    @Slot(str)
    def _on_dl_found(self, name: str) -> None:
        self._pet.react("perk_up")
        self._feed_pop(i18n.t("dl_done").format(name=name[:36]))

    def _check_mic(self) -> None:
        """读注册表看麦克风是否被占用 开会自动安静"""
        if self._mic_busy:
            return
        self._mic_busy = True
        threading.Thread(target=self._mic_thread, daemon=True).start()

    def _mic_thread(self) -> None:
        try:
            import winreg
            in_use = False
            base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged"
            try:
                root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
            except OSError:
                root = None
            if root is not None:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            stop, _ = winreg.QueryValueEx(k, "LastUsedTimeStop")
                            if int(stop) == 0:  # 还没停 = 正在用
                                in_use = True
                                break
                    except OSError:
                        continue
                winreg.CloseKey(root)
            if in_use != self._meeting_mode:
                self._mic_changed.emit(in_use)
        except Exception:
            pass
        finally:
            self._mic_busy = False

    @Slot(bool)
    def _on_mic_changed(self, in_use: bool) -> None:
        if in_use and not self._meeting_mode:
            self._thought.pop(i18n.t("meeting_on"), self._pet)  # 进静音前最后说一句
            self._meeting_mode = True
            somatic.set_state("meeting", agent_prompts.SOMA_MEETING_STATE)
        elif not in_use and self._meeting_mode:
            self._meeting_mode = False
            somatic.set_state("meeting", None)
            self._thought.pop(i18n.t("meeting_off"), self._pet)

    def _check_desktop(self) -> None:
        """桌面图标太多了 让agent提议收拾"""
        if self._desk_busy or self._meeting_mode:
            return
        self._desk_busy = True
        threading.Thread(target=self._desk_thread, daemon=True).start()

    def _desk_thread(self) -> None:
        try:
            desk = Path.home() / "Desktop"
            if not desk.is_dir():
                return
            n = sum(1 for p in desk.iterdir() if p.is_file() and p.suffix.lower() != ".lnk")
            if n >= _DESK_LIMIT:
                today = datetime.now().date().isoformat()
                if stats.get_note("desk_tidy") != today:
                    stats.set_note("desk_tidy", today)
                    self._desk_crowded.emit(n)
        except Exception:
            pass
        finally:
            self._desk_busy = False

    @Slot(int)
    def _on_desk_crowded(self, n: int) -> None:
        if self._worker.is_running:
            return
        self.request_message.emit(agent_prompts.DESK_TIDY_MSG.format(n=n))

    def _on_pet_moved_paws(self) -> None:
        """走动时心情好就留脚印 节日换花样"""
        try:
            _val, _aro, _r = emotion.snapshot()
            if _val < 0.25:
                return
            pos = self._pet.frameGeometry().center()
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
            self._paws.add(pos.x(), pos.y() + self._pet.height() // 4, heading, kind)
        except Exception:
            pass

    def _maybe_hide_seek(self) -> bool:
        """偶尔藏起来让用户找 一天最多一次"""
        if not self._settings.proactive_enabled or self._meeting_mode:
            return False
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep or self._tail is not None:
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
        self._feed_pop(i18n.t("hs_start"))
        QTimer.singleShot(1500, self._hs_hide)
        return True

    def _hs_hide(self) -> None:
        from desktop_pet.pet.hideseek import TailWindow
        from desktop_pet.eyes import capture
        if self._tail is not None or not self._pet.isVisible():
            return
        scr = self._app.primaryScreen().availableGeometry()
        x = random.randint(scr.left() + 120, scr.right() - 120)
        y = random.randint(scr.top() + 160, scr.bottom() - 120)
        tail = TailWindow()
        capture.register_own_window(int(tail.winId()))
        tail.found.connect(self._hs_found)
        tail.gave_up.connect(self._hs_gave_up)
        self._pet.setVisible(False)
        tail.appear_at(x, y)
        self._tail = tail

    def _hs_reveal(self, near: "QPoint | None") -> None:
        if near is not None:
            scr = self._app.primaryScreen().availableGeometry()
            nx = max(scr.left(), min(near.x() - self._pet.width() // 2, scr.right() - self._pet.width()))
            ny = max(scr.top(), min(near.y() - self._pet.height() // 2, scr.bottom() - self._pet.height()))
            self._pet.move(nx, ny)
        self._pet.setVisible(True)
        self._pet.wake()

    @Slot()
    def _hs_found(self) -> None:
        tail, self._tail = self._tail, None
        pos = tail.pos() if tail is not None else None
        self._hs_reveal(pos)
        self._pet.react("celebrate")
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        somatic.note(agent_prompts.SOMA_HS_FOUND)
        self._feed_pop(i18n.t("hs_found"))

    @Slot()
    def _hs_gave_up(self) -> None:
        self._tail = None
        self._hs_reveal(None)
        self._feed_pop(i18n.t("hs_giveup"))

    def _hs_abort(self) -> None:
        """藏着的时候被召唤就直接现身"""
        if self._tail is not None:
            self._tail.stop()
            self._tail = None
            self._hs_reveal(None)

    def _check_weather(self) -> None:
        """两小时问一次天气 拟态跟着换"""
        if self._weather_busy or not self._settings.allow_web:
            return
        self._weather_busy = True
        threading.Thread(target=self._weather_thread, daemon=True).start()

    def _weather_thread(self) -> None:
        try:
            from desktop_pet.settings import build_http_client
            client = build_http_client(self._settings.proxy)
            r = client.get("https://wttr.in/?format=j1", timeout=15)
            cur = r.json()["current_condition"][0]
            temp = float(cur.get("temp_C", 20))
            precip = float(cur.get("precipMM", 0) or 0)
            kind = ""
            if temp >= 33:
                kind = "melt"
            elif precip > 0.1:
                kind = "snow" if temp <= 2 else "rain"
            self._weather_ready.emit(kind)
        except Exception:
            pass
        finally:
            self._weather_busy = False

    @Slot(str)
    def _on_weather(self, kind: str) -> None:
        if kind == self._weather_kind:
            return
        self._weather_kind = kind
        self._pet.set_weather(kind)
        somatic.set_state("weather", agent_prompts.SOMA_WEATHER.get(kind))
        if kind:
            self._feed_pop(i18n.t("weather_" + kind))

    def _on_activity_done(self, name: str) -> None:
        """小品演完的彩蛋 钓鱼有渔获"""
        if name != "fish":
            return
        catch = ""
        try:
            if self._clip_treasures and random.random() < 0.5:
                _k, text, _ts = random.choice(list(self._clip_treasures))
                catch = text.strip().replace("\n", " ")[:46]
            else:
                today_lines = [str(it.get("text", "")) for it in journal.recent(6)]
                if today_lines:
                    catch = random.choice(today_lines)[:46]
        except Exception:
            pass
        if catch:
            QTimer.singleShot(1200, lambda: self._feed_pop(i18n.t("fish_catch").format(thing=catch)))

    def _throw_ball(self) -> None:
        """丢颗球给它玩"""
        if self._ball is not None or not self._pet.isVisible() or self._pet.is_asleep:
            return
        from desktop_pet.pet.ball import BallWindow
        from desktop_pet.eyes import capture
        ball = BallWindow()
        capture.register_own_window(int(ball.winId()))
        ball.caught.connect(self._on_ball_caught)
        ball.stopped.connect(self._on_ball_stopped)
        scr = self._app.primaryScreen().availableGeometry()
        ball.throw_from_top(scr, self._pet.frameGeometry())
        self._ball = ball
        self._pet.react("perk_up")

    @Slot()
    def _on_ball_caught(self) -> None:
        self._ball = None
        self._pet.react("jump_spin")
        emotion.apply("praised")
        selector.set_emotion(*emotion.snapshot())
        somatic.note(agent_prompts.SOMA_BALL)
        QTimer.singleShot(900, lambda: self._feed_pop(i18n.t("ball_caught")))

    @Slot()
    def _on_ball_stopped(self) -> None:
        self._ball = None
        self._pet.react("peek")

    def _maybe_perch(self) -> bool:
        """偶尔跳上前台窗口顶上待着 窗口一动摔下来"""
        if not self._settings.proactive_enabled or self._meeting_mode or self._perch_hwnd:
            return False
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep or self._tail is not None:
            return False
        now = time.time()
        if now - self._perch_last < 7200 or random.random() > 0.15:
            return False
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or hwnd == int(self._pet.winId()):
                return False
            left, top, right, _bottom = win32gui.GetWindowRect(hwnd)
            scr = self._app.primaryScreen().availableGeometry()
            if right - left < 500 or top < scr.top() + self._pet.height() * 0.8:
                return False
            self._perch_last = now
            self._perch_hwnd = hwnd
            self._perch_rect = (left, top, right)
            x = left + int((right - left) * 0.30) - self._pet.width() // 2
            y = top - int(self._pet.height() * 0.72)
            self._pet.move(x, y)
            self._pet.react("peek")
            self._feed_pop(i18n.t("perch_up"))
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
        self._pet._start_toss(random.uniform(-120, 120), 60.0)
        QTimer.singleShot(1400, lambda: self._pet.react("puff_up"))
        QTimer.singleShot(1700, lambda: self._feed_pop(i18n.t("perch_fall")))

    def _perch_done(self) -> None:
        if not self._perch_hwnd:
            return
        self._perch_hwnd = 0
        self._perch_timer.stop()
        self._pet.react("stretch")

    def _toggle_focus(self) -> None:
        """番茄钟 开一轮或提前结束"""
        if time.time() < self._focus_until:
            self._focus_timer.stop()
            self._focus_until = 0.0
            somatic.set_state("focus", None)
            self._feed_pop(i18n.t("focus_cancel"))
            return
        self._focus_until = time.time() + _FOCUS_MINUTES * 60
        self._focus_timer.start(_FOCUS_MINUTES * 60 * 1000)
        self._pet.perform("read")
        somatic.set_state("focus", agent_prompts.SOMA_FOCUS_STATE)
        self._feed_pop(i18n.t("focus_start").format(m=_FOCUS_MINUTES))

    def _end_focus(self) -> None:
        if self._focus_until <= 0:
            return
        self._focus_until = 0.0
        somatic.set_state("focus", None)
        somatic.note(agent_prompts.SOMA_FOCUS_DONE)
        self._pet.react("celebrate")
        emotion.apply("task_done")
        selector.set_emotion(*emotion.snapshot())
        self._feed_pop(i18n.t("focus_done").format(m=_FOCUS_MINUTES))

    def _check_bugs(self) -> None:
        """定时扫temp 垃圾堆大了生一只虫"""
        if self._bug is not None or self._bug_scanning:
            return
        if not self._settings.proactive_enabled:
            return
        if self._engaged() or not self._pet.isVisible() or self._pet.is_asleep:
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
        if self._bug is not None or not self._pet.isVisible():
            return
        from desktop_pet.pet.bug import BugWindow
        from desktop_pet.eyes import capture
        bug = BugWindow()
        capture.register_own_window(int(bug.winId()))
        bug.squished.connect(self._on_bug_squished)
        bug.escaped.connect(self._on_bug_escaped)
        geo = self._pet.frameGeometry()
        screen = self._app.primaryScreen().availableGeometry()
        side = 1 if geo.center().x() < screen.center().x() else -1
        bug.spawn_near(geo.center().x() + side * (geo.width() // 2 + 70),
                       min(geo.bottom() + 10, screen.bottom() - 80), screen)
        self._bug = bug
        self._pet.react("double_take")
        self._feed_pop(i18n.t("bug_spotted").format(size=feeding.human_size(size)))

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
            self._feed_pop(i18n.t("bug_nothing"))
            return
        stats.add_eaten(freed, 0)  # 算它吃的 但不算文件投喂数
        emotion.apply("fed")
        selector.set_emotion(*emotion.snapshot())
        self._pet.react("celebrate")
        somatic.note(agent_prompts.SOMA_BUG.format(n=count, size=feeding.human_size(freed)))
        self._feed_pop(i18n.t("bug_squished_msg").format(n=count, size=feeding.human_size(freed)))

    @Slot()
    def _on_bug_escaped(self) -> None:
        self._bug = None

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
                self._pet.react("celebrate")
                self._feed_pop(i18n.t("bgwatch_ok").format(id=t["id"]))
                emotion.apply("task_done")
                selector.set_emotion(*emotion.snapshot())
            else:
                self._pet.react("droop")
                self._feed_pop(i18n.t("bgwatch_fail").format(id=t["id"], code=t["returncode"]))
                if not self._worker.is_running:
                    self.request_message.emit(agent_prompts.BGWATCH_ANALYZE_MSG.format(
                        id=t["id"], command=t["command"][:80], code=t["returncode"],
                        tail=t["tail"][-1200:]))

    @Slot(bool)
    def _on_busy(self, busy: bool) -> None:
        self._busy = busy
        self._pet.set_busy(busy)
        if busy:
            self._cancelling = False
            self._wake()
            self._media.dismiss()
            self._pet.set_think_energy(emotion.snapshot()[1])
            self._think.start(self._pet)
        else:
            self._think.stop()
            self._todo.dismiss()
            self._timed_inflight = False
            if not self._cancelling:   # 取消态不清 _inflight_timed 留给requeue
                self._inflight_timed = None
            self._drain_pending_bg()
            self._drain_timed()

    @Slot(bool)
    def _on_task_finished(self, ok: bool) -> None:
        try:
            emotion.apply("task_done" if ok else "task_failed")
        except Exception:
            pass
        selector.set_emotion(*emotion.snapshot())
        if not self._lecturing and not self._pet.is_reacting:
            if not ok:
                self._pet.slump()
            elif random.random() < _CELEBRATE_CHANCE:
                self._pet.celebrate()

    @Slot()
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

    @Slot()
    def _check_reminders(self) -> None:
        try:
            self._drain_reminders()
        except Exception:
            pass

    @Slot()
    def _check_inbox(self) -> None:
        if not self._settings.remote_inbox or self._inbox_inflight:
            return
        self._inbox_inflight = True

        def work() -> None:
            try:
                actions = remote_inbox.poll()
            except Exception:
                actions = []
            for kind, content in actions:
                self._remote_action.emit(kind, content)
            self._inbox_inflight = False
        threading.Thread(target=work, daemon=True, name="mochi-inbox").start()

    @Slot(str, str)
    def _on_remote_action(self, kind: str, content: str) -> None:
        if kind == "task":
            self._timed_queue.append(content)
            self._drain_timed()
        elif kind == "say":
            if not self._shown or not self._pet.isVisible() or self._foreground_is_fullscreen():
                self._tray.notify(i18n.t("tray_tooltip"), content)
            else:
                self._pet.wake()
                self.request_reminder.emit(content)

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

    @Slot()
    def _check_proactive(self) -> None:
        try:
            if self._meeting_mode:
                return  # 开会不主动出声
            if self._maybe_peek():
                return
            if self._maybe_occasion():
                return
            if self._maybe_hide_seek():
                return
            if self._maybe_perch():
                return
            if self._maybe_giveback():
                return
            self._maybe_speak_up()
        except Exception:
            pass

    def _maybe_giveback(self) -> bool:
        """亲密度够了 把几小时前帮用户收着的剪贴宝贝拿出来提一嘴"""
        if not self._settings.proactive_enabled or not self._clip_treasures:
            return False
        if self._worker.is_running or self._engaged() or not self._pet.isVisible() or self._pet.is_asleep:
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
        self._pet.set_pendant(len(self._clip_treasures))
        self._last_giveback = now
        snippet = text.strip().replace("\n", " ")[:60]
        self._pet.react("peek")
        self.request_message.emit(agent_prompts.GIVEBACK_MSG.format(
            hours=f"{age_h:.0f}", kind=kind, snippet=snippet))
        return True

    @Slot()
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

    @Slot()
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

    @Slot(str)
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
            self.request_proactive.emit("welcome_back", context)
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

    def _wake(self) -> None:
        self._pet.wake()

    @Slot()
    def _on_hide(self) -> None:
        self._cancel_active_task(notify=False)
        self._input.fade_out()
        self._speech.interrupt()
        voice.flush()
        self._reset_lecture()
        self._think.stop()
        self._media.dismiss()
        self._todo.dismiss()

    @Slot()
    def _follow(self) -> None:
        if self._speech.isVisible():
            self._speech.place_below(self._pet)
        if self._input.isVisible():
            self._input.place_below(self._pet)
        if self._think.isVisible():
            self._think.follow(self._pet)
        if self._thought.isVisible():
            self._thought.follow(self._pet)
        screen = self._app.primaryScreen().availableGeometry()
        if self._board.isVisible():
            self._board.follow(self._pet, screen)
        if self._todo.isVisible():
            self._todo.follow(self._pet, screen)
        if self._media.isVisible():
            self._media.follow(self._pet, screen)
        if self._confirm_box.is_open():
            self._confirm_box.follow(self._pet, screen)

    def _status_snapshot(self) -> dict:
        """控制面板主页状态快照"""
        _val, _aro, rapport = emotion.snapshot()
        if self._worker.is_running or self._busy:
            state = "busy"
        elif not self._pet.isVisible():
            state = "hidden"
        elif self._pet.is_asleep:
            state = "asleep"
        else:
            state = "idle"

        def _safe(fn):
            try:
                return fn()
            except Exception:
                return 0

        try:
            p_count, p_cap = proactive.today(datetime.now(), self._settings.proactive_level)
        except Exception:
            p_count, p_cap = 0, 0
        return {
            "shown": self._shown,
            "state": state,
            "mood": emotion.animation_state(),
            "rapport": rapport,
            "experiences": _safe(store.count),
            "docs": _safe(docs.count),
            "journal": _safe(journal.count),
            "skills": _safe(skills.count),
            "proactive_today": p_count,
            "proactive_cap": p_cap,
            "model": self._settings.model,
            "configured": self._settings.is_configured,
        }

    def _bring_online(self) -> None:
        """桌宠上线 首次播入场动画 之后只显示唤醒"""
        if not self._pet.isVisible():
            self._pet.setVisible(True)
        if not self._entered:
            self._entered = True
            cursor_screen = self._app.screenAt(QCursor.pos()) or self._app.primaryScreen()
            screen = cursor_screen.availableGeometry()
            rest = QPoint(
                screen.right() - self._pet.width() - _PET_MARGIN,
                screen.bottom() - self._pet.height() - _PET_MARGIN,
            )
            self._pet.move(rest)
            self._pet.show()
            self._pet.play_entrance(next_entrance_kind(), rest, screen)
            QTimer.singleShot(5200, self._morning_ritual)
        else:
            self._pet.wake()

    def _morning_ritual(self) -> None:
        """每天第一次见面 起床气加心情预报 纪念日端蛋糕"""
        today = datetime.now().date().isoformat()
        if stats.get_note("forecast") != today:
            stats.set_note("forecast", today)
            self._pet.react("yawn")
            val, _aro, rapport = emotion.snapshot()
            if val >= 0.25:
                key = "forecast_sunny"
            elif val >= -0.15:
                key = "forecast_cloudy"
            else:
                key = "forecast_rain"
            text = i18n.t(key)
            if rapport >= 0.6:
                text += i18n.t("forecast_close_suffix")
            QTimer.singleShot(1800, lambda: self._feed_pop(text))
        # 纪念日
        days = stats.snapshot()["days"]
        milestone = days in (7, 30, 100, 200, 520) or (days > 0 and days % 365 == 0)
        if milestone and stats.get_note("cake") != today:
            stats.set_note("cake", today)
            self._cake_on = True
            somatic.note(agent_prompts.SOMA_CAKE_OUT.format(days=days))
            QTimer.singleShot(4200, lambda: (
                self._pet.set_cake(True),
                self._feed_pop(i18n.t("cake_day").format(days=days)),
            ))
            QTimer.singleShot(10 * 60 * 1000, self._cake_timeout)

    def _cake_timeout(self) -> None:
        if getattr(self, "_cake_on", False):
            self._cake_on = False
            self._pet.set_cake(False)

    def _on_pet_clicked_cake(self) -> None:
        """点宠物时蛋糕亮着就是吹蜡烛"""
        if not getattr(self, "_cake_on", False):
            return
        if self._pet.blow_cake():
            self._cake_on = False
            emotion.apply("praised")
            selector.set_emotion(*emotion.snapshot())
            somatic.note(agent_prompts.SOMA_CAKE_BLOWN)
            QTimer.singleShot(900, lambda: self._pet.react("celebrate"))
            QTimer.singleShot(1100, lambda: self._feed_pop(i18n.t("cake_blow")))
            QTimer.singleShot(2600, lambda: self._pet.set_cake(False))

    def _bond_snapshot(self) -> dict:
        """控制面板羁绊页快照"""
        _val, _aro, rapport = emotion.snapshot()
        st = stats.snapshot()

        def _safe(fn, default):
            try:
                return fn()
            except Exception:
                return default

        return {
            "persona": persona.get(),
            "preferences": _safe(store.profile_items, []),
            "experiences": _safe(lambda: store.recent_experiences(10), []),
            "env": _safe(store.env_items, []),
            "skills": _safe(skills.count, 0),
            "rapport": rapport,
            "days": st["days"],
            "interactions": st["interactions"],
            "files_eaten": st.get("files_eaten", 0),
            "eaten_human": feeding.human_size(st.get("bytes_eaten", 0)),
        }

    def _toggle_power(self) -> None:
        if self._shown:
            self._power_off()
        else:
            self._power_on()

    def _power_on(self) -> None:
        """开机显示桌宠"""
        if self._shown:
            return
        self._shown = True
        self._cancelling = False
        self._bring_online()
        emotion.apply("returned")
        selector.set_emotion(*emotion.snapshot())
        self._just_returned = True
        self._drain_reminders()

    def _power_off(self) -> None:
        """关机收起桌宠和所有浮层 程序留在后台"""
        if not self._shown:
            return
        self._shown = False
        self._cancelling = True
        self._worker.cancel()
        self._confirm_result = False
        self._confirm_event.set()
        self._confirm_box.close_box()
        self._speech.interrupt()
        voice.flush()
        self._reset_lecture()
        self._media.dismiss()
        self._todo.dismiss()
        self._input.fade_out()
        self._pending_bg.clear()
        self._requeue_timed()
        self._on_busy(False)
        self._pet.clear_pending()
        radar.reset()
        self._pet.setVisible(False)

    def _open_panel(self) -> None:
        if self._panel is not None:
            self._panel.raise_()
            self._panel.activateWindow()
            return
        self._relang = False
        self._panel = ControlPanel(
            self._settings,
            on_reset=self._reset_all,
            on_apply=self._apply_settings_live,
            status_provider=self._status_snapshot,
            on_toggle_active=self._toggle_power,
            bond_provider=self._bond_snapshot,
            on_set_language=self._set_language,
            hotkey_status_provider=self._hotkey_status_snapshot,
            on_preview_voice=self._preview_voice,
            on_new_topic=self._new_topic,
            intro=self._relang_intro,
        )
        self._relang_intro = None
        self._panel.setModal(False)   # 非模态 面板开着也能操作桌宠
        self._panel.finished.connect(self._on_panel_closed)
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def _on_panel_closed(self, _result: int = 0) -> None:
        self._panel = None
        if self._pending_quit:
            self._do_quit()
            return
        if self._relang:               # 切语言后用新语言重建面板
            self._relang = False
            QTimer.singleShot(0, self._open_panel)

    def _set_language(self, lang: str) -> None:
        self._settings.ui_language = lang
        self._settings.save()
        i18n.set_language(lang)
        self._tray.retranslate()
        self._relang = True
        if self._panel is not None:
            self._relang_intro = self._panel.snapshot_for_transition()
            self._panel.accept()

    def _preview_voice(self, voice_id: str, rate: int) -> None:
        voice.preview(i18n.t("tts_sample"), voice_id, rate)

    def _apply_settings_live(self) -> None:
        i18n.set_language(self._settings.ui_language)
        self._tray.retranslate()
        voice.set_voice(self._settings.tts_voice)
        voice.set_rate(self._settings.tts_rate)
        voice.set_enabled(self._settings.tts_enabled)
        sampler.set_enabled(self._settings.clip_sampler or self._settings.clip_alchemy)
        if self._settings.remote_inbox:
            remote_inbox.ensure_dir()
        self._hotkeys.restart({
            "summon": self._settings.hotkey_summon,
            "ask": self._settings.hotkey_ask,
            "quick": self._settings.hotkey_quick,
        })
        if self._input.isVisible():
            self._input.setPlaceholderText(i18n.t("input_placeholder"))

    def _new_topic(self) -> None:
        if self._busy or self._worker.is_running:
            self._worker.cancel()
        self._worker.new_topic()
        self._speech.interrupt()
        self._todo.dismiss()
        self._reset_lecture()

    def _reset_all(self) -> None:
        if self._busy or self._worker.is_running:
            self._worker.cancel()
        self._worker.forget_all()
        emotion.reset()
        reminders.clear()
        stats.clear()
        selector.set_emotion(*emotion.snapshot())
        self._pet.express("neutral")

    def _quit(self) -> None:
        if self._pending_quit:
            return
        self._pending_quit = True
        try:
            self._tray.hide()
        except Exception:
            pass
        if self._panel is not None:
            try:
                self._panel.reject()
            except Exception:
                pass
            return
        self._do_quit()

    def _do_quit(self) -> None:
        if self._entered and self._pet.isVisible() and not getattr(self, "_farewell_done", False):
            # 走之前挥个手说晚安 再真正退
            self._farewell_done = True
            self._pet.react("wave")
            line = ""
            try:
                today = datetime.now().date().isoformat()
                for it in reversed(journal.recent(6)):
                    if str(it.get("ts", "")).startswith(today):
                        line = str(it.get("text", ""))[:42]
                        break
            except Exception:
                pass
            self._feed_pop(i18n.t("bye_with_note").format(note=line) if line else i18n.t("bye_plain"))
            QTimer.singleShot(1700, self._do_quit)
            return
        for _t in (self._presence_timer, self._reminder_timer, self._proactive_timer,
                   self._watch_timer, self._remote_timer):
            try:
                _t.stop()
            except Exception:
                pass
        self._hotkeys.stop()
        try:
            voice.shutdown()
        except Exception:
            pass
        if self._worker.is_running:
            self._worker.cancel()
        self._confirm_event.set()
        try:
            from desktop_pet.agent.bgtasks import bg_tasks
            for _tid, _task, _secs in bg_tasks.snapshot():
                bg_tasks.stop(_tid)
        except Exception:
            pass
        self._worker.shutdown()
        try:
            mcp_hub.shutdown()
        except Exception:
            pass
        self._thread.quit()
        self._thread.wait(3000)
        self._app.quit()
        # 正常quit卡死时兜底硬杀
        try:
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(ctypes.windll.kernel32.GetCurrentProcess(), 0)
        except Exception:
            pass
        os._exit(0)

    def run(self) -> int:
        stats.mark_first_seen()
        voice.set_voice(self._settings.tts_voice)
        voice.set_rate(self._settings.tts_rate)
        voice.set_enabled(self._settings.tts_enabled)
        self._pet.express("neutral")
        self._thread.start()
        self._tray.show()
        self._presence_timer.start(_PRESENCE_POLL_MS)
        self._reminder_timer.start(_REMINDER_POLL_MS)
        self._proactive_timer.start(_PROACTIVE_POLL_MS)
        self._watch_timer.start(_WATCH_POLL_MS)
        self._remote_timer.start(_REMOTE_POLL_MS)
        self._bgwatch_timer.start(_BGWATCH_POLL_MS)
        self._bug_timer.start(_BUG_SCAN_MS)
        self._shy_timer.start(_SHY_POLL_MS)
        self._vitals_timer.start(_VITALS_POLL_MS)
        self._dl_timer.start(_DL_POLL_MS)
        self._mic_timer.start(_MIC_POLL_MS)
        self._desk_timer.start(_DESK_POLL_MS)
        self._weather_timer.start(2 * 3600 * 1000)
        if self._settings.remote_inbox:
            remote_inbox.ensure_dir()
        self._hotkeys.start()
        from desktop_pet.executor import vision
        vision.prewarm()
        self._open_panel()
        return self._app.exec()
