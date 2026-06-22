"""Full-scene workshop where Xiaofeixue visibly processes documents."""

from __future__ import annotations

import time
import hashlib
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from desktop_pet import i18n
from desktop_pet.pet.fx import make_floating
from desktop_pet.pet.sprite_skin import SpriteAtlasSkin
from desktop_pet.pet.portal_transit import PortalTransit
from desktop_pet.world import WorldObject, WorldStore, get_world


_SIZE = (900, 600)
_ASSET = Path(__file__).resolve().parent.parent / "assets" / "workshop" / "workshop_room.png"
_BOOK_COLORS = ("#b9453f", "#3e8b82", "#d2a33e", "#6379a9", "#8c5f91", "#c66f3d")


class WorkshopWindow(QWidget):
    book_requested = Signal(str)
    archive_requested = Signal()

    def __init__(self, store: WorldStore | None = None) -> None:
        super().__init__()
        make_floating(self)
        self.setFixedSize(*_SIZE)
        self.setMouseTracking(True)
        self._background = QPixmap(str(_ASSET))
        self._skin = SpriteAtlasSkin("xiaofeixue")
        self._store = store or get_world()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._clock = 0.0
        self._stage = "idle"
        self._label = ""
        self._stage_started = time.monotonic()
        self._books: list[WorldObject] = []
        self._book_rects: list[tuple[QRectF, str, str]] = []
        self._slot_rects = [self._slot_rect(index) for index in range(15)]
        self._drawer_rect = QRectF(610, 456, 230, 52)
        self._drag_book_id = ""
        self._drag_start = QPointF()
        self._drag_pos = QPointF()
        self._carrying_book = False
        self._close_rect = QRectF(self.width() - 42, 14, 28, 28)
        self.refresh_books()

    @property
    def stage(self) -> str:
        return self._stage

    def refresh_books(self) -> None:
        self._books = self._store.visible_books()
        self.update()

    def open_library(self, screen) -> None:
        self.refresh_books()
        self.set_stage("idle", "")
        self._place(screen)
        self.show()
        self.raise_()
        self.activateWindow()

    def reveal(self, screen) -> None:
        self._place(screen)
        self.show()
        self.raise_()
        if self._stage != "idle":
            self._timer.start(33)

    def begin_document(self, label: str, screen) -> None:
        self._carrying_book = False
        self.refresh_books()
        self.set_stage("arriving", label)
        self._place(screen)
        self.show()
        self.raise_()
        self._timer.start(33)

    def begin_revisit(self, item: WorldObject, screen) -> None:
        self._carrying_book = True
        self.refresh_books()
        self.set_stage("arriving", item.title)
        self._place(screen)
        self.show()
        self.raise_()
        self._timer.start(33)

    def complete_revisit(self) -> None:
        self.set_stage("returning")

    def set_stage(self, stage: str, label: str | None = None) -> None:
        self._stage = stage
        if label is not None:
            self._label = label
        self._stage_started = time.monotonic()
        if stage == "idle" or not self.isVisible():
            self._timer.stop()
        elif self.isVisible():
            self._timer.start(33)
        self.update()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def complete_document(self, item: dict | None, ok: bool) -> None:
        if item is not None:
            self.refresh_books()
        self.set_stage("returning" if ok else "failed")

    def stop_scene(self) -> None:
        self._timer.stop()
        self.hide()
        self.set_stage("idle", "")

    def _place(self, screen) -> None:
        x = screen.center().x() - self.width() // 2
        y = screen.center().y() - self.height() // 2
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        self.move(x, y)

    def _tick(self) -> None:
        self._clock += 0.033
        self.update()

    def _sprite_state(self) -> str:
        if self._stage == "arriving":
            return "running-right"
        if self._stage == "returning":
            return "running-left"
        if self._stage == "failed":
            return "failed"
        if self._stage in {"reading", "working", "revisiting"}:
            return "read" if self._skin.has_state("read") else "review"
        return "idle"

    def _sprite_rect(self) -> QRectF:
        elapsed = time.monotonic() - self._stage_started
        if self._stage == "arriving":
            p = min(1.0, elapsed / 1.15)
            x = 94 + (365 - 94) * p
        elif self._stage == "returning":
            p = min(1.0, elapsed / 1.30)
            x = 365 - (365 - 94) * p
        elif self._stage == "idle":
            x = 190
        else:
            x = 365
        return QRectF(x, 350, 150, 164)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)
        else:
            painter.fillRect(self.rect(), QColor("#25282b"))
        self._paint_books(painter)
        self._paint_portal(painter)
        self._paint_document(painter)
        self._paint_character(painter)
        self._paint_status(painter)
        self._paint_close(painter)

    def _paint_character(self, painter: QPainter) -> None:
        pixmap = self._skin.frame_pixmap(self._sprite_state(), self._clock)
        if pixmap.isNull():
            return
        target = self._sprite_rect()
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

    def _paint_document(self, painter: QPainter) -> None:
        if self._stage not in {"arriving", "reading", "working", "revisiting", "returning", "failed"}:
            return
        if self._stage in {"arriving", "returning"}:
            sprite = self._sprite_rect()
            rect = QRectF(sprite.right() - 28, sprite.center().y() + 12, 34, 42)
        else:
            rect = QRectF(470, 354, 42, 52)
        if self._carrying_book:
            painter.setPen(QPen(QColor("#4a2827"), 2))
            painter.setBrush(self._project_color(self._label))
            painter.drawRoundedRect(rect, 2, 2)
            painter.setPen(QPen(QColor("#f0d58e"), 2))
            painter.drawLine(int(rect.left() + 7), int(rect.top() + 4),
                             int(rect.left() + 7), int(rect.bottom() - 4))
        else:
            painter.setPen(QPen(QColor("#372f31"), 2))
            painter.setBrush(QColor("#f4efe4"))
            painter.drawRect(rect)
            painter.setPen(QPen(QColor("#b9453f"), 2))
            for offset in (13, 21, 29):
                painter.drawLine(int(rect.left() + 8), int(rect.top() + offset),
                                 int(rect.right() - 7), int(rect.top() + offset))

    def _paint_portal(self, painter: QPainter) -> None:
        if self._stage not in {"arriving", "returning"}:
            return
        elapsed = time.monotonic() - self._stage_started
        duration = 1.15 if self._stage == "arriving" else 1.30
        progress = min(1.0, elapsed / duration)
        direction = "arrival" if self._stage == "arriving" else "departure"
        PortalTransit(direction).draw(painter, QPointF(126, 506), progress, 1.25)

    @staticmethod
    def _slot_rect(index: int) -> QRectF:
        row, col = divmod(index, 5)
        baselines = (247, 348, 450)
        return QRectF(613 + col * 39, baselines[row] - 48, 31, 48)

    @staticmethod
    def _project_color(project_key: str) -> QColor:
        digest = hashlib.sha1((project_key or "misc").encode("utf-8")).digest()[0]
        return QColor(_BOOK_COLORS[digest % len(_BOOK_COLORS)])

    def _draw_book(self, painter: QPainter, rect: QRectF, item: WorldObject, floating: bool = False) -> None:
        color = self._project_color(item.project_key)
        spine = QRectF(rect.center().x() - 9, rect.bottom() - 44, 18, 44)
        if floating:
            spine = QRectF(rect.center().x() - 11, rect.center().y() - 25, 22, 50)
        painter.setPen(QPen(color.darker(155), 1))
        painter.setBrush(color)
        painter.drawRect(spine)
        painter.setPen(QPen(QColor(246, 231, 184, 215), 2))
        painter.drawLine(int(spine.left() + 3), int(spine.top() + 8),
                         int(spine.right() - 3), int(spine.top() + 8))
        painter.setPen(QPen(QColor(255, 255, 255, 95), 1))
        painter.drawLine(int(spine.left() + 3), int(spine.top() + 13),
                         int(spine.left() + 3), int(spine.bottom() - 4))

    def _paint_books(self, painter: QPainter) -> None:
        self._book_rects.clear()
        for item in self._books:
            if item.slot is None or not 0 <= item.slot < len(self._slot_rects):
                continue
            rect = self._slot_rects[item.slot]
            if item.id != self._drag_book_id:
                self._draw_book(painter, rect, item)
            self._book_rects.append((rect, item.id, item.title))
        if self._drag_book_id:
            item = next((book for book in self._books if book.id == self._drag_book_id), None)
            if item is not None:
                self._draw_book(painter, QRectF(self._drag_pos.x() - 18, self._drag_pos.y() - 26, 36, 52), item, True)
        archived = len(self._store.archived())
        if archived:
            painter.setPen(QPen(QColor("#e7d39b"), 1))
            painter.setBrush(QColor(24, 25, 27, 175))
            painter.drawRoundedRect(QRectF(730, 474, 82, 25), 4, 4)
            painter.drawText(QRectF(730, 474, 82, 25), Qt.AlignmentFlag.AlignCenter,
                             i18n.t("workshop_archive_count").format(n=archived))

    def _paint_status(self, painter: QPainter) -> None:
        if self._stage == "idle" and not self._label:
            return
        band = QRectF(0, self.height() - 58, self.width(), 58)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 22, 24, 205))
        painter.drawRect(band)
        painter.setPen(QColor("#f5f2eb"))
        font = painter.font()
        font.setPixelSize(16)
        painter.setFont(font)
        stage_text = i18n.t("workshop_stage_" + self._stage)
        painter.drawText(22, self.height() - 31, stage_text)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor("#d8d3c9"))
        painter.drawText(22, self.height() - 12, self._label[:70])
        if self._stage in {"reading", "working", "revisiting"}:
            sweep = int((self._clock * 95) % (self.width() - 44))
            painter.setPen(QPen(QColor("#63c7bd"), 3))
            painter.drawLine(22, self.height() - 3, 22 + sweep, self.height() - 3)

    def _paint_close(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(245, 242, 235, 220), 2))
        painter.setBrush(QColor(25, 26, 28, 165))
        painter.drawRoundedRect(self._close_rect, 5, 5)
        pad = 8
        painter.drawLine(int(self._close_rect.left() + pad), int(self._close_rect.top() + pad),
                         int(self._close_rect.right() - pad), int(self._close_rect.bottom() - pad))
        painter.drawLine(int(self._close_rect.right() - pad), int(self._close_rect.top() + pad),
                         int(self._close_rect.left() + pad), int(self._close_rect.bottom() - pad))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_book_id:
            self._drag_pos = event.position()
            self.update()
            event.accept()
            return
        title = next((title for rect, _item_id, title in self._book_rects
                      if rect.contains(event.position())), "")
        if self._drawer_rect.contains(event.position()):
            title = i18n.t("workshop_archive_hint")
        self.setToolTip(title or (i18n.t("workshop_close_hint") if self._close_rect.contains(event.position()) else ""))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if self._close_rect.contains(event.position()):
            self.hide()
            event.accept()
            return
        if self._drawer_rect.contains(event.position()):
            self.archive_requested.emit()
            event.accept()
            return
        for rect, item_id, _title in self._book_rects:
            if rect.contains(event.position()) and item_id:
                self._drag_book_id = item_id
                self._drag_start = event.position()
                self._drag_pos = event.position()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._drag_book_id:
            super().mouseReleaseEvent(event)
            return
        item_id, self._drag_book_id = self._drag_book_id, ""
        distance = event.position() - self._drag_start
        if distance.x() * distance.x() + distance.y() * distance.y() <= 25:
            self.book_requested.emit(item_id)
        else:
            slot = next((index for index, rect in enumerate(self._slot_rects)
                         if rect.adjusted(-5, -5, 5, 5).contains(event.position())), None)
            if slot is not None:
                self._store.move(item_id, slot)
                self.refresh_books()
        self.update()
        event.accept()
