"""Compact desktop overlays used by the memory-fishing game."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from desktop_pet import i18n
from desktop_pet.pet.fx import make_floating, place_beside_pet


class FishingGauge(QWidget):
    reeled = Signal(float)
    timed_out = Signal()

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setFixedSize(320, 96)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._started = 0.0
        self._duration = 0.0
        self._speed = 0.0
        self._target = 0.5
        self._width = 0.2
        self._marker = 0.0
        self._round = 1
        self._score = 0

    def begin(self, round_no: int, score: int, target: float, width: float,
              speed: float, duration: float) -> None:
        self._round = round_no
        self._score = score
        self._target = target
        self._width = width
        self._speed = speed
        self._duration = duration
        self._started = time.monotonic()
        self._marker = 0.0
        self._timer.start(16)
        self.show()
        self.raise_()
        self.update()

    def stop_round(self) -> None:
        self._timer.stop()
        self.hide()

    def marker_position(self) -> float:
        return self._marker

    def follow(self, pet, screen) -> None:
        place_beside_pet(self, pet, screen, prefer="left", gap=12)

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._started
        if elapsed >= self._duration:
            self.stop_round()
            self.timed_out.emit()
            return
        phase = (elapsed * self._speed) % 2.0
        self._marker = phase if phase <= 1.0 else 2.0 - phase
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._timer.isActive():
            marker = self._marker
            self.stop_round()
            self.reeled.emit(marker)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(251, 250, 247, 245))
        painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 7, 7)
        painter.setPen(QPen(QColor("#373443")))
        painter.drawText(14, 23, i18n.t("fishing_round").format(n=self._round, score=self._score))
        painter.setPen(QPen(QColor("#777181")))
        painter.drawText(14, 43, i18n.t("fishing_reel_hint"))

        bar = QRectF(16, 58, self.width() - 32, 18)
        painter.setPen(QPen(QColor("#d4d0dc"), 1))
        painter.setBrush(QColor("#ece9f0"))
        painter.drawRoundedRect(bar, 5, 5)
        target = QRectF(
            bar.left() + (self._target - self._width / 2) * bar.width(),
            bar.top(), self._width * bar.width(), bar.height(),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#78bf8b"))
        painter.drawRoundedRect(target, 4, 4)
        perfect = QRectF(target.center().x() - target.width() / 8, target.top(),
                         target.width() / 4, target.height())
        painter.setBrush(QColor("#f2c14e"))
        painter.drawRect(perfect)
        marker_x = bar.left() + self._marker * bar.width()
        painter.setPen(QPen(QColor("#5746b3"), 3))
        painter.drawLine(int(marker_x), int(bar.top() - 5), int(marker_x), int(bar.bottom() + 5))


class FishingSummary(QWidget):
    view_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setFixedSize(390, 300)
        self.setStyleSheet("""
            QWidget { background: #fbfaf7; color: #302f39; font-family: 'Microsoft YaHei UI'; }
            QListWidget { background: white; border: 1px solid #dedbe6; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 7px; }
            QListWidget::item:selected { background: #ece8ff; color: #4937a8; }
            QPushButton { background: #6f5bd3; color: white; border: 0; border-radius: 6px; padding: 8px; }
            QPushButton:disabled { background: #c9c5d8; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 17px; font-weight: 600;")
        root.addWidget(self._title)
        self._score = QLabel()
        root.addWidget(self._score)
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._selected)
        root.addWidget(self._list, 1)
        self._view = QPushButton(i18n.t("fishing_view_memory"))
        self._view.clicked.connect(self._view_current)
        buttons = QHBoxLayout()
        self._close = QPushButton(i18n.t("fishing_close"))
        self._close.clicked.connect(self.hide)
        buttons.addWidget(self._close)
        buttons.addWidget(self._view)
        root.addLayout(buttons)

    def show_result(self, score: int, best: int, new_best: bool, catches: list[dict], pet, screen) -> None:
        self._title.setText(i18n.t("fishing_summary_title"))
        key = "fishing_summary_best" if new_best else "fishing_summary"
        self._score.setText(i18n.t(key).format(score=score, best=best))
        self._view.setText(i18n.t("fishing_view_memory"))
        self._close.setText(i18n.t("fishing_close"))
        self._list.clear()
        for catch in catches:
            item = QListWidgetItem(catch.get("title", ""))
            item.setData(Qt.ItemDataRole.UserRole, catch)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._view.setEnabled(False)
        place_beside_pet(self, pet, screen, prefer="left", gap=12)
        self.show()
        self.raise_()
        self.activateWindow()

    def _selected(self, current, _previous) -> None:
        entry = current.data(Qt.ItemDataRole.UserRole) if current is not None else {}
        self._view.setEnabled(bool(entry.get("id")))

    def _view_current(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        item_id = str(entry.get("id", ""))
        if item_id:
            self.hide()
            self.view_requested.emit(item_id)
