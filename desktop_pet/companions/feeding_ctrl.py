# author: bdth
# email: 2074055628@qq.com
# 投喂伴生 文件分流吃进肚或知识库

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from desktop_pet import i18n, journal, somatic, stats
from desktop_pet.agent import prompts as agent_prompts
from desktop_pet.audit import audit
from desktop_pet.docs import docs
from desktop_pet.emotion.state import emotion
from desktop_pet.pet import feeding
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.confirm import ConfirmBox


class FeedingCtrl(QObject):
    _feed_note = Signal(str)

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._feed_pending: tuple[list, int] | None = None
        self._feed_doc: str | None = None
        self._feed_confirm = ConfirmBox()
        from desktop_pet.eyes import capture
        capture.register_own_window(int(self._feed_confirm.winId()))
        self._host._pet.fed.connect(self._on_fed)
        self._feed_confirm.answered.connect(self._on_feed_answer)
        self._feed_note.connect(self._on_feed_note)

    def start(self) -> None:
        pass

    @Slot(list)
    def _on_fed(self, paths: list) -> None:
        """投喂入口 按类型分流"""
        kind = feeding.classify(paths)
        if kind == "missing":
            self._host._feed_pop(i18n.t("feed_missing"))
            return
        if kind == "protected":
            self._host._pet.react("recoil")
            self._host._feed_pop(i18n.t("feed_protected"))
            return
        if kind == "risky":
            self._host._pet.react("shake")
            self._host._feed_pop(i18n.t("feed_risky"))
            return
        if kind == "image":
            if self._host._worker.is_running:
                self._host._feed_pop(i18n.t("feed_busy"))
                return
            path = str(Path(paths[0]).expanduser().resolve())
            self._host._pet.react("perk_up")
            self._host.request_message.emit(agent_prompts.FEED_IMAGE_MSG.format(name=Path(path).name, path=path))
            return
        if kind == "doc":
            self._feed_doc = paths[0]
            screen = self._host._app.primaryScreen().availableGeometry()
            self._feed_confirm.ask(i18n.t("feed_doc_ask").format(name=Path(paths[0]).name), self._host._pet, screen)
            return
        total, truncated = feeding.total_size(paths)
        if total > feeding._BIG_BYTES or feeding.has_dir(paths) or truncated:
            self._feed_pending = (paths, total)
            name = Path(paths[0]).name + (f" +{len(paths) - 1}" if len(paths) > 1 else "")
            screen = self._host._app.primaryScreen().availableGeometry()
            self._feed_confirm.ask(
                i18n.t("feed_confirm").format(name=name, size=feeding.human_size(total)), self._host._pet, screen)
            return
        self._eat(paths, total)

    @Slot(bool)
    def _on_feed_answer(self, ok: bool) -> None:
        """投喂确认回来 文档和大餐两种等待"""
        if self._feed_doc is not None:
            path, self._feed_doc = self._feed_doc, None
            if not ok:
                return
            self._host._pet.react("eating")
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
        self._host._pet.react("eating")
        QTimer.singleShot(1700, lambda: self._finish_eat(paths, total))

    def _finish_eat(self, paths: list, total: int) -> None:
        err = feeding.recycle(paths)
        if err:
            self._host._pet.react("droop")
            self._host._feed_pop(i18n.t("feed_eat_fail"))
            audit.reply(f"feed recycle failed: {err}")
            return
        stats.add_eaten(total, len(paths))
        emotion.apply("fed")
        selector.set_emotion(*emotion.snapshot())
        self._host._pet.set_expression("happy")
        names = Path(paths[0]).name + (f" +{len(paths) - 1}" if len(paths) > 1 else "")
        somatic.note(agent_prompts.SOMA_FED.format(names=names, size=feeding.human_size(total)))
        if total > 100 * 1024 * 1024:
            journal.add(f"主人喂我吃了 {feeding.human_size(total)} 的垃圾文件 饱了")
        self._host._feed_pop(i18n.t("feed_eaten").format(size=feeding.human_size(total)))

    @Slot(str)
    def _on_feed_note(self, text: str) -> None:
        self._host._feed_pop(text)
