# author: bdth
# email: 2074055628@qq.com
# 玩具球 丢出去弹 滚到桌宠那它来接

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from desktop_pet.eyes import capture
from desktop_pet.pet.fx import make_floating

_SIZE = 44
_R = 16.0
_GRAVITY = 2600.0
_BOUNCE = 0.62


class BallWindow(QWidget):
    caught = Signal()
    stopped = Signal()

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.resize(_SIZE, _SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._t = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._spin = 0.0
        self._bounces = 0
        self._pet_rect = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def closeEvent(self, event) -> None:
        # 注销自家窗口登记 别让死句柄堆在 capture._own_hwnds 里被 Windows 回收复用误伤别家窗口
        capture.unregister_own_window(int(self.winId()))
        super().closeEvent(event)

    def throw_from_top(self, screen, pet_rect) -> None:
        """从屏幕上方丢下来 朝宠物那边滚"""
        self._screen = screen
        self._pet_rect = pet_rect
        x = random.randint(screen.left() + 100, screen.right() - 100)
        self.move(x, screen.top() - _SIZE)
        side = 1 if pet_rect.center().x() > x else -1
        self._vx = side * random.uniform(180, 320)
        self._vy = random.uniform(60, 160)
        self._bounces = 0
        self.show()
        self._timer.start(16)

    def _tick(self) -> None:
        dt = 0.016
        self._t += dt
        scr = self._screen
        self._vy += _GRAVITY * dt
        self._vx *= 0.999
        x = self.x() + self._vx * dt
        y = self.y() + self._vy * dt
        self._spin += self._vx * dt * 0.55
        floor = scr.bottom() - _SIZE
        if x < scr.left():
            x = scr.left()
            self._vx = abs(self._vx) * _BOUNCE
        elif x > scr.right() - _SIZE:
            x = scr.right() - _SIZE
            self._vx = -abs(self._vx) * _BOUNCE
        if y >= floor:
            y = floor
            self._bounces += 1
            self._vy = -abs(self._vy) * _BOUNCE
            if abs(self._vy) < 240 or self._bounces > 6:
                self._timer.stop()
                self.close()
                self.stopped.emit()
                return
        self.move(int(x), int(y))
        # 滚进宠物怀里就算接到
        if self._pet_rect is not None and self._pet_rect.adjusted(-10, -10, 10, 10).contains(int(x + _SIZE / 2), int(y + _SIZE / 2)):
            self._timer.stop()
            self.close()
            self.caught.emit()
            return
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(_SIZE / 2, _SIZE / 2)
        painter.rotate(self._spin)
        grad = QRadialGradient(QPointF(-4, -5), _R * 2)
        grad.setColorAt(0.0, QColor(150, 140, 196))
        grad.setColorAt(1.0, QColor(92, 84, 128))
        painter.setPen(QPen(QColor(40, 38, 48), 1.6))
        painter.setBrush(grad)
        painter.drawEllipse(QPointF(0, 0), _R, _R)
        # 球面两道弧纹 转起来才看得出滚
        pen = QPen(QColor(40, 38, 48, 170))
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(int(-_R), int(-_R * 0.55), int(_R * 2), int(_R * 1.1), 0, 180 * 16)
        painter.drawArc(int(-_R * 0.55), int(-_R), int(_R * 1.1), int(_R * 2), 90 * 16, 180 * 16)
        # 高光
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(235, 230, 250, 190))
        painter.drawEllipse(QPointF(-5, -6), 3.4, 3.4)
