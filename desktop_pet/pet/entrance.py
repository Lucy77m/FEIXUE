# author: bdth
# email: 2074055628@qq.com
# 桌宠出场动画:定义多种登场方式(掉落/淡入/滑入/升起/开门/传送/降落伞)及其窗口与形体变换

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from desktop_pet.pet.character import BLOB_HALF_H
from desktop_pet.settings import DATA_DIR

ENTRANCE_KINDS = ("drop", "fade_pop", "slide", "rise", "door", "teleport", "parachute")

_DURATION = {
    "drop": 1.1,
    "fade_pop": 0.7,
    "slide": 0.85,
    "rise": 0.95,
    "door": 1.4,
    "teleport": 0.95,
    "parachute": 1.7,
}
_DEFAULT_DURATION = 1.0

_LAST_ENTRANCE_PATH = DATA_DIR / "last_entrance.txt"


def next_entrance_kind() -> str:
    try:
        last = _LAST_ENTRANCE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        last = ""
    choices = [k for k in ENTRANCE_KINDS if k != last] or list(ENTRANCE_KINDS)
    kind = random.choice(choices)
    try:
        _LAST_ENTRANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_ENTRANCE_PATH.write_text(kind, encoding="utf-8")
    except OSError:
        pass
    return kind


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _ease_in(p: float) -> float:
    return p * p


def _ease_out_back(p: float) -> float:
    c = 1.70158
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2


def _clamp01(p: float) -> float:
    return max(0.0, min(1.0, p))


def _seg(p: float, a: float, b: float) -> float:
    return _clamp01((p - a) / (b - a)) if b > a else 0.0


