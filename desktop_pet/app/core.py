# author: bdth
# email: 2074055628@qq.com
# 桌宠主控 装配ui agent线程和各类定时器

from __future__ import annotations

import sys
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from desktop_pet import hearing, i18n, stats
from desktop_pet.app.agent_bridge import AgentBridgeMixin
from desktop_pet.app.autonomy import AutonomyMixin
from desktop_pet.app.lifecycle import LifecycleMixin
from desktop_pet.app.qtenv import _install_qt_message_filter, _light_palette
from desktop_pet.app.quick_actions import QuickActionsMixin
from desktop_pet.app.voice import VoiceMixin
from desktop_pet.app.worker import AgentWorker
from desktop_pet.clipsampler import sampler
from desktop_pet.companions.dreams import Dreams
from desktop_pet.companions.feeding_ctrl import FeedingCtrl
from desktop_pet.companions.playtime import Playtime
from desktop_pet.companions.rituals import Rituals
from desktop_pet.companions.sensors import Sensors
from desktop_pet.companions.watchers import Watchers
from desktop_pet.companions.wellbeing import Wellbeing
from desktop_pet.emotion.state import emotion
from desktop_pet.hotkeys import GlobalHotkeys
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.blackboard import BlackBoard
from desktop_pet.pet.chat import InputBox, SpeechText, ThoughtBubble, ThoughtBubbles
from desktop_pet.pet.confirm import ConfirmBox
from desktop_pet.pet.control_hint import ControlHint
from desktop_pet.pet.media import MediaFrame
from desktop_pet.pet.todo_board import TodoBoard
from desktop_pet.pet.tray import Tray
from desktop_pet.pet.window import PetWindow
from desktop_pet.settings import Settings


_PRESENCE_POLL_MS = 12_000
_REMINDER_POLL_MS = 15_000
_PROACTIVE_POLL_MS = 60_000
_WATCH_POLL_MS = 15_000


