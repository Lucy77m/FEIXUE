# author: bdth
# email: 2074055628@qq.com
# 桌宠应用主控:装配 PySide6 界面、Agent 工作线程与各类定时器,串起信号槽与事件循环

from __future__ import annotations

import os
import random
import re
import sys
import threading
import traceback
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QColor, QCursor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from desktop_pet import i18n, journal, occasions, persona, presence, stats, voice
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
from desktop_pet.pet.control_panel import ControlPanel
from desktop_pet.pet.media import MediaFrame
from desktop_pet.pet.confirm import ConfirmBox
from desktop_pet.pet.entrance import next_entrance_kind
from desktop_pet.pet.tray import Tray
from desktop_pet.pet.window import PetWindow
from desktop_pet.proactive import proactive
from desktop_pet.reminders import reminders
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
_PROACTIVE_RAPPORT_GATE = {"安静": 0.45, "正常": 0.30, "话痨": 0.15}
_PROACTIVE_RAPPORT_GATE_DEFAULT = 0.30
_CELEBRATE_CHANCE = 0.25
_EXPLORE_CHANCE = 0.3  # 主动开口时，有这个概率"真去网上瞄一眼"再分享(需开联网)
_PEEK_MIN_INTERVAL_S = 600.0  # 看屏帮手两次之间至少隔 10 分钟(隐私 + 省成本)
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
    """统一的浅色调色板：Qt 弹窗(下拉容器/菜单/tooltip)等未被 QSS 覆盖的部件会用它，
    从根上杜绝 Windows 深色模式渗进来(比如下拉框圆角四角露出的黑)。"""
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
    """把底层异常翻成一句人话，让「乱填 key / 断网 / 限流」一眼能看懂，而不是甩英文堆栈。"""
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
    busy_changed = Signal(bool)
    task_finished = Signal(bool)
    step = Signal(str)
    think_text = Signal(str)
    plan_changed = Signal(str)
    media_requested = Signal(str, str, str)
    perform_requested = Signal(str)
    background_done = Signal(str, str)
    rewrite_ready = Signal(str)

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
            except Exception as exc:  # noqa: BLE001
                reply = _friendly_error(exc)
                ok = False
                audit.reply(f"{reply}\n{traceback.format_exc()}")
            if self._agent.was_cancelled(reply) or self._agent.is_cancelled:
                self.busy_changed.emit(False)
                return
            self.reply_ready.emit(reply)
            self.busy_changed.emit(False)
            self.task_finished.emit(ok and not self._agent.hit_step_limit)
            if ok:
                try:
                    self._agent.reflect()
                except Exception:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001
            pass

    @Slot(str)
    def run_task(self, task: str) -> None:
        try:
            self._agent.run_background(task)
        except Exception:  # noqa: BLE001
            pass

    @Slot(str, str)
    def speak_spontaneously(self, mode: str, context: str) -> None:
        try:
            reply = self._agent.speak_spontaneously(mode, context)
            if reply.strip():
                self.reply_ready.emit(reply)
        except Exception:  # noqa: BLE001
            pass

    @Slot(str)
    def explore(self, topic: str) -> None:
        # 在独立 daemon 线程跑临时子代理真去查，绝不阻塞 worker 线程；结果像主动消息一样播报
        def work() -> None:
            try:
                reply = self._agent.explore_topic(topic)
            except Exception:  # noqa: BLE001
                reply = ""
            if reply and reply.strip():
                self.reply_ready.emit(reply)
        threading.Thread(target=work, daemon=True, name="mochi-explore").start()

    @Slot(str)
    def peek_screen(self, trigger: str = "") -> None:
        # 看一眼屏幕判断是否卡住，daemon 线程跑、不阻塞 worker；觉得需要帮才出声
        def work() -> None:
            try:
                reply = self._agent.peek_screen(trigger)
            except Exception:  # noqa: BLE001
                reply = ""
            if reply and reply.strip():
                self.reply_ready.emit(reply)
        threading.Thread(target=work, daemon=True, name="mochi-peek").start()

    @Slot(str)
    def rewrite(self, text: str) -> None:
        # 「顺手就改」：独立 daemon 线程改写选区，不阻塞 worker、不碰主对话历史
        def work() -> None:
            try:
                out = self._agent.rewrite_text(text)
            except Exception:  # noqa: BLE001
                out = ""
            self.rewrite_ready.emit(out)
        threading.Thread(target=work, daemon=True, name="mochi-rewrite").start()

    @Slot(str, str)
    def clip_alchemy(self, kind: str, text: str) -> None:
        # 剪贴板炼金术：独立 daemon 线程处理复制的内容，结果走 speak 播报
        def work() -> None:
            try:
                out = self._agent.transform_clipboard(kind, text)
            except Exception:  # noqa: BLE001
                out = ""
            if out and out.strip():
                self.reply_ready.emit(out)
        threading.Thread(target=work, daemon=True, name="mochi-alchemy").start()

    def forget_all(self) -> None:
        self._agent.forget_all()