class Entrance:
    def __init__(self, kind: str, screen, rest, win_w: int, win_h: int) -> None:
        self.kind = kind
        self.duration = _DURATION.get(kind, _DEFAULT_DURATION)
        self._screen = screen
        self._rest = rest
        self._w = win_w
        self._h = win_h
        self._from_right = rest.x() + win_w / 2 >= screen.center().x()

    def window_state(self, p: float):
        rx, ry = float(self._rest.x()), float(self._rest.y())
        x, y, opacity = rx, ry, 1.0
        if self.kind == "drop":
            start_y = self._screen.top() - self._h
            y = start_y + (ry - start_y) * _ease_in(_seg(p, 0.0, 0.78))
        elif self.kind == "parachute":
            start_y = self._screen.top() - self._h
            y = start_y + (ry - start_y) * _seg(p, 0.0, 0.9)
        elif self.kind == "rise":
            start_y = float(self._screen.bottom())
            bounce = math.sin(_seg(p, 0.0, 1.0) * math.pi) * self._h * 0.06
            y = start_y + (ry - start_y) * _ease_out(_seg(p, 0.0, 0.85)) - bounce
        elif self.kind == "slide":
            start_x = float(self._screen.right()) if self._from_right else float(self._screen.left() - self._w)
            over = math.sin(_seg(p, 0.0, 1.0) * math.pi) * self._w * 0.05 * (-1 if self._from_right else 1)
            x = start_x + (rx - start_x) * _ease_out(_seg(p, 0.0, 0.85)) + over
        elif self.kind == "fade_pop":
            opacity = _seg(p, 0.0, 0.4)
        return QPointF(x, y), _clamp01(opacity)

    def blob_transform(self, p: float):
        sx = sy = 1.0
        oy = rot = 0.0
        if self.kind in ("drop", "rise", "parachute"):
            land = _seg(p, 0.82, 1.0)
            if land > 0:
                s = math.sin(land * math.pi)
                sx, sy = 1 + 0.22 * s, 1 - 0.22 * s
        elif self.kind == "fade_pop":
            sx = sy = _ease_out_back(_seg(p, 0.0, 1.0))
        elif self.kind == "teleport":
            sx = sy = _ease_out_back(_seg(p, 0.45, 0.85))
        elif self.kind == "door":
            g = _seg(p, 0.32, 0.72)
            sx = sy = g
            oy = (1 - g) * self._h * 0.12
        return sx, sy, oy, rot

    def draw_props(self, painter: QPainter, w: int, h: int, p: float) -> None:
        if self.kind == "door":
            self._draw_door(painter, w, h, p)
        elif self.kind == "teleport":
            self._draw_teleport(painter, w, h, p)
        elif self.kind == "parachute":
            self._draw_parachute(painter, w, h, p)

    def draw_overlay(self, painter: QPainter, w: int, h: int, p: float) -> None:
        if self.kind == "teleport":
            flash = _seg(p, 0.45, 0.82)
            if 0 < flash < 1:
                ring = QPen(QColor(205, 232, 255, int(220 * (1 - flash))))
                ring.setWidthF(w * 0.03)
                painter.setPen(ring)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                r = min(w, h) * 0.42 * flash
                painter.drawEllipse(QPointF(w / 2, h * 0.5), r, r)

    def _draw_door(self, painter: QPainter, w: int, h: int, p: float) -> None:
        fade = 1.0 - _seg(p, 0.75, 1.0)
        if fade <= 0:
            return
        cx = w / 2
        dw, dh = w * 0.72, h * 0.82
        x0, y0 = cx - dw / 2, h * 0.5 - dh / 2
        radius = dw * 0.12
        painter.setPen(Qt.PenStyle.NoPen)
        frame = QColor(74, 56, 40); frame.setAlphaF(fade)
        painter.setBrush(frame)
        painter.drawRoundedRect(QRectF(x0 - w * 0.03, y0 - h * 0.02, dw + w * 0.06, dh + h * 0.02), radius, radius)
        interior = QColor(34, 30, 30); interior.setAlphaF(fade)
        painter.setBrush(interior)
        painter.drawRoundedRect(QRectF(x0, y0, dw, dh), radius * 0.7, radius * 0.7)
        open_amt = _seg(p, 0.3, 0.62)
        panel_w = dw * (1 - open_amt)
        if panel_w > 1:
            panel = QColor(120, 92, 60); panel.setAlphaF(fade)
            painter.setBrush(panel)
            painter.drawRoundedRect(QRectF(x0, y0, panel_w, dh), radius * 0.6, radius * 0.6)
            knob = QColor(60, 44, 28); knob.setAlphaF(fade)
            painter.setBrush(knob)
            painter.drawEllipse(QPointF(x0 + panel_w * 0.82, h * 0.5), w * 0.018, w * 0.018)

    def _draw_teleport(self, painter: QPainter, w: int, h: int, p: float) -> None:
        cx, cy = w / 2, h * 0.5
        radius = min(w, h) * 0.45
        conv = _seg(p, 0.0, 0.55)
        painter.setPen(Qt.PenStyle.NoPen)
        if conv < 1.0:
            count = 12
            for i in range(count):
                ang = i / count * 2 * math.pi + p * 3.0
                dist = radius * (1 - _ease_in(conv))
                spark = QColor(150, 200, 255); spark.setAlphaF(1 - conv)
                painter.setBrush(spark)
                painter.drawEllipse(QPointF(cx + math.cos(ang) * dist, cy + math.sin(ang) * dist), w * 0.022, w * 0.022)

    def _draw_parachute(self, painter: QPainter, w: int, h: int, p: float) -> None:
        detach = _seg(p, 0.82, 1.0)
        if detach >= 1.0:
            return
        alpha = 1 - detach
        cx = w / 2
        cy = h * 0.2 - detach * h * 0.5
        cw = w * 0.46
        canopy = QColor(232, 110, 122); canopy.setAlphaF(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(canopy)
        dome = QPainterPath()
        dome.moveTo(cx - cw / 2, cy)
        dome.arcTo(QRectF(cx - cw / 2, cy - cw * 0.42, cw, cw * 0.84), 0, 180)
        dome.closeSubpath()
        painter.drawPath(dome)
        string = QPen(QColor(90, 70, 60, int(255 * alpha)))
        string.setWidthF(max(1.0, w * 0.007))
        painter.setPen(string)
        blob_top = h / 2 - BLOB_HALF_H
        for f in (-0.42, -0.14, 0.14, 0.42):
            painter.drawLine(
                QPointF(cx + cw / 2 * f, cy),
                QPointF(cx + cw * 0.12 * (1 if f > 0 else -1), blob_top),
            )
