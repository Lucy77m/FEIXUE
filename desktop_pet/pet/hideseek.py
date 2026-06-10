# author: bdth
# email: 2074055628@qq.com
# 捉迷藏的尾巴尖 藏起来只露这一截 点到算找到

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from desktop_pet.pet.fx import make_floating

_SIZE = 52
_TIMEOUT = 180.0
_INK = QColor(40, 38, 48)


class TailWindow(QWidget):
    found = Signal()
    gave_up = Signal()

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.resize(_SIZE, _SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self._born = time.time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def appear_at(self, x: int, y: int) -> None:
        self._born = time.time()
        self.move(int(x - _SIZE / 2), int(y - _SIZE / 2))
        self.show()
        self._timer.start(33)

    def _tick(self) -> None:
        self._t += 0.033
        if time.time() - self._born > _TIMEOUT:
            self._timer.stop()
            self.close()
            self.gave_up.emit()
            return
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._timer.stop()
        self.close()
        self.found.emit()
        event.accept()

    def stop(self) -> None:
        self._timer.stop()
        self.close()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(_SIZE / 2, _SIZE * 0.82)
        sway = math.sin(self._t * 2.4) * 9
        # 一截墨色小尾巴 从底下探出来 轻轻摇
        pen = QPen(_INK)
        pen.setWidthF(7.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x1 = sway * 0.4
        y1 = -14.0
        x2 = sway
        y2 = -26.0
        # 两段折出弯尾
        painter.drawLine(QPointF(0, 4), QPointF(x1, y1))
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        # 尾尖小球
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_INK)
        painter.drawEllipse(QPointF(x2, y2), 5.4, 5.4)
        # 尖上一点高光
        painter.setBrush(QColor(150, 142, 180, 200))
        painter.drawEllipse(QPointF(x2 - 1.5, y2 - 1.5), 1.6, 1.6)
