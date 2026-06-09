# author: bdth
# email: 2074055628@qq.com
# 桌宠虫洞穿越：原地裂开虫洞→旋转缩入→窗口在不可见时瞬移→屏幕另一处冒出。
# 与 Entrance / Hideout 平行的第三种"窗口移动模式"，由 PetWindow 逐帧驱动。

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

_DURATION = 2.8
_JUMP_P = 0.5


def _clamp01(p: float) -> float:
    return max(0.0, min(1.0, p))


def _seg(p: float, a: float, b: float) -> float:
    return _clamp01((p - a) / (b - a)) if b > a else 0.0


def _ease_in(p: float) -> float:
    return p * p


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _ease_out_back(p: float) -> float:
    c = 1.70158
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2


class Wormhole:
    def __init__(self, frm: QPointF, to: QPointF, win_w: int, win_h: int) -> None:
        self._from = QPointF(frm)
        self._to = QPointF(to)
        self._w = win_w
        self._h = win_h
        self.duration = _DURATION

    def window_state(self, p: float) -> QPointF:
        """前半在出发点、后半在目标点；跳变卡在 blob 不可见的 _JUMP_P。"""
        return QPointF(self._from) if p < _JUMP_P else QPointF(self._to)

    def blob_transform(self, p: float):
        """返回 (sx, sy, oy, rot)：旋转缩入 → 不可见 → 旋出并过冲落定。"""
        if p < 0.22:
            return 1.0, 1.0, 0.0, 0.0
        if p < _JUMP_P:
            e = _ease_in(_seg(p, 0.22, 0.46))
            s = max(0.0, 1.0 - e)
            return s, s, 0.0, 540.0 * e
        if p < 0.55:
            return 0.0, 0.0, 0.0, 0.0
        e = _ease_out_back(_seg(p, 0.55, 0.82))
        s = max(0.0, e)
        spin = 360.0 * (1.0 - _ease_out(_seg(p, 0.55, 0.82)))
        return s, s, 0.0, spin

    def _portal_open(self, p: float) -> float:
        """虫洞张开度：出发侧 0→1→0，目标侧 0→1→0。"""
        if p < _JUMP_P:
            if p < 0.22:
                return _ease_out(_seg(p, 0.0, 0.22))
            if p < 0.42:
                return 1.0
            return 1.0 - _ease_in(_seg(p, 0.42, 0.5))
        if p < 0.58:
            return _ease_out(_seg(p, 0.5, 0.58))
        if p < 0.82:
            return 1.0
        return 1.0 - _ease_in(_seg(p, 0.82, 1.0))

    def draw_props(self, painter: QPainter, w: int, h: int, p: float) -> None:
        open_ = self._portal_open(p)
        if open_ <= 0.01:
            return
        rad = min(w, h) * 0.42 * open_
        painter.save()
        painter.translate(w / 2, h * 0.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(120, 90, 230, int(70 * open_)))
        painter.drawEllipse(QPointF(0.0, 0.0), rad * 1.18, rad * 1.18)

        pen = QPen(QColor(150, 120, 245))
        pen.setWidthF(max(1.5, w * 0.012))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(4):
            f = 1.0 - i * 0.22
            painter.save()
            painter.rotate((p * 1500 + i * 40) % 360)
            painter.drawArc(QRectF(-rad * f, -rad * f, rad * 2 * f, rad * 2 * f), 0, 300 * 16)
            painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(12, 8, 28))
        painter.drawEllipse(QPointF(0.0, 0.0), rad, rad)

        inward = p < _JUMP_P
        for k in range(8):
            a = p * 9.0 + k * (math.tau / 8)
            phase = (p * 4.0 + k * 0.3) % 1.0
            r = (1.0 - phase) if inward else phase
            pr = (1.0 - r)
            x, y = math.cos(a) * rad * 1.25 * r, math.sin(a) * rad * 1.25 * r
            painter.setBrush(QColor(190, 170, 255, int(220 * pr)))
            painter.drawEllipse(QPointF(x, y), w * 0.018 * pr + 0.5, w * 0.018 * pr + 0.5)
        painter.restore()
