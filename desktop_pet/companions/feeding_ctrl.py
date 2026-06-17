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
    _feed_result = Signal(object)  # 后台删文件结果回主线程演出 err lockname holder paths total
    _feed_sized = Signal(object)   # 后台算完总大小回主线程决定弹确认还是直接吃 paths total truncated

    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._feed_pending: tuple[list, int] | None = None
        self._feed_doc: str | None = None
        self._sizing = False  # 正在后台量这次投喂的总大小 期间挡住叠加
        self._stopped = False  # 退出已开始 别再启动会被 os._exit 截断的回收站删除
        self._feed_confirm = ConfirmBox()
        from desktop_pet.eyes import capture
        capture.register_own_window(int(self._feed_confirm.winId()))
        self._host._pet.fed.connect(self._on_fed)
        self._feed_confirm.answered.connect(self._on_feed_answer)
        self._feed_note.connect(self._on_feed_note)
        self._feed_result.connect(self._on_feed_result)
        self._feed_sized.connect(self._on_feed_sized)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        # 置位 已排队的 _finish_eat 发现已停就不删 别让 os._exit 把回收站操作截半
        self._stopped = True

    @Slot(list)
    def _on_fed(self, paths: list) -> None:
        """投喂入口 按类型分流"""
        # 上次确认框还没答别再叠 doc 和大餐共用一个 ConfirmBox 叠加会串话答错对象
        if self._feed_doc is not None or self._feed_pending is not None or self._sizing:
            self._host._feed_pop(i18n.t("feed_busy"))
            return
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
        # total_size 会 os.walk 最多两万个文件 在 ui 线程做会冻住 丢后台量完回主线程决定
        self._sizing = True
        threading.Thread(target=self._size_then_decide, args=(paths,), daemon=True, name="mochi-feed-size").start()

    def _size_then_decide(self, paths: list) -> None:
        total, truncated = feeding.total_size(paths)
        self._feed_sized.emit((paths, total, truncated))

    @Slot(object)
    def _on_feed_sized(self, data: object) -> None:
        """后台量完总大小回主线程 大餐文件夹弹确认 小份直接吃"""
        paths, total, truncated = data
        self._sizing = False
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
        if self._stopped:
            return  # 退出中这次别真删 留着文件下次启动可重喂 好过 os._exit 把删除截半
        # 真删文件 回收站 COM 失败重试占用诊断全是慢阻塞活 放后台别冻住 qt 事件循环
        def work() -> None:
            err = feeding.recycle(paths)
            name = who = ""
            if err and not err.startswith(("path not found", "no valid path")):
                name, who = feeding.diagnose_lock(paths)  # 真锁住才诊断谁锁的
            self._feed_result.emit((err, name, who, paths, total))
        threading.Thread(target=work, daemon=True, name="mochi-feed-eat").start()

    @Slot(object)
    def _on_feed_result(self, data: object) -> None:
        """后台删完回主线程 演出吃饱或被占用"""
        err, name, who, paths, total = data
        if err:
            self._host._pet.react("droop")
            if err.startswith(("path not found", "no valid path")):
                msg = i18n.t("feed_missing")  # 路径不对或没了别说占用
            else:
                msg = (i18n.t("feed_eat_locked").format(name=name, who=who or i18n.t("feed_lock_unknown"))
                       if name else i18n.t("feed_eat_fail"))  # 真锁住才点名 谁都没锁才退回含糊
            self._host._feed_pop(msg)
            audit.reply(f"feed recycle failed: {err} [locked={name!r} holder={who!r}]")
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
