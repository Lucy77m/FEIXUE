# author: bdth
# email: 2074055628@qq.com
# 垃圾虫 在桌宠旁爬 点死触发真清理

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from desktop_pet.pet.fx import make_floating

_SIZE = 64
_TICK_MS = 33
_WANDER = 90  # 出生点附近活动半径
_LIFE_S = 600.0  # 没人理这么久就溜了
_INK = QColor(40, 38, 48)


class BugWindow(QWidget):
    squished = Signal()
    escaped = Signal()

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.resize(_SIZE, _SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self._born = time.time()
        self._phase = random.uniform(0, math.tau)
        self._home = QPointF()
        self._pos = QPointF()
        self._vel = QPointF(0, 0)
        self._heading = random.uniform(0, math.tau)
        self._squish = -1.0  # >=0 表示死亡动画进行中
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def spawn_near(self, x: int, y: int, screen) -> None:
        """在某点附近落地开爬"""
        self._home = QPointF(x, y)
        self._pos = QPointF(x, y)
        self._born = time.time()
        self._screen = screen
        self.move(int(x - _SIZE / 2), int(y - _SIZE / 2))
        self.show()
        self._timer.start(_TICK_MS)

    def _tick(self) -> None:
        dt = _TICK_MS / 1000.0
        self._t += dt
        if self._squish >= 0:
            self._squish += dt
            if self._squish > 0.55:
                self._timer.stop()
                self.close()
                self.squished.emit()
                return
            self.update()
            return
        if time.time() - self._born > _LIFE_S:
            self._timer.stop()
            self.close()
            self.escaped.emit()
            return
        # 走走停停的布朗爬行 拴在出生点附近
        if random.random() < 0.03:
            self._heading += random.uniform(-1.6, 1.6)
        speed = 26.0 * (0.5 + 0.5 * math.sin(self._t * 1.7 + self._phase))  # 一阵一阵地爬
        self._pos += QPointF(math.cos(self._heading) * speed * dt, math.sin(self._heading) * speed * dt)
        off = self._pos - self._home
        dist = math.hypot(off.x(), off.y())
        if dist > _WANDER:  # 出圈掉头回家
            self._heading = math.atan2(-off.y(), -off.x()) + random.uniform(-0.5, 0.5)
        scr = getattr(self, "_screen", None)
        if scr is not None:
            self._pos.setX(max(scr.left() + _SIZE, min(self._pos.x(), scr.right() - _SIZE)))
            self._pos.setY(max(scr.top() + _SIZE, min(self._pos.y(), scr.bottom() - _SIZE)))
        self.move(int(self._pos.x() - _SIZE / 2), int(self._pos.y() - _SIZE / 2))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._squish < 0:
            self._squish = 0.0
        event.accept()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(_SIZE / 2, _SIZE / 2)
        if self._squish >= 0:
            self._paint_squish(painter)
            return
        painter.rotate(math.degrees(self._heading) + 90)  # 头朝前进方向
        wig = math.sin(self._t * 14 + self._phase)
        # 六条腿 两侧交替划
        pen = QPen(_INK)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for side in (-1, 1):
            for i in range(3):
                y = -7 + i * 7
                sw = wig if (i % 2 == 0) == (side > 0) else -wig
                x1, y1 = side * 7, y
                x2, y2 = side * (13 + 2 * sw), y + 3 + 2.5 * sw
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        # 触角
        for side in (-1, 1):
            painter.drawLine(QPointF(side * 3, -12), QPointF(side * (6 + wig * 1.5), -18))
        # 身体两节
        painter.setPen(QPen(_INK, 1.6))
        painter.setBrush(QColor(86, 80, 104))
        painter.drawEllipse(QPointF(0, 4), 8.0, 10.0)
        painter.setBrush(QColor(60, 56, 76))
        painter.drawEllipse(QPointF(0, -7), 6.5, 7.0)
        # 背上一道纹
        painter.setPen(QPen(QColor(140, 132, 168), 1.2))
        painter.drawLine(QPointF(0, -2), QPointF(0, 11))

    def _paint_squish(self, painter: QPainter) -> None:
        """被点死 压扁加溅墨"""
        p = min(1.0, self._squish / 0.55)
        # 压扁的身体
        alpha = max(0, int(255 * (1 - p * 1.1)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 64, 90, alpha))
        painter.drawEllipse(QPointF(0, 2), 10 + 6 * p, max(2.0, 9 * (1 - p)))
        # 八方溅墨点
        painter.setBrush(QColor(60, 56, 76, max(0, int(220 * (1 - p)))))
        for k in range(8):
            ang = k * math.pi / 4 + 0.3
            r = 6 + 16 * p
            painter.drawEllipse(QPointF(math.cos(ang) * r, math.sin(ang) * r + 2),
                                2.4 * (1 - p * 0.5), 2.4 * (1 - p * 0.5))