_ALCHEMY_MIN_INTERVAL_S = 45.0  # 炼金术最短间隔，免得一直冒泡打扰


class PetApp(QObject):
    request_reminder = Signal(str)
    request_task = Signal(str)
    request_proactive = Signal(str, str)
    request_explore = Signal(str)
    request_peek = Signal(str)
    request_confirm = Signal(str)
    request_rewrite = Signal(str)
    request_clip_alchemy = Signal(str, str)

    def __init__(self) -> None:
        _install_qt_message_filter()
        self._app = QApplication(sys.argv)
        self._app.setStyle("Fusion")  # 统一渲染，不吃 Windows 深色模式调色板(根治下拉/菜单/tooltip 渗黑)
        self._app.setPalette(_light_palette())
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setFont(QFont("Microsoft YaHei UI", 10))
        from desktop_pet.pet.icon import mochi_icon
        self._app.setWindowIcon(mochi_icon())
        super().__init__()

        self._busy = False
        self._shown = False  # MOCHI 是否开机(桌宠显示中)；默认关机，启动后需在主页点「开机」
        self._entered = False  # 是否已经入场过(首次开机播入场动画)
        self._panel = None  # 控制面板单实例(托盘多次单击只激活同一个)
        self._relang = False  # 切换界面语言时置位 → 面板用新语言重开
        self._fired_occasions: set[str] = set()  # 本次运行已庆祝过的节日/生日(避免重复)
        self._last_peek: datetime | None = None  # 上次看屏时间(看屏帮手的冷却)
        self._cancelling = False  # 中断时置位；让 UI 忽略迟到的 step/think 信号
        self._pending_bg: list[tuple[str, str]] = []  # 已完成的后台任务，等空闲时机再播报
        self._confirm_event = threading.Event()  # worker 线程阻塞在这里，等用户点 执行/不执行
        self._confirm_result = False

        from desktop_pet.agent.loop import Agent

        self._settings = Settings.load()
        i18n.set_language(self._settings.ui_language)
        emotion.apply("returned")
        selector.set_emotion(*emotion.snapshot())

        self._pet = PetWindow()
        self._speech = SpeechText()
        self._input = InputBox()
        self._board = BlackBoard()
        self._media = MediaFrame()
        self._confirm_box = ConfirmBox()
        self._thought = ThoughtBubble()
        self._think = ThoughtBubbles()

        from desktop_pet.eyes import capture
        for _w in (self._pet, self._speech, self._input, self._board, self._media, self._confirm_box, self._thought, self._think):
            capture.register_own_window(int(_w.winId()))

        self._lecturing = False
        self._segments: list[tuple[str, str]] = []
        self._seg_i = 0
        self._board_dismiss = QTimer(self)
        self._board_dismiss.setSingleShot(True)
        self._board_dismiss.timeout.connect(self._end_lecture)
        self._board_next = QTimer(self)  # 每块板停留足够长时间读完，再切下一块
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
        self._just_returned = False

        self._tray = Tray(
            on_open_panel=self._open_panel,
            on_quit=self._quit,
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
        self._pet.moved.connect(self._follow)
        self._pet.grabbed.connect(self._wake)
        self._pet.hid.connect(self._on_hide)
        self._speech.talking.connect(self._on_speech_talking)
        self._speech.finished.connect(self._on_speech_finished)
        self._input.submitted.connect(self._worker.handle)
        self._input.submitted.connect(self._on_submit)
        self._worker.reply_ready.connect(self._on_reply)
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
        self.request_proactive.connect(self._worker.speak_spontaneously)
        self.request_explore.connect(self._worker.explore)
        self.request_peek.connect(self._worker.peek_screen)
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

    @Slot()
    def _toggle_input(self) -> None:
        self._wake()
        busy = self._worker.is_running or self._busy or self._speech.is_speaking or self._lecturing
        # 第一次点才执行中断并弹「停下来了」；已经在取消中（worker 还在收尾）再点就别重复弹，
        # 直接去开输入框 —— 否则坏 key/坏网卡住时，每点一下都弹一次，看起来像「一直停不下来」。
        if busy and not self._cancelling:
            self._cancelling = True
            self._worker.cancel()
            self._confirm_result = False
            self._confirm_event.set()  # 若 worker 正卡在等确认，把它放行
            self._confirm_box.close_box()
            self._on_busy(False)
            self._speech.interrupt()
            voice.flush()
            self._reset_lecture()
            self._pet.clear_pending()
            self._thought.pop(i18n.t("ui_stopped"), self._pet)
            return
        if self._input.isVisible():
            self._input.fade_out()
        else:
            self._input.popup(self._pet)

    @Slot()
    def _summon(self) -> None:
        if not self._shown:  # 关机时按热键唤出 = 顺便开机
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
        # 热键注册结果只记录、给控制面板看；不再用桌宠动画打扰（尤其关机时）
        if isinstance(status, dict):
            self._hotkey_status = status

    def _hotkey_status_snapshot(self) -> dict:
        return dict(self._hotkey_status)

    @Slot()
    def _ask_selection(self) -> None:
        if not self._shown:  # 关机时选区问答 = 顺便开机
            self._power_on()
        self._saved_clip = self._app.clipboard().text()
        try:
            import pyautogui
            for mod in ("alt", "ctrl", "shift"):
                pyautogui.keyUp(mod)
        except Exception:  # noqa: BLE001
            self._summon()
            return
        QTimer.singleShot(70, self._copy_selection)

    def _copy_selection(self) -> None:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "c")
        except Exception:  # noqa: BLE001
            self._summon()
            return
        QTimer.singleShot(200, self._after_copy)

    def _after_copy(self) -> None:
        text = self._app.clipboard().text().strip()
        saved = getattr(self, "_saved_clip", "")
        self._summon()
        if not text or text == saved.strip():
            return
        self._app.clipboard().setText(saved)
        snippet = text if len(text) <= 500 else text[:500] + "…"
        self._input.setText(f"关于这个：{snippet}")
        self._input.setFocus()

    # —— 顺手就改：Ctrl+Alt+Q 复制选区 → LLM 改写 → 写回剪贴板并自动粘贴替换 ——
    @Slot()
    def _quick_rewrite(self) -> None:
        if not self._shown:
            self._power_on()
        self._saved_clip = self._app.clipboard().text()
        try:
            import pyautogui
            for mod in ("alt", "ctrl", "shift"):
                pyautogui.keyUp(mod)
        except Exception:  # noqa: BLE001
            return
        QTimer.singleShot(70, self._quick_copy)

    def _quick_copy(self) -> None:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "c")
        except Exception:  # noqa: BLE001
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
        sampler.mark_self_write(result)  # 防回环：别让采样器把自己写回的当新复制
        self._app.clipboard().setText(result)
        if self._settings.quick_paste_back:
            try:
                import pyautogui
                QTimer.singleShot(60, lambda: pyautogui.hotkey("ctrl", "v"))
            except Exception:  # noqa: BLE001
                pass
        self._thought.pop(i18n.t("quick_done"), self._pet)

    # —— 剪贴板炼金术：感知复制内容，空闲时顺手处理 ——
    @Slot()
    def _on_clipboard_changed(self) -> None:
        try:
            sampler.feed(self._app.clipboard().text())
        except Exception:  # noqa: BLE001
            pass

    @Slot(str, str)
    def _on_clip_interesting(self, kind: str, text: str) -> None:
        s = self._settings
        if not s.clip_alchemy:
            return
        allowed = {k.strip() for k in (s.clip_alchemy_kinds or "").split(",") if k.strip()}
        if allowed and kind not in allowed:
            return
        if (self._worker.is_running or self._busy or self._lecturing or self._speech.is_speaking
                or self._input.isVisible() or not self._pet.isVisible() or self._pet.is_asleep):
            return  # 别打断：忙/说话/输入框开/没显示/睡着 都不触发
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
        except Exception:  # noqa: BLE001
            pass
        selector.set_emotion(*emotion.snapshot())
        self._wake()
        self._just_returned = False
        stats.bump_interactions()
        proactive.defer(datetime.now(), self._settings.proactive_level)
        self._input.fade_out()

    @Slot(str)
    def _on_reply(self, raw: str) -> None:
        tag, text = _parse_emotion(raw)
        self._pet.express(tag)
        self._reset_lecture()
        segments = parse_segments(text)  # 只解析一次，复用给 _start_lecture（原来 has_board 已切一遍、命中后又切一遍）
        voice.speak(" ".join(body for kind, body in segments if kind != "board"))  # 朗读非黑板内容(开了才出声)
        if any(kind == "board" for kind, _ in segments):
            self._start_lecture(segments)
        else:
            self._speech.place_below(self._pet)
            self._speech.speak(_split_sentences(text))

    @Slot(str, str)
    def _on_background_done(self, task: str, result: str) -> None:
        # 先排队——绝不打断用户和我正在前台做的事。
        self._pending_bg.append((task, result))
        self._drain_pending_bg()

    def _foreground_busy(self) -> bool:
        return (self._busy or self._worker.is_running or self._speech.is_speaking
                or self._lecturing or self._cancelling or self._input.isVisible())

    def _drain_pending_bg(self) -> None:
        if not self._pending_bg or self._foreground_busy() or not self._pet.isVisible():
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
            # 不要立刻跳到下一段——让这块板停留足够长时间读完
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
    def _on_step(self, label: str) -> None:
        if self._cancelling:  # 任务被中断——忽略仍在途中的 step 信号
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
        if self._cancelling:
            return
        self._board.present(
            markdown, self._pet, self._app.primaryScreen().availableGeometry(),
            animate=not self._board.isVisible(),
        )

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
        # 由 agent 的 confirm 工具在 WORKER 线程调用：请 UI 弹面板，阻塞等用户点 执行/不执行
        self._confirm_result = False
        self._confirm_event.clear()
        self.request_confirm.emit(action)  # 入队 → UI 线程的 _on_confirm_requested
        self._confirm_event.wait(timeout=300)  # 最长 5 分钟；取消也会 set 这个 event
        return self._confirm_result

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
        self._confirm_result = ok
        self._confirm_event.set()

    @Slot(bool)
    def _on_busy(self, busy: bool) -> None:
        self._busy = busy
        self._pet.set_busy(busy)
        if busy:
            self._cancelling = False  # 新一轮开始——信号重新有效
            self._wake()
            self._media.dismiss()
            self._pet.set_think_energy(emotion.snapshot()[1])
            self._think.start(self._pet)
        else:
            self._think.stop()
            self._drain_pending_bg()  # 前台空出来了——排队的后台结果现在可以播报了

    @Slot(bool)
    def _on_task_finished(self, ok: bool) -> None:
        try:
            emotion.apply("task_done" if ok else "task_failed")
        except Exception:  # noqa: BLE001
            pass
        selector.set_emotion(*emotion.snapshot())
        # 回复时已经触发过一次情绪反应；别再叠第二次
        # （之前就是这样导致桌宠回完话紧接着「抽动两下」）。
        if not self._lecturing and not self._pet.is_reacting:
            if not ok:
                self._pet.slump()
            elif random.random() < _CELEBRATE_CHANCE:
                self._pet.celebrate()

    @Slot()
    def _on_presence(self) -> None:
        try:
            self._drain_pending_bg()  # 兜底：等空下来时把排队的后台结果播报掉
            radar.observe()  # 维持卡住雷达的窗口停留计时
            self._poll_presence()
        except Exception:  # noqa: BLE001
            pass

    def _poll_presence(self) -> None:
        if self._busy or not self._pet.isVisible():
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
        except Exception:  # noqa: BLE001
            pass

    def _drain_reminders(self) -> None:
        if not self._shown:  # 关机时不弹提醒(开机后到点的会走迟到宽限补报)
            return
        due = reminders.due(datetime.now())
        if not due:
            return
        says = [r.what for r in due if r.kind != "do"]
        tasks = [r.what for r in due if r.kind == "do"]
        if says:
            if not self._pet.isVisible():
                self._pet.setVisible(True)
            self._pet.wake()
            self.request_reminder.emit("；".join(says))
        for task in tasks:
            self.request_task.emit(task)

    @Slot()
    def _check_proactive(self) -> None:
        try:
            if self._maybe_peek():  # 看屏帮手优先(默认关)
                return
            if not self._maybe_occasion():  # 节日/生日次之；都没命中才走普通主动搭话
                self._maybe_speak_up()
        except Exception:  # noqa: BLE001
            pass

    def _maybe_peek(self) -> bool:
        s = self._settings
        if not s.watch_screen or not s.allow_control:
            return False  # 双开关：必须显式开「看屏」且没关「操控」
        if (self._worker.is_running or self._busy or self._lecturing or self._speech.is_speaking
                or self._input.isVisible() or not self._pet.isVisible() or self._pet.is_asleep):
            return False
        if presence.idle_seconds() >= 60:  # 人得正在用(idle 很小)，否则不偷看
            return False
        _val, _aro, rapport = emotion.snapshot()
        if rapport < 0.35:
            return False
        now = datetime.now()
        if self._last_peek is not None and (now - self._last_peek).total_seconds() < _PEEK_MIN_INTERVAL_S:
            return False
        sig = radar.observe()
        if not sig.worth_peek:  # 雷达说不值得看(无报错、未久驻)就不偷看——取代原来的随机概率
            return False
        self._last_peek = now
        self.request_peek.emit(sig.title)
        return True

    def _maybe_occasion(self) -> bool:
        if not self._settings.proactive_enabled:
            return False
        if (self._worker.is_running or self._busy or self._lecturing or self._speech.is_speaking
                or self._input.isVisible() or not self._pet.isVisible() or self._pet.is_asleep):
            return False
        if presence.idle_seconds() >= _AWAY_S:  # 人不在就不庆祝(等回来)
            return False
        key = occasions.today_key(datetime.now(), self._settings.birthday)
        if not key or key in self._fired_occasions:
            return False
        self._fired_occasions.add(key)
        ctx = (f"（{occasions.describe(key)}，用你自己的口吻、温暖自然地道一句应景的话，"
               "别太正式、也别照念。）")
        if key == "birthday":
            self._pet.celebrate()
        else:
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
            self.request_explore.emit(self._pick_explore_topic())  # 真去网上瞄一眼再分享
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
        # 宠物贴边藏起来了 → 收起跟随它的浮层(输入框/语音气泡/黑板/思考粒子/拍立得)
        self._input.fade_out()
        self._speech.interrupt()
        voice.flush()
        self._reset_lecture()
        self._think.stop()
        self._media.dismiss()

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
        if self._media.isVisible():
            self._media.follow(self._pet, screen)
        if self._confirm_box.is_open():
            self._confirm_box.follow(self._pet, screen)

    def _status_snapshot(self) -> dict:
        """给控制面板主页用的状态机快照。"""
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
            except Exception:  # noqa: BLE001
                return 0

        try:
            p_count, p_cap = proactive.today(datetime.now(), self._settings.proactive_level)
        except Exception:  # noqa: BLE001
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
        """让桌宠真正上线：首次播入场动画，之后只是显示+唤醒。"""
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
        else:
            self._pet.wake()

    def _bond_snapshot(self) -> dict:
        """给控制面板「它眼中的你」页用的羁绊快照(记忆/人格/相处统计)。"""
        _val, _aro, rapport = emotion.snapshot()
        st = stats.snapshot()

        def _safe(fn, default):
            try:
                return fn()
            except Exception:  # noqa: BLE001
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
        }

    def _toggle_power(self) -> None:
        if self._shown:
            self._power_off()
        else:
            self._power_on()

    def _power_on(self) -> None:
        """开机：让桌宠出现(首次播入场动画，之后唤醒)。"""
        if self._shown:
            return
        self._shown = True
        self._cancelling = False
        self._bring_online()
        emotion.apply("returned")
        selector.set_emotion(*emotion.snapshot())
        self._just_returned = True

    def _power_off(self) -> None:
        """关机：收起桌宠动画 + 停掉进行中的一切 + 收起所有浮层；程序仍常驻后台(不退出)。"""
        if not self._shown:
            return
        self._shown = False
        self._cancelling = True
        self._worker.cancel()
        self._confirm_result = False
        self._confirm_event.set()  # 若 worker 正卡在等确认，放它走
        self._confirm_box.close_box()
        self._speech.interrupt()
        voice.flush()
        self._reset_lecture()
        self._media.dismiss()
        self._input.fade_out()
        self._pending_bg.clear()
        self._on_busy(False)
        self._pet.clear_pending()
        radar.reset()
        self._pet.setVisible(False)  # 收起动画

    def _open_panel(self) -> None:
        if self._panel is not None:  # 单实例：已经开着就激活它，绝不叠出第二个
            self._panel.raise_()
            self._panel.activateWindow()
            return
        while True:  # 切界面语言时关掉重开，用新语言重建整个面板
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
            )
            self._panel.exec()
            self._panel = None
            if not self._relang:
                break

    def _set_language(self, lang: str) -> None:
        # 界面语言即时生效：存盘 + 切 i18n + 重译托盘，然后关掉面板让 _open_panel 用新语言重开
        self._settings.ui_language = lang
        self._settings.save()
        i18n.set_language(lang)
        self._tray.retranslate()
        self._relang = True
        if self._panel is not None:
            self._panel.accept()

    def _apply_settings_live(self) -> None:
        i18n.set_language(self._settings.ui_language)
        self._tray.retranslate()
        voice.set_enabled(self._settings.tts_enabled)
        sampler.set_enabled(self._settings.clip_sampler or self._settings.clip_alchemy)
        self._hotkeys.restart({
            "summon": self._settings.hotkey_summon,
            "ask": self._settings.hotkey_ask,
            "quick": self._settings.hotkey_quick,
        })
        if self._input.isVisible():
            self._input.setPlaceholderText(i18n.t("input_placeholder"))

    def _reset_all(self) -> None:
        if self._busy or self._worker.is_running:
            self._worker.cancel()
        self._worker.forget_all()
        emotion.reset()
        reminders.clear()
        stats.clear()  # 清空记忆=像新生儿，相处统计也归零
        selector.set_emotion(*emotion.snapshot())
        self._pet.express("neutral")

    def _quit(self) -> None:
        self._hotkeys.stop()
        if self._worker.is_running:
            self._worker.cancel()  # 让卡在网络/工具里的 agent.run 从下一个检查点尽快退出
        self._confirm_event.set()  # 万一正卡在等确认面板，放它走
        self._worker.shutdown()
        try:
            mcp_hub.shutdown()  # 关 MCP 事件循环 + stdio 子进程；下面 os._exit 会绕过 atexit，故这里显式收
        except Exception:  # noqa: BLE001
            pass
        self._thread.quit()
        self._thread.wait(3000)  # 给 3 秒优雅退
        self._app.quit()
        os._exit(0)  # 兜底：worker / MCP / 后台线程万一仍卡着，也保证进程立刻退干净、绝不挂死
        # （子进程在 cancel/shutdown 已 kill，配置/情绪是即时存盘的，强退不丢数据）

    def run(self) -> int:
        stats.mark_first_seen()  # 记下你们第一次相遇的日子
        voice.set_enabled(self._settings.tts_enabled)
        self._pet.express("neutral")
        self._thread.start()
        self._tray.show()
        self._presence_timer.start(_PRESENCE_POLL_MS)
        self._reminder_timer.start(_REMINDER_POLL_MS)
        self._proactive_timer.start(_PROACTIVE_POLL_MS)
        self._hotkeys.start()
        from desktop_pet.executor import vision
        vision.prewarm()
        # 默认关机：不自动显示桌宠，启动即弹控制面板；必须在主页点「开机」MOCHI 才出现。
        self._open_panel()
        return self._app.exec()
