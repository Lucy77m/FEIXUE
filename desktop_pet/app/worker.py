# agent工作线程 对话和各类后台差事都从这进 信号发回ui

from __future__ import annotations

import logging
import threading
import traceback

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, Signal, Slot

from desktop_pet.app.textflow import _friendly_error
from desktop_pet.audit import audit


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
    control_active = Signal(bool, str)
    background_done = Signal(str, str)
    rewrite_ready = Signal(str)
    analysis_ready = Signal(str)
    dream_ready = Signal(str)

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
                    on_perform=self.perform_requested.emit, on_control=self.control_active.emit,
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
                    logger.debug("worker: reflect failed", exc_info=True)
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
                    on_perform=self.perform_requested.emit, on_control=self.control_active.emit,
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
            elif mode == "workshop_revisit":
                self.proactive_reply.emit("")
        except Exception as exc:
            audit.system("speak_spontaneously failed", error=repr(exc))
            if mode == "workshop_revisit":
                self.proactive_reply.emit("")

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
        threading.Thread(target=work, daemon=True, name="feixue-explore").start()

    @Slot()
    def make_dream(self) -> None:
        # 睡着时后台揉一个梦 不出声 攒着回来再提
        def work() -> None:
            try:
                text = self._agent.dream()
            except Exception as exc:
                audit.system("dream failed", error=repr(exc))
                text = ""
            if text and text.strip():
                self.dream_ready.emit(text)
        threading.Thread(target=work, daemon=True, name="feixue-dream").start()

    @Slot()
    def consolidate(self) -> None:
        # 睡着时后台把成簇零碎记忆揉成高阶概括 不出声 没簇就静默no-op
        def work() -> None:
            try:
                n = self._agent.consolidate_memory()
                if n:
                    audit.system("memory consolidated", merged=n)
            except Exception as exc:
                audit.system("consolidate failed", error=repr(exc))
        threading.Thread(target=work, daemon=True, name="feixue-consolidate").start()

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
        threading.Thread(target=work, daemon=True, name="feixue-peek").start()

    @Slot(str)
    def analyze_screen(self, focus: str) -> None:
        def work() -> None:
            try:
                reply = self._agent.analyze_screen(focus)
            except Exception as exc:
                audit.system("analyze_screen failed", error=repr(exc))
                reply = ""
            self.analysis_ready.emit(reply or "")
        threading.Thread(target=work, daemon=True, name="feixue-watch").start()

    @Slot(str)
    def rewrite(self, text: str) -> None:
        def work() -> None:
            try:
                out = self._agent.rewrite_text(text)
            except Exception as exc:
                audit.system("rewrite failed", error=repr(exc))
                out = ""
            self.rewrite_ready.emit(out)
        threading.Thread(target=work, daemon=True, name="feixue-rewrite").start()

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
        threading.Thread(target=work, daemon=True, name="feixue-alchemy").start()

    @Slot()
    def forget_all(self) -> None:
        # 经队列在 worker 线程跑 必须和在途 run 串行 不能从 UI 线程直接改 agent._messages 会撕裂消息历史
        self._agent.forget_all()

    @Slot()
    def new_topic(self) -> None:
        self._agent.new_topic()
