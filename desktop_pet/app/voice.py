# 听觉接线mixin 按住说话 唤醒词 听写浮条状态流转

from __future__ import annotations


from desktop_pet import hearing


class VoiceMixin:
    """语音输入这一侧的信号处理"""

    def _on_talk_hotkey(self) -> None:
        if not self._settings.hear_enabled or not hearing.is_ready():
            return
        if self._busy or self._worker.is_running:
            return  # 它正干着活 这时候的语音会排队造成迷惑 直接不收
        hearing.start_talk()
        self._talk_release_timer.start()

    def _poll_talk_release(self) -> None:
        """轮询按住说话的主键 松开即定稿"""
        import ctypes
        from desktop_pet.hotkeys import parse_combo
        parsed = parse_combo(self._settings.hotkey_talk)
        vk = parsed[1] if parsed else 0
        if not vk or not (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000):
            self._talk_release_timer.stop()
            hearing.stop_talk()

    def _on_hear_state(self, state: str) -> None:
        if state == "listening":
            self._hear_got_final = False
            self._hearbar.begin()
        elif state == "wake_hit":
            self._wake()
        elif state == "idle":
            if self._hear_got_final:
                self._hear_got_final = False
            else:
                self._hearbar.dismiss()  # 没听清或空说 静静收起

    def _on_hear_partial(self, text: str) -> None:
        self._hearbar.set_text(text)

    def _on_hear_tick(self, remaining: float) -> None:
        self._hearbar.set_remaining(remaining)

    def _on_hear_final(self, text: str) -> None:
        """一句定稿 当成打字输入走完整对话链路"""
        self._hear_got_final = True
        self._hearbar.finish(text)
        self._wake()
        self._hear_submit.emit(text, None)
