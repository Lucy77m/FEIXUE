"""Turn desktop drops into visible Agent tasks and persistent keepsakes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QMenu

from desktop_pet import i18n, journal, keepsakes
from desktop_pet.pet import feeding
from desktop_pet.pet.chat import attachment_payload
from desktop_pet.pet.tray import _dress


@dataclass
class WorkflowSession:
    kind: str
    label: str
    source: str
    action: str
    result: str = ""
    world_id: str = ""


class WorkflowCtrl(QObject):
    def __init__(self, host) -> None:
        super().__init__()
        self._host = host
        self._offer: dict | None = None
        self._active: WorkflowSession | None = None
        self._menu: QMenu | None = None
        self._host._pet.offered.connect(self._on_offer)

    def stop(self) -> None:
        if self._active is not None and self._active.action == "workshop":
            self._host._workshop.stop()
        self._offer = None
        self._active = None
        self._host._pet.clear_work_item()
        if self._menu is not None:
            self._menu.close()

    @Slot(object)
    def _on_offer(self, payload: object) -> None:
        if not isinstance(payload, dict) or self._host._engaged():
            self._host._feed_pop(i18n.t("workflow_busy"))
            return
        offer = self._normalize(payload)
        if offer is None:
            return
        self._offer = offer
        self._host._pet.wake()
        self._host._pet.set_work_item(offer["kind"], offer["label"], "received")
        self._host._pet.react("perk_up")
        self._show_actions()

    def _normalize(self, payload: dict) -> dict | None:
        kind = str(payload.get("kind", "text"))
        if kind == "files":
            paths = [str(Path(p).expanduser().resolve()) for p in payload.get("paths", []) if Path(p).exists()]
            if not paths:
                return None
            suffix = Path(paths[0]).suffix.lower()
            visual = suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
            return {
                "kind": "image" if visual else "file",
                "label": Path(paths[0]).name + (f" +{len(paths) - 1}" if len(paths) > 1 else ""),
                "source": "; ".join(paths),
                "paths": paths,
                "text": "",
                "feedable": feeding.classify(paths) == "food",
                "workshopable": feeding.classify(paths) == "doc",
            }
        text = str(payload.get("text", "")).strip()
        if not text:
            return None
        return {
            "kind": "url" if kind == "url" else "text",
            "label": " ".join(text.split())[:42],
            "source": text[:500],
            "paths": [],
            "text": text[:8000],
            "feedable": False,
            "workshopable": False,
        }

    def _show_actions(self) -> None:
        if self._offer is None:
            return
        menu = _dress(QMenu())
        for action in self.actions_for(
            self._offer["kind"], self._offer.get("feedable", False),
            self._offer.get("workshopable", False),
        ):
            item = QAction(i18n.t(f"workflow_{action}"), menu)
            item.triggered.connect(lambda _checked=False, value=action: self._start(value))
            menu.addAction(item)
        menu.aboutToHide.connect(self._menu_hidden)
        self._menu = menu
        menu.popup(QCursor.pos())

    @staticmethod
    def actions_for(kind: str, feedable: bool = False, workshopable: bool = False) -> tuple[str, ...]:
        if kind == "image":
            return ("inspect", "summarize", "remember")
        if kind == "file":
            base = ("inspect", "summarize", "organize", "remember")
            return (("workshop",) if workshopable else ()) + base + (("feed",) if feedable else ())
        if kind == "url":
            return ("inspect", "summarize", "remember")
        return ("explain", "summarize", "remember")

    def _menu_hidden(self) -> None:
        if self._active is None and self._offer is not None:
            QTimer.singleShot(250, self._clear_unstarted)

    def _clear_unstarted(self) -> None:
        if self._active is None:
            self._offer = None
            self._host._pet.clear_work_item()

    def _start(self, action: str) -> None:
        offer, self._offer = self._offer, None
        if offer is None:
            return
        if action == "feed":
            self._host._pet.clear_work_item()
            self._host._feeding.offer(offer["paths"])
            return
        prompt = self._prompt(action, offer)
        attachments = attachment_payload(offer["paths"])
        self._active = WorkflowSession(
            kind=offer["kind"], label=offer["label"], source=offer["source"], action=action,
        )
        if action == "workshop":
            world_id = self._host._workshop.begin(offer["label"], offer["source"])
            if not world_id:
                self._active = None
                self._host._pet.clear_work_item()
                self._host._feed_pop(i18n.t("workflow_busy"))
                return
            self._active.world_id = world_id
        else:
            self._host._pet.set_work_item(offer["kind"], offer["label"], "working")
        self._host._input.submitted.emit(prompt, attachments)

    @staticmethod
    def _prompt(action: str, offer: dict) -> str:
        goals = {
            "inspect": i18n.t("workflow_goal_inspect"),
            "summarize": i18n.t("workflow_goal_summarize"),
            "organize": i18n.t("workflow_goal_organize"),
            "remember": i18n.t("workflow_goal_remember"),
            "explain": i18n.t("workflow_goal_explain"),
            "workshop": i18n.t("workflow_goal_workshop"),
        }
        body = goals.get(action, goals["inspect"])
        if offer["text"]:
            body += f"\n\n我交给你的内容：\n{offer['text']}"
        elif offer["paths"]:
            body += "\n\n文件：\n" + "\n".join(offer["paths"])
        return body

    def on_step(self, label: str) -> None:
        if self._active is None:
            return
        lowered = label.lower()
        if any(word in lowered for word in ("read", "search", "recall", "screen", "读取", "搜索", "查看")):
            stage = "reading"
        elif any(word in lowered for word in ("write", "edit", "run", "shell", "act", "写入", "执行", "操作")):
            stage = "acting"
        else:
            stage = "working"
        self._host._pet.set_work_item(self._active.kind, self._active.label, stage)
        if self._active.action == "workshop":
            self._host._workshop.on_step(stage)

    def on_reply(self, raw: str) -> None:
        if self._active is not None:
            self._active.result = " ".join((raw or "").split())[:600]

    def complete(self, ok: bool, context: str = "") -> dict | None:
        session, self._active = self._active, None
        if session is None:
            return None
        self._host._pet.set_work_item(session.kind, session.label, "done" if ok else "failed")
        if not ok:
            if session.action == "workshop":
                self._host._workshop.complete(False, None, session.world_id)
            else:
                QTimer.singleShot(1800, self._host._pet.clear_work_item)
            return None
        title = (i18n.t("workshop_book_title").format(name=session.label)
                 if session.action == "workshop"
                 else f"{i18n.t(f'workflow_{session.action}')} · {session.label}")
        item = keepsakes.add(
            "book" if session.action == "workshop" else session.kind,
            title, session.result or i18n.t("workflow_done"),
            source=session.source, context="workshop" if session.action == "workshop" else context,
        )
        if session.action == "workshop":
            self._host._workshop.complete(True, item, session.world_id)
        journal.add(f"小绯雪完成了「{title}」，留下了一件纪念物")
        shelf = getattr(self._host, "_keepsake_shelf", None)
        if shelf is not None:
            shelf.refresh()
        if session.action != "workshop":
            QTimer.singleShot(2400, self._host._pet.clear_work_item)
        return item