class PetApp(QuickActionsMixin, VoiceMixin, AgentBridgeMixin,
             AutonomyMixin, LifecycleMixin, QObject):
    request_reminder = Signal(str)
    request_task = Signal(str)
    request_timed_task = Signal(str)
    request_proactive = Signal(str, str)
    request_explore = Signal(str)
    request_peek = Signal(str)
    request_analyze = Signal(str)
    request_dream = Signal()
    request_consolidate = Signal()
    request_message = Signal(str)
    request_confirm = Signal(str)
    request_rewrite = Signal(str)
    request_clip_alchemy = Signal(str, str)
    _hear_partial = Signal(str)
    _hear_final = Signal(str)
    _hear_state = Signal(str)
    _hear_submit = Signal(str, object)  # 语音定稿走信号进worker线程 直调会把llm请求卡在ui线程
    _hear_tick = Signal(float)

    def __init__(self) -> None:
        _install_qt_message_filter()
        self._app = QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._app.setPalette(_light_palette())
        self._app.setQuitOnLastWindowClosed(False)
        from desktop_pet.pet.fx import smooth_font
        self._app.setFont(smooth_font(QFont("Microsoft YaHei UI", 10)))
        from desktop_pet.pet.icon import mochi_icon
        self._app.setWindowIcon(mochi_icon())
        super().__init__()

        self._busy = False
        self._shown = False
        self._entered = False
        self._panel = None
        self._relang = False
        self._relang_intro = None
        self._fired_occasions: set[str] = set()
        self._last_peek: datetime | None = None
        self._watch_inflight = False
        self._cancelling = False
        self._pending_quit = False
        self._pending_bg: list[tuple[str, str]] = []
        self._timed_queue: list[str] = []
        self._timed_inflight = False
        self._inflight_timed: str | None = None
        self._confirm_event = threading.Event()
        self._confirm_result = False
        self._confirm_pending = False

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
        self._thought = ThoughtBubble()
        self._think = ThoughtBubbles()
        self._control_hint = ControlHint()
        # 操作浮层延迟收起 连续操作不闪 单次操作也留够时间让你看见
        self._control_hide_timer = QTimer(self)
        self._control_hide_timer.setSingleShot(True)
        self._control_hide_timer.timeout.connect(self._control_hint.hide_hint)

        from desktop_pet.eyes import capture
        for _w in (self._pet, self._speech, self._input, self._board, self._todo, self._media,
                   self._confirm_box, self._thought, self._think, self._control_hint):
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
        self._meeting_mode = False
        self._shot_last = 0.0
        self._just_returned = False

        self._feeding = FeedingCtrl(self)
        self._sensors = Sensors(self)
        self._playtime = Playtime(self)
        self._watchers = Watchers(self)
        self._rituals = Rituals(self)
        self._wellbeing = Wellbeing(self)
        self._dreams = Dreams(self)

        self._tray = Tray(
            on_open_panel=self._open_panel,
            on_quit=self._quit,
            on_talk=self._summon,
            on_peek=self._peek_now,
            on_new_topic=self._new_topic,
            on_toggle_show=self._toggle_power,
            is_shown=lambda: self._shown,
            on_focus=self._rituals.toggle_focus,
            on_ball=self._playtime.throw_ball,
            on_perform=self._on_perform,
        )
        self._hotkeys = GlobalHotkeys({
            "summon": self._settings.hotkey_summon,
            "ask": self._settings.hotkey_ask,
            "quick": self._settings.hotkey_quick,
            "talk": self._settings.hotkey_talk,
        })
        self._hotkey_status: dict = {}
        # 听写浮条和按住说话的松键轮询
        from desktop_pet.pet.hear_ui import HearBar
        self._hearbar = HearBar()
        self._hear_got_final = False
        self._talk_release_timer = QTimer(self)
        self._talk_release_timer.setInterval(50)
        self._talk_release_timer.timeout.connect(self._poll_talk_release)
        hearing.cb_partial = self._hear_partial.emit
        hearing.cb_final = self._hear_final.emit
        hearing.cb_state = self._hear_state.emit
        hearing.cb_tick = self._hear_tick.emit
        # 思考执行中或关机隐藏时 热键和唤醒词都无视 hearing线程会来问
        hearing.cb_busy = lambda: self._busy or self._worker.is_running or not self._shown
        # 开会时只屏蔽唤醒词 热键是用户主动按的仍然放行
        hearing.cb_wake_block = lambda: self._meeting_mode
        self._connect()

    def _connect(self) -> None:
        self._pet.clicked.connect(self._toggle_input)
        self._pet.clicked.connect(self._rituals.on_pet_clicked_cake)
        self._pet.moved.connect(self._follow)
        self._pet.grabbed.connect(self._wake)
        self._pet.hid.connect(self._on_hide)
        self._pet.wants_travel.connect(self._on_wants_travel)
        self._pet.context_requested.connect(self._show_quick_menu)
        self._speech.talking.connect(self._on_speech_talking)
        self._speech.finished.connect(self._on_speech_finished)
        # 藏边时整只露出的判据 说话中或讲课中
        self._pet.bind_speaking(lambda: self._speech.is_speaking or self._lecturing)
        self._input.submitted.connect(self._worker.handle)
        self._input.submitted.connect(self._on_submit)
        self._hotkeys.talk_pressed.connect(self._on_talk_hotkey)
        self._hear_partial.connect(self._on_hear_partial)
        self._hear_final.connect(self._on_hear_final)
        self._hear_state.connect(self._on_hear_state)
        self._hear_submit.connect(self._worker.handle)
        self._hear_submit.connect(self._on_submit)
        self._hear_tick.connect(self._on_hear_tick)
        self._worker.reply_ready.connect(self._on_reply)
        self._worker.proactive_reply.connect(self._on_proactive_reply)
        self._worker.busy_changed.connect(self._on_busy)
        self._worker.task_finished.connect(self._on_task_finished)
        self._worker.step.connect(self._on_step)
        self._worker.think_text.connect(self._on_think_text)
        self._worker.plan_changed.connect(self._on_plan)
        self._worker.media_requested.connect(self._on_media)
        self._worker.perform_requested.connect(self._on_perform)
        self._worker.control_active.connect(self._on_control)
        self._worker.background_done.connect(self._on_background_done)
        self.request_reminder.connect(self._worker.deliver_reminder)
        self.request_task.connect(self._worker.run_task)
        self.request_timed_task.connect(self._worker.run_timed_task)
        self.request_proactive.connect(self._worker.speak_spontaneously)
        self.request_explore.connect(self._worker.explore)
        self.request_peek.connect(self._worker.peek_screen)
        self.request_dream.connect(self._worker.make_dream)
        self.request_consolidate.connect(self._worker.consolidate)
        self._worker.dream_ready.connect(self._dreams.set_dream)
        self.request_analyze.connect(self._worker.analyze_screen)
        self.request_message.connect(self._worker.handle)
        self._worker.analysis_ready.connect(self._on_analysis)
        self.request_confirm.connect(self._on_confirm_requested)
        self._confirm_box.answered.connect(self._on_confirm_answered)
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

    def run(self) -> int:
        stats.mark_first_seen()
        hearing.set_enabled(self._settings.hear_enabled)
        hearing.set_wake_enabled(self._settings.hear_enabled and self._settings.wake_enabled)
        self._pet.express("neutral")
        self._thread.start()
        self._tray.show()
        self._presence_timer.start(_PRESENCE_POLL_MS)
        self._reminder_timer.start(_REMINDER_POLL_MS)
        self._proactive_timer.start(_PROACTIVE_POLL_MS)
        self._watch_timer.start(_WATCH_POLL_MS)
        self._feeding.start()
        self._sensors.start()
        self._playtime.start()
        self._watchers.start()
        self._rituals.start()
        self._wellbeing.start()
        self._dreams.start()
        self._hotkeys.start()
        from desktop_pet.executor import vision
        vision.prewarm()
        self._open_panel()
        return self._app.exec()
