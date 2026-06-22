# 好几个道具共用的小元件 音符和四角闪光

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF


def draw_note(painter: QPainter, at: QPointF, bw: float, bh: float, col: QColor, double: bool) -> None:
    """画音符 double 时连成八分音符"""
    head_r = bh * 0.05
    stem_h = bh * 0.17
    pen = QPen(col)
    pen.setWidthF(max(1.4, bw * 0.016))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(col)
    painter.drawEllipse(at, head_r, head_r * 0.8)
    stem_x = at.x() + head_r * 0.9
    top = QPointF(stem_x, at.y() - stem_h)
    painter.drawLine(QPointF(stem_x, at.y()), top)
    flag = QPen(col)
    flag.setWidthF(max(1.6, bw * 0.02))
    flag.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(flag)
    painter.drawLine(top, QPointF(stem_x + head_r * 1.4, at.y() - stem_h * 0.55))
    if double:
        at2 = QPointF(at.x() + head_r * 2.6, at.y() + head_r * 0.6)
        painter.setPen(pen)
        painter.setBrush(col)
        painter.drawEllipse(at2, head_r, head_r * 0.8)
        stem2 = QPointF(at2.x() + head_r * 0.9, at2.y() - stem_h)
        painter.drawLine(QPointF(at2.x() + head_r * 0.9, at2.y()), stem2)
        beam = QPen(col)
        beam.setWidthF(max(1.8, bw * 0.022))
        painter.setPen(beam)
        painter.drawLine(top, stem2)


def draw_spark(painter: QPainter, at: QPointF, bw: float, bh: float, p: float) -> None:
    """画四角闪光 先涨后缩"""
    s = (math.sin(p * math.pi)) * bh * 0.16
    if s <= 0.5:  # 太小不画
        return
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 210, 90))
    painter.drawPolygon(QPolygonF([
        QPointF(at.x(), at.y() - s), QPointF(at.x() + s * 0.28, at.y() - s * 0.28),
        QPointF(at.x() + s, at.y()), QPointF(at.x() + s * 0.28, at.y() + s * 0.28),
        QPointF(at.x(), at.y() + s), QPointF(at.x() - s * 0.28, at.y() + s * 0.28),
        QPointF(at.x() - s, at.y()), QPointF(at.x() - s * 0.28, at.y() - s * 0.28),
    ]))
