# author: bdth
# email: 2074055628@qq.com
# agent与ui之间的桥mixin 回复上屏 讲课 确认框 进度气泡

from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtGui import QCursor

from desktop_pet import i18n, stats
from desktop_pet.app.textflow import _parse_emotion, _split_sentences
from desktop_pet.emotion.state import appraise_user_message, emotion
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.blackboard import parse_segments
from desktop_pet.proactive import proactive


_CELEBRATE_CHANCE = 0.25


class AgentBridgeMixin:
    """承接worker信号把结果演出来"""

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
        self._pet.yield_performance()  # 点名演出让位 新消息要摆思考姿势
        self._todo.dismiss()
        self._just_returned = False
        stats.bump_interactions()
        proactive.defer(datetime.now(), self._settings.proactive_level)
        self._input.fade_out()

    def _on_proactive_reply(self, raw: str) -> None:
        if not self._shown or self._foreground_busy() or self._lecturing:
            return  # 关机隐藏时即便有在途的主动回复返回也不弹气泡
        self._on_reply(raw)

    def _on_reply(self, raw: str) -> None:
        if not self._shown:
            return  # 关机或退出后才回来的回复别再弹气泡说话
        tag, text = _parse_emotion(raw)
        self._pet.express(tag)
        self._reset_lecture()
        self._speech.interrupt()
        segments = parse_segments(text)
        if any(kind == "board" for kind, _ in segments):
            # 黑板走讲课逐段流
            self._start_lecture(segments)
        else:
            self._speech.place_below(self._pet)
            sents = _split_sentences(text)
            self._speech.speak(sents)

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

    def _on_speech_finished(self) -> None:
        self._pet.set_state("rest")
        if self._lecturing:
            self._advance_lecture()
        else:
            self._drain_pending_bg()

    def _on_speech_talking(self, on: bool) -> None:
        self._pet.set_state("speaking" if on else "rest")

    def _on_step(self, label: str) -> None:
        if self._cancelling:
            return
        self._pet.note_think_step(label)
        if label == "思考中…":
            return
        self._thought.show_step(label, self._pet)

    def _on_think_text(self, fragment: str) -> None:
        if self._cancelling:
            return
        self._think.feed(fragment)

    def _on_plan(self, markdown: str) -> None:
        if self._cancelling or not self._pet.isVisible():
            return
        self._todo.set_markdown(markdown, self._pet, self._app.primaryScreen().availableGeometry())

    def _on_media(self, kind: str, path: str, caption: str) -> None:
        if self._cancelling:
            return
        screen = self._app.primaryScreen().availableGeometry()
        if kind == "gif":
            self._media.play_gif(path, caption, self._pet, screen)
        else:
            self._media.show_image(path, caption, self._pet, screen)

    def _on_perform(self, name: str) -> None:
        if self._cancelling:
            return
        self._wake()
        self._pet.perform(name)

    def _on_control(self, active: bool, label: str) -> None:
        """agent 借用鼠标键盘时顶部弹正在帮你操作浮层"""
        if active:
            if not self._shown:
                return  # 关机隐藏时不弹
            self._control_hide_timer.stop()
            screen = (self._app.screenAt(QCursor.pos()) or self._app.primaryScreen()).availableGeometry()
            self._control_hint.show_hint(label, screen)
        else:
            # 留个零点九秒让你看清 下一次操作会取消这次收起 不闪
            self._control_hide_timer.start(900)

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

    def _on_confirm_requested(self, action: str) -> None:
        if self._cancelling:
            self._confirm_event.set()
            return
        self._wake()
        screen = self._app.primaryScreen().availableGeometry()
        self._confirm_box.ask(action, self._pet, screen)

    def _on_confirm_answered(self, ok: bool) -> None:
        if not self._confirm_pending:
            return
        self._confirm_result = ok
        self._confirm_event.set()

    def _feed_pop(self, text: str) -> None:
        if self._meeting_mode or not self._shown or self._engaged():
            return  # 开会 关机 忙于任务或对话时主动气泡全咽下去 不打断
        self._thought.pop(text, self._pet)

    def _feed_react(self, name: str) -> None:
        """伴生的自发小动作 忙或对话或关机或开会时不放 免得打断思考姿势"""
        if self._meeting_mode or not self._shown or self._engaged():
            return
        self._pet.react(name)

    def _feed_perform(self, name: str) -> None:
        """伴生的自发表演 同上 忙时不打断"""
        if self._meeting_mode or not self._shown or self._engaged():
            return
        self._pet.perform(name)

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
            self._control_hide_timer.stop()
            self._control_hint.hide_hint()  # 回合结束兜底收起操作浮层 防卡住
            self._timed_inflight = False
            if not self._cancelling:   # 取消态不清 _inflight_timed 留给requeue
                self._inflight_timed = None
            self._drain_pending_bg()
            self._drain_timed()

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
