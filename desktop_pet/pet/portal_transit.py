"""One-way portal transition used for continuous workshop travel."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient


class PortalTransit:
    def __init__(self, direction: str) -> None:
        self.direction = "arrival" if direction == "arrival" else "departure"
        self.duration = 1.45
        self.midpoint = 0.62 if self.direction == "departure" else 0.30

    def transform(self, progress: float) -> tuple[float, float, float, float]:
        p = _clamp(progress)
        if self.direction == "departure":
            e = _ease_in(_segment(p, 0.12, 0.82))
            scale = max(0.0, 1.0 - e)
            return scale, scale, 18.0 * e, max(0.0, 1.0 - e)
        e = _ease_out(_segment(p, 0.18, 0.86))
        return e, e, 18.0 * (1.0 - e), e

    def portal_open(self, progress: float) -> float:
        p = _clamp(progress)
        if p < 0.18:
            return _ease_out(p / 0.18)
        if p < 0.78:
            return 1.0
        return 1.0 - _ease_in(_segment(p, 0.78, 1.0))

    def draw(self, painter: QPainter, foot: QPointF, progress: float, scale: float = 1.0) -> None:
        open_ = self.portal_open(progress)
        if open_ <= 0.01:
            return
        width = 82.0 * scale * open_
        height = 25.0 * scale * open_
        center = QPointF(foot.x(), foot.y() - 3.0 * scale)
        glow = QRadialGradient(center, width * 0.75)
        glow.setColorAt(0.0, QColor(83, 232, 226, int(105 * open_)))
        glow.setColorAt(1.0, QColor(83, 232, 226, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, width * 0.80, height * 1.6)
        painter.setBrush(QColor(13, 28, 31, int(238 * open_)))
        painter.setPen(QPen(QColor(91, 238, 231, int(245 * open_)), max(1.5, 2.2 * scale)))
        painter.drawEllipse(QRectF(center.x() - width / 2, center.y() - height / 2, width, height))
        painter.setPen(QPen(QColor(221, 255, 250, int(220 * open_)), max(1.0, 1.2 * scale)))
        for index in range(4):
            angle = progress * 7.0 + index * math.pi / 2
            painter.drawPoint(QPointF(
                center.x() + math.cos(angle) * width * 0.38,
                center.y() + math.sin(angle) * height * 0.35,
            ))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _segment(value: float, start: float, end: float) -> float:
    return _clamp((value - start) / (end - start)) if end > start else 0.0


def _ease_in(value: float) -> float:
    return value * value


def _ease_out(value: float) -> float:
    return 1.0 - (1.0 - value) ** 3
