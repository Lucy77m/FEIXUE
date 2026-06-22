"""Orchestrate document and revisit trips between desktop and workshop."""

from __future__ import annotations

import re

from PySide6.QtCore import QObject, QTimer, Slot

from desktop_pet import i18n, keepsakes
from desktop_pet.pet.workshop import WorkshopWindow
from desktop_pet.world import WorldObject, WorldStore, get_world


class WorkshopCtrl(QObject):
    def __init__(self, host, store: WorldStore | None = None) -> None:
        super().__init__()
        self._host = host
        self._store = store or get_world()
        self._store.migrate_keepsakes()
        self._window = WorkshopWindow(self._store)
        from desktop_pet.eyes import capture
        capture.register_own_window(int(self._window.winId()))
        self._window.book_requested.connect(self._open_book)
        self._window.archive_requested.connect(self._open_archive)
        self._active = False
        self._mode = ""
        self._session = 0
        self._world_id = ""
        self._label = ""
        self._pending_stage = "reading"
        self._pet_was_visible = False
        self._waiting_ai = False
        self._discard_revisit_reply = False
        self._used_ai = False
        self._revisit_reply = ""
        self._pending_revisit_id = ""

    def is_active(self) -> bool:
        return self._active

    def begin(self, label: str, source: str) -> str:
        if self._active:
            return ""
        item = self._store.create_reading(label, source)
        if not self._start_departure(item, "document"):
            self._store.interrupt(item.id)
            return ""
        return item.id

    def _start_departure(self, item: WorldObject, mode: str) -> bool:
        self._active = True
        self._mode = mode
        self._session += 1
        session = self._session
        self._world_id = item.id
        self._label = item.title
        self._pending_stage = "reading"
        pet = self._host._pet
        self._pet_was_visible = pet.isVisible()
        pet.wake()
        payload = {"kind": "book" if mode == "revisit" else "file", "label": item.title,
                   "stage": "received"}
        started = pet.begin_portal_departure(
            payload,
            midpoint=lambda: self._enter_workshop(session),
            finished=lambda: self._desktop_departed(session),
        )
        if not started:
            self._active = False
            self._mode = ""
            self._world_id = ""
        return started

    def _enter_workshop(self, session: int) -> None:
        if not self._current(session):
            return
        item = self._store.get(self._world_id)
        if item is None:
            self.cancel_transit()
            return
        if self._mode == "revisit":
            self._window.begin_revisit(item, self._screen())
        else:
            self._window.begin_document(self._label, self._screen())
        QTimer.singleShot(1150, lambda: self._settle_at_desk(session))

    def _desktop_departed(self, session: int) -> None:
        if self._current(session):
            self._host._pet.hide()

    def _settle_at_desk(self, session: int) -> None:
        if not self._current(session):
            return
        if self._mode == "revisit":
            self._window.set_stage("revisiting", self._label)
            QTimer.singleShot(2300, lambda: self._finish_revisit_reading(session))
        else:
            self._window.set_stage(self._pending_stage, self._label)

    def on_step(self, stage: str) -> None:
        if not self._active or self._mode != "document":
            return
        self._pending_stage = "reading" if stage == "reading" else "working"
        if self._window.stage != "arriving":
            self._window.set_stage(self._pending_stage, self._label)

    def complete(self, ok: bool, item: dict | None, world_id: str = "") -> None:
        if not self._active or self._mode != "document" or (world_id and world_id != self._world_id):
            return
        if ok and item is not None:
            self._store.complete(self._world_id, str(item.get("detail", "")), str(item.get("id", "")))
        else:
            self._store.interrupt(self._world_id)
        self._window.complete_document(item, ok)
        session = self._session
        QTimer.singleShot(1350 if ok else 1050, lambda: self._leave_workshop(session, ok))

    def begin_revisit(self, item: WorldObject, use_ai: bool, context: str) -> bool:
        if self._active or self._store.carry(item.id) is None:
            return False
        use_ai = use_ai and not self._discard_revisit_reply
        self._waiting_ai = use_ai
        self._used_ai = use_ai
        self._revisit_reply = ""
        if not self._start_departure(item, "revisit"):
            self._store.reshelve(item.id)
            return False
        if use_ai:
            safe = i18n.t("workshop_revisit_ai_prompt").format(
                title=item.title[:120],
                summary=item.summary[:700],
                context=context[:120],
            )
            self._host.request_proactive.emit("workshop_revisit", safe)
            session = self._session
            QTimer.singleShot(20_000, lambda: self._ai_timeout(session))
        else:
            self._revisit_reply = self._local_revisit(item)
        return True

    def accept_revisit_reply(self, raw: str) -> bool:
        if self._discard_revisit_reply:
            self._discard_revisit_reply = False
            return True
        if not self._active or self._mode != "revisit" or not self._waiting_ai:
            return False
        self._waiting_ai = False
        text = " ".join(re.sub(r"^\[[^\]]+\]\s*", "", raw or "").split())
        item = self._store.get(self._world_id)
        if text:
            sentences = [part for part in re.split(r"(?<=[。！？.!?])\s*", text) if part]
            self._revisit_reply = "".join(sentences[:2])[:360]
        else:
            self._used_ai = False
            self._revisit_reply = self._local_revisit(item)
        return True

    def _ai_timeout(self, session: int) -> None:
        if not self._current(session) or not self._waiting_ai:
            return
        self._waiting_ai = False
        self._discard_revisit_reply = True
        self._used_ai = False
        self._revisit_reply = self._local_revisit(self._store.get(self._world_id))

    def _finish_revisit_reading(self, session: int) -> None:
        if not self._current(session):
            return
        if self._waiting_ai:
            QTimer.singleShot(500, lambda: self._finish_revisit_reading(session))
            return
        self._window.complete_revisit()
        QTimer.singleShot(1300, lambda: self._leave_workshop(session, True))

    def _leave_workshop(self, session: int, ok: bool) -> None:
        if not self._current(session):
            return
        self._window.stop_scene()
        payload = {"kind": "book" if ok else "file", "label": self._label,
                   "stage": "done" if ok else "failed"}
        pet = self._host._pet
        pet.show()
        pet.raise_()
        if not pet.begin_portal_arrival(payload, lambda: self._finish_desktop_return(session, ok)):
            self._finish_desktop_return(session, ok)

    def _finish_desktop_return(self, session: int, ok: bool) -> None:
        if not self._current(session):
            return
        mode, item_id = self._mode, self._world_id
        if mode == "revisit":
            self._store.reshelve(item_id)
            self._store.record_revisit(item_id, self._used_ai)
            self._pending_revisit_id = item_id
            message = self._revisit_reply or self._local_revisit(self._store.get(item_id))
        else:
            message = i18n.t("workshop_returned" if ok else "workshop_failed")
        self._active = False
        self._mode = ""
        self._world_id = ""
        if self._waiting_ai:
            self._discard_revisit_reply = True
        self._waiting_ai = False
        if self._pet_was_visible and self._host._shown:
            pet = self._host._pet
            pet.show()
            pet.raise_()
            if ok:
                pet.celebrate()
            else:
                pet.slump()
            thought = getattr(self._host, "_thought", None)
            if thought is not None:
                thought.pop(message, pet)
            QTimer.singleShot(2600, pet.clear_work_item)
        elif not self._host._shown:
            self._host._pet.hide()

    def consume_pending_revisit(self) -> bool:
        item_id, self._pending_revisit_id = self._pending_revisit_id, ""
        if not item_id:
            return False
        item = self._store.get(item_id)
        if item is not None and item.origin_keepsake_id:
            self._host._open_keepsake(item.origin_keepsake_id)
        return True

    def open_library(self) -> None:
        self._store.migrate_keepsakes()
        if self._active:
            self._window.reveal(self._screen())
        else:
            self._window.open_library(self._screen())

    def cancel_transit(self) -> None:
        self._session += 1
        mode, item_id, was_active = self._mode, self._world_id, self._active
        self._active = False
        self._mode = ""
        self._world_id = ""
        if self._waiting_ai:
            self._discard_revisit_reply = True
        self._waiting_ai = False
        self._window.stop_scene()
        self._host._pet.cancel_portal(clear_payload=True)
        if was_active and item_id:
            if mode == "revisit":
                self._store.reshelve(item_id)
            else:
                self._store.interrupt(item_id)
        if was_active and self._pet_was_visible and self._host._shown:
            self._host._pet.show()
            self._host._pet.raise_()

    def stop(self) -> None:
        self.cancel_transit()

    @Slot(str)
    def _open_book(self, world_id: str) -> None:
        item = self._store.get(world_id)
        if item is None or not item.origin_keepsake_id or keepsakes.get(item.origin_keepsake_id) is None:
            return
        self._window.hide()
        self._host._open_keepsake(item.origin_keepsake_id)

    @Slot()
    def _open_archive(self) -> None:
        self._window.hide()
        self._host._open_keepsake("")

    def _current(self, session: int) -> bool:
        return self._active and session == self._session

    @staticmethod
    def _local_revisit(item: WorldObject | None) -> str:
        if item is None:
            return i18n.t("workshop_revisit_fallback")
        summary = " ".join(item.summary.split())[:150] or i18n.t("workshop_revisit_empty")
        return i18n.t("workshop_revisit_local").format(title=item.title, summary=summary)

    def _screen(self):
        return (self._host._app.screenAt(self._host._pet.frameGeometry().center())
                or self._host._app.primaryScreen()).availableGeometry()
