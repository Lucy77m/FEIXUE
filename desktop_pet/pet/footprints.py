# 墨水脚印层 心情好走过会留脚印 几秒淡掉 节日换花纹

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_LIFE = 4.5
_MAX = 24
_INK = QColor(52, 48, 66)


class FootprintLayer(QWidget):
    """全屏穿透层 只负责画脚印"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._steps: list[list] = []  # x y rot kind born left底
        self._left = False  # 左右脚交替
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _ensure_win32_passthrough(self) -> None:
        """win层面也设穿透 保险"""
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x20 | 0x80000)  # TRANSPARENT LAYERED
        except Exception:
            pass

    def add(self, x: int, y: int, heading: float, kind: str = "paw", life_s: float | None = None) -> None:
        """落一个脚印"""
        if not self.isVisible():
            scr = self.screen()
            if scr is None:
                return
            self.setGeometry(scr.virtualGeometry())
            self.show()
            self._ensure_win32_passthrough()
            self._timer.start(80)
        self._left = not self._left
        self._steps.append([x, y, heading, kind, time.time(), self._left, life_s or _LIFE])
        if len(self._steps) > _MAX:
            self._steps.pop(0)

    def _tick(self) -> None:
        now = time.time()
        self._steps = [s for s in self._steps if now - s[4] < (s[6] if len(s) > 6 else _LIFE)]
        if not self._steps:
            self._timer.stop()
            self.hide()
            return
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.time()
        origin = self.geometry().topLeft()
        for step in self._steps:
            x, y, rot, kind, born, left = step[:6]
            life_s = step[6] if len(step) > 6 else _LIFE
            age = (now - born) / life_s
            alpha = max(0, int(150 * (1 - age)))
            if alpha <= 0:
                continue
            painter.save()
            painter.translate(x - origin.x(), y - origin.y())
            painter.rotate(math.degrees(rot) + 90)
            col = QColor(_INK.red(), _INK.green(), _INK.blue(), alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(col)
            if kind == "flower":
                for i in range(5):
                    ang = i * math.tau / 5
                    painter.drawEllipse(QPointF(math.cos(ang) * 5.2, math.sin(ang) * 5.2), 3.4, 3.4)
                painter.setBrush(QColor(244, 168, 184, alpha))
                painter.drawEllipse(QPointF(0, 0), 2.6, 2.6)
            elif kind == "snow":
                pen = QPen(col)
                pen.setWidthF(1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                for i in range(6):
                    ang = i * math.tau / 6
                    painter.drawLine(QPointF(0, 0), QPointF(math.cos(ang) * 7, math.sin(ang) * 7))
            elif kind == "star":
                pen = QPen(QColor(255, 196, 82, alpha))
                pen.setWidthF(1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                for i in range(4):
                    ang = i * math.tau / 4
                    painter.drawLine(
                        QPointF(math.cos(ang) * 2.0, math.sin(ang) * 2.0),
                        QPointF(math.cos(ang) * 8.0, math.sin(ang) * 8.0),
                    )
            elif kind == "dot":
                painter.setBrush(QColor(104, 86, 140, alpha))
                painter.drawEllipse(QPointF(0, 0), 3.4, 3.4)
            else:
                side = -1 if left else 1
                ox = side * 5.5
                # 脚掌加三趾
                painter.drawEllipse(QPointF(ox, 2.5), 4.2, 5.2)
                for i in range(3):
                    tx = ox + (i - 1) * 3.4
                    painter.drawEllipse(QPointF(tx, -4.4 + abs(i - 1) * 1.0), 1.7, 2.0)
            painter.restore()
