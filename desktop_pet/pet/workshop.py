"""Full-scene workshop where Xiaofeixue visibly processes documents."""

from __future__ import annotations

import math
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
        self._objects: list[WorldObject] = []
        self._books: list[WorldObject] = []
        self._book_rects: list[tuple[QRectF, str, str]] = []
        self._slot_rects = [self._slot_rect(index) for index in range(20)]
        self._drag_book_id = ""
        self._drag_start = QPointF()
        self._drag_pos = QPointF()
        self._carrying_book = False
        self._close_rect = QRectF(self.width() - 42, 14, 28, 28)
        self._weather_kind = ""
        self.refresh_books()

    @property
    def stage(self) -> str:
        return self._stage

    def refresh_books(self) -> None:
        self._objects = self._store.visible_objects()
        self._books = [o for o in self._objects if o.kind == "book"]
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

    def set_weather_kind(self, kind: str) -> None:
        """由 companion 调用 设置窗外天气"""
        if kind != self._weather_kind:
            self._weather_kind = kind
            if self.isVisible():
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
        self._paint_window_weather(painter)
        self._paint_books(painter)
        self._paint_keepsakes(painter)
        self._paint_dreams(painter)
        self._paint_mementos(painter)
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

    def _paint_window_weather(self, painter: QPainter) -> None:
        """在窗户区域叠加记忆天气微缩视觉"""
        if not self._weather_kind or self._weather_kind == "clear":
            return
        # 窗户区域：背景图左上角
        wx, wy, ww, wh = 40, 35, 155, 115
        painter.save()
        painter.setClipRect(QRectF(wx, wy, ww, wh))
        t = self._clock
        if self._weather_kind == "rain":
            painter.setPen(QPen(QColor(136, 153, 187, 100), 1.5))
            for i in range(6):
                x = wx + 20 + i * 22 + math.sin(t * 2 + i) * 3
                y = wy + (t * 40 + i * 18) % wh
                painter.drawLine(QPointF(x, y), QPointF(x + 2, y + 10))
        elif self._weather_kind == "fog":
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(3):
                alpha = int(30 + 20 * math.sin(t * 0.8 + i * 2))
                painter.setBrush(QColor(180, 180, 170, alpha))
                cx = wx + 40 + i * 40 + math.sin(t * 0.3 + i) * 10
                cy = wy + 50 + math.cos(t * 0.5 + i) * 8
                painter.drawEllipse(QPointF(cx, cy), 25, 12)
        elif self._weather_kind == "stars":
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(5):
                alpha = int(100 + 80 * math.sin(t * 2 + i * 1.3))
                painter.setBrush(QColor(255, 196, 82, max(0, alpha)))
                sx = wx + 25 + (i * 31) % ww
                sy = wy + 20 + (i * 17) % (wh - 30)
                r = 2 + math.sin(t * 3 + i) * 0.8
                painter.drawEllipse(QPointF(sx, sy), r, r)
        elif self._weather_kind == "warm":
            painter.setPen(Qt.PenStyle.NoBrush)
            painter.setPen(QPen(QColor(240, 160, 128, 60), 1))
            painter.setBrush(QColor(240, 160, 128, 25))
            painter.drawEllipse(QPointF(wx + ww / 2, wy + wh / 2), 40, 30)
        elif self._weather_kind == "static":
            painter.setPen(QPen(QColor(200, 200, 200, 70), 1))
            for i in range(4):
                x = wx + 30 + i * 28 + random.uniform(-5, 5)
                y = wy + 40 + random.uniform(-10, 10)
                painter.drawLine(QPointF(x, y), QPointF(x + 8, y + random.uniform(-3, 3)))
        elif self._weather_kind == "gentle":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(136, 196, 160, 40))
            for i in range(3):
                cx = wx + 50 + i * 30 + math.sin(t * 0.4 + i) * 5
                cy = wy + 60 + math.cos(t * 0.3 + i) * 5
                painter.drawEllipse(QPointF(cx, cy), 6, 6)
        painter.restore()

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
        baselines = (230, 318, 406, 494)
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
        for item in self._objects:
            if item.kind != "book":
                continue
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

    # ── 信物绘制 ──────────────────────────────────────────

    _KEEPSAKE_COLORS = {
        "file": "#7eb8da", "image": "#da7eb8", "url": "#b8da7e",
        "text": "#dab87e", "default": "#c4a0e0",
    }

    def _paint_keepsakes(self, painter: QPainter) -> None:
        for item in self._objects:
            if item.kind != "keepsake" or item.slot is None:
                continue
            if not 0 <= item.slot < len(self._slot_rects):
                continue
            rect = self._slot_rects[item.slot]
            cx, cy = rect.center().x(), rect.center().y()
            color = QColor(self._KEEPSAKE_COLORS.get(
                (item.source.split(":")[0] if item.source else ""), self._KEEPSAKE_COLORS["default"]))
            painter.setPen(QPen(QColor("#d4a840"), 1.5))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(cx, cy), 9, 9)
            painter.setPen(QPen(QColor("#f0d58e"), 1))
            painter.drawLine(int(cx - 3), int(cy), int(cx + 3), int(cy))
            painter.drawLine(int(cx), int(cy - 3), int(cx), int(cy + 3))
            self._book_rects.append((rect, item.id, item.title))

    # ── 梦境碎片绘制 ──────────────────────────────────────

    def _paint_dreams(self, painter: QPainter) -> None:
        for item in self._objects:
            if item.kind != "dream" or item.slot is None:
                continue
            if not 0 <= item.slot < len(self._slot_rects):
                continue
            rect = self._slot_rects[item.slot]
            cx, cy = rect.center().x(), rect.center().y()
            alpha_f = (math.sin(self._clock * 1.5 + item.slot * 0.7) + 1) * 0.5
            alpha = int(40 + 110 * alpha_f)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(180, 170, 210, alpha))
            for dx, dy, r in [(-4, -3, 4), (3, -5, 3), (0, 1, 5), (-6, 2, 3)]:
                painter.drawEllipse(QPointF(cx + dx, cy + dy), r, r)
            self._book_rects.append((rect, item.id, item.title))

    # ── 里程碑纪念品绘制 ──────────────────────────────────

    def _paint_mementos(self, painter: QPainter) -> None:
        for item in self._objects:
            if item.kind != "memento" or item.slot is None:
                continue
            if not 0 <= item.slot < len(self._slot_rects):
                continue
            rect = self._slot_rects[item.slot]
            cx, cy = rect.center().x(), rect.center().y()
            painter.setPen(QPen(QColor("#d4a040"), 2))
            painter.setBrush(QColor("#f5e6b8"))
            painter.drawEllipse(QPointF(cx, cy), 10, 10)
            painter.setPen(QPen(QColor("#8b6914"), 1.5))
            painter.drawEllipse(QPointF(cx, cy), 6, 6)
            painter.setPen(QPen(QColor("#d4a040"), 1))
            for i in range(4):
                ang = i * math.tau / 4
                painter.drawLine(
                    QPointF(cx + math.cos(ang) * 3, cy + math.sin(ang) * 3),
                    QPointF(cx + math.cos(ang) * 8, cy + math.sin(ang) * 8),
                )
            self._book_rects.append((rect, item.id, item.title))

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
        title = ""
        hit_id = ""
        for rect, item_id, item_title in self._book_rects:
            if rect.contains(event.position()):
                title = item_title
                hit_id = item_id
                break
        if hit_id:
            obj = self._store.get(hit_id)
            if obj is not None:
                if obj.kind == "keepsake":
                    title = i18n.t("workshop_keepsake_tip").format(title=title)
                elif obj.kind == "dream":
                    title = i18n.t("workshop_dream_tip")
                elif obj.kind == "memento":
                    title = i18n.t("workshop_memento_tip").format(title=title)
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
