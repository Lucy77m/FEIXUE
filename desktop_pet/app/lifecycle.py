# author: bdth
# email: 2074055628@qq.com
# 生命周期mixin 上线下线 控制面板 设置生效 退出清场

from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QCursor

from desktop_pet import hearing, i18n, journal, persona, stats
from desktop_pet.clipsampler import sampler
from desktop_pet.docs import docs
from desktop_pet.emotion.state import emotion
from desktop_pet.eyes.radar import radar
from desktop_pet.mcp_hub import mcp_hub
from desktop_pet.memory.store import store
from desktop_pet.pet import feeding
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.control_panel import ControlPanel
from desktop_pet.pet.entrance import next_entrance_kind
from desktop_pet.proactive import proactive
from desktop_pet.reminders import reminders
from desktop_pet.skills import skills


_PET_MARGIN = 60


class LifecycleMixin:
    """开关机 面板和善后"""

    def _wake(self) -> None:
        self._pet.wake()

    def _on_hide(self) -> None:
        self._cancel_active_task(notify=False)
        self._input.fade_out()
        self._speech.interrupt()
        self._reset_lecture()
        self._think.stop()
        self._media.dismiss()
        self._todo.dismiss()

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
            QTimer.singleShot(5200, self._rituals.morning_ritual)
        else:
            self._pet.wake()

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
            "journal": _safe(lambda: journal.diary(20), []),
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
        self._reset_lecture()
        self._media.dismiss()
        self._todo.dismiss()
        self._control_hide_timer.stop()
        self._control_hint.hide_hint()
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

    def _apply_settings_live(self) -> None:
        i18n.set_language(self._settings.ui_language)
        self._tray.retranslate()
        hearing.set_enabled(self._settings.hear_enabled)
        hearing.set_wake_enabled(self._settings.hear_enabled and self._settings.wake_enabled)
        sampler.set_enabled(self._settings.clip_sampler or self._settings.clip_alchemy)
        try:
            self._sensors._check_weather()  # 天气开关切换后立即生效 关了就收伞 开了马上查 不必等2小时
        except Exception:
            pass
        self._hotkeys.restart({
            "summon": self._settings.hotkey_summon,
            "ask": self._settings.hotkey_ask,
            "quick": self._settings.hotkey_quick,
            "talk": self._settings.hotkey_talk,
        })
        if self._input.isVisible():
            self._input.setPlaceholderText(i18n.t("input_placeholder"))

    def _new_topic(self) -> None:
        if self._busy or self._worker.is_running:
            self._worker.cancel()
        # 经队列进 worker 线程:cancel 让在途 run() 收尾后 再串行清消息历史 不和 run() 抢同一个 list
        self.request_new_topic.emit()
        self._speech.interrupt()
        self._todo.dismiss()
        self._reset_lecture()

    def _reset_all(self) -> None:
        if self._busy or self._worker.is_running:
            self._worker.cancel()
        self.request_forget_all.emit()  # 同上 改走队列进 worker 线程 别在 UI 线程直接 wipe + 改消息历史
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
        # 先掐死全部伴生轮询 退出过程不再孵新线程
        for c in (self._sensors, self._playtime, self._watchers, self._rituals, self._feeding, self._wellbeing, self._dreams):
            try:
                c.stop()
            except Exception:
                pass
        if self._rituals.farewell():
            return
        self._requeue_timed()  # 没派发的定时(do)任务写回 reminders 持久化 别随 os._exit 一起丢掉
        for _t in (self._presence_timer, self._reminder_timer, self._proactive_timer,
                   self._watch_timer):
            try:
                _t.stop()
            except Exception:
                pass
        self._hotkeys.stop()
        try:
            hearing.shutdown()
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
        # 先停 worker 线程的事件循环并等它退出 run()——务必在 shutdown() 杀 shell/python 子进程之前
        # 否则主线程的 close() 会和仍在 run() 里用着子进程的 worker 线程 对杀同一个 Popen(对杀曾引发 access violation)
        self._thread.quit()
        self._thread.wait(3000)
        self._worker.shutdown()  # 此刻 worker 已停 杀子进程不再撞在途调用
        try:
            mcp_hub.shutdown()
        except Exception:
            pass
        # 硬退之前干净关掉两个 SQLite 库——锁住等后台反思的在途 commit 收尾再关。
        # 关完磁盘上的库就是一致的，进程随后退出也不会把它截断成 malformed（库损坏根因）
        for db in (store, docs):
            try:
                db.close()
            except Exception:
                pass
        # os._exit 直接走 C _exit 立即终止 不跑 Qt 析构/不对自身 TerminateProcess
        # ——那两样都在多线程退出时引发过 access violation；os._exit 可靠且不触发析构故障
        self._app.quit()
        os._exit(0)
