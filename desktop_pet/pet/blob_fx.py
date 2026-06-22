# 反应特效mixin 摸头投喂庆祝这些一次性演出的变形与粒子

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPolygonF,
)

from desktop_pet.pet.props.common import draw_note
from desktop_pet.pet.behaviors import registry
from desktop_pet.pet.behaviors.easing import ease_in, ease_out
from desktop_pet.pet.blob_defs import _DREAM_COLORS, _INK, _SKIN, _edge_alpha


class ReactFxMixin:
    """一次性反应演出的变形和特效"""

    def _react_transform(
        self, name: str, p: float, bw: float, bh: float
    ) -> tuple[float, float, float, float, float]:
        return registry.evaluate(name, p, bw, bh)


    _FX_NOTES = frozenset({"dance", "headbang", "purr"})
    _FX_CONFETTI = frozenset({"cheer", "celebrate"})
    _FX_SWOOSH = frozenset({"spin", "jump_spin", "roll", "flip"})
    _FX_SHOCK = frozenset({"gasp", "double_take", "recoil"})
    _FX_RING = frozenset({"pop", "boing"})


    _FX_GLOOM = frozenset({"slump", "droop", "deflate", "sigh", "splat"})
    _FX_MUNCH = frozenset({"eating"})
    _FX_TICKLE = frozenset({"giggle"})
    _FX_WARM = frozenset({"snuggle"})
    _FX_WAVE = frozenset({"wave"})

    def _draw_react_fx(self, painter: QPainter, name: str, p: float, cx: float, cy: float,
                       bw: float, bh: float) -> None:
        """按反应名分发到对应特效"""
        if name not in (self._FX_NOTES | self._FX_CONFETTI | self._FX_SWOOSH | self._FX_SHOCK
                        | self._FX_RING | self._FX_GLOOM | self._FX_MUNCH | self._FX_TICKLE
                        | self._FX_WARM | self._FX_WAVE):
            return
        painter.save()
        self._fx_origin_y = cy
        painter.translate(cx, cy)
        if name in self._FX_NOTES:
            self._fx_notes(painter, p, bw, bh)
        elif name in self._FX_CONFETTI:
            self._fx_confetti(painter, p, bw, bh)
        elif name in self._FX_SWOOSH:
            self._fx_swoosh(painter, p, bw, bh)
        elif name in self._FX_SHOCK:
            self._fx_shock(painter, p, bw, bh)
        elif name in self._FX_RING:
            self._fx_ring(painter, p, bw, bh)
        elif name in self._FX_GLOOM:
            self._fx_gloom(painter, p, bw, bh)
        elif name in self._FX_MUNCH:
            self._fx_munch(painter, p, bw, bh)
        elif name in self._FX_TICKLE:
            self._fx_tickle(painter, p, bw, bh)
        elif name in self._FX_WARM:
            self._fx_warm(painter, p, bw, bh)
        elif name in self._FX_WAVE:
            self._fx_wave(painter, p, bw, bh)
        painter.restore()

    def _fx_wave(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """身侧的手画弧挥动"""
        gate = math.sin(min(p * 4, 1.0, (1 - p) * 4) * math.pi / 2)
        if gate <= 0.01:
            return
        swing = math.sin(p * math.pi * 6)
        hx = bw * 0.55 + swing * bw * 0.10
        hy = -bh * 0.30 - gate * bh * 0.16 - abs(swing) * bh * 0.05
        painter.setPen(self._think_hand_pen(bw))
        painter.setBrush(_SKIN)
        painter.drawEllipse(QPointF(hx, hy), bw * 0.10 * gate, bw * 0.10 * gate)

    def _fx_warm(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """身侧升起的热气波纹"""
        gate = math.sin(min(p * 3, 1.0, (1 - p) * 3) * math.pi / 2)
        for k in range(3):
            ph = (p * 1.6 + k * 0.33) % 1.0
            x0 = (k - 1) * bw * 0.34
            rise = ph * bh * 0.7
            a = max(0, int(170 * gate * math.sin(ph * math.pi)))
            pen = QPen(QColor(238, 150, 92, a))
            pen.setWidthF(max(1.6, bw * 0.018))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pts = QPolygonF()
            for i in range(9):
                t = i / 8.0
                pts.append(QPointF(x0 + math.sin((t * 2.2 + ph * 2) * math.pi) * bw * 0.05,
                                   bh * 0.1 - rise - t * bh * 0.28))
            painter.drawPolyline(pts)

    def _fx_tickle(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """痒得乱蹦的小星和墨点"""
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(7):
            ph = (p * 2.4 + k * 0.29) % 1.0
            side = 1 if k % 2 == 0 else -1
            x = side * (bw * 0.32 + ph * bw * 0.3) + math.sin(ph * math.pi * 3 + k) * bw * 0.04
            y = bh * 0.1 - math.sin(ph * math.pi) * bh * 0.55
            a = max(0, int(225 * (1 - ph)))
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(a)
            if k % 3 == 0:
                # 四角小星
                pen = QPen(col)
                pen.setWidthF(max(1.4, bw * 0.014))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                r = bw * 0.030 * (1 - ph * 0.4)
                painter.drawLine(QPointF(x - r, y), QPointF(x + r, y))
                painter.drawLine(QPointF(x, y - r), QPointF(x, y + r))
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                rr = bw * 0.018 * (1 - ph * 0.5)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(x, y), rr, rr)

    def _fx_munch(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """吃东西全程特效 文件落下 碎屑 咕咚 打嗝星"""
        mouth_y = bh * 0.26
        if p < 0.15:
            # 小文件从头顶落进嘴里 越落越小
            k = ease_in(p / 0.15)
            fy = -bh * 0.95 + (mouth_y + bh * 0.95) * k
            s = bw * 0.16 * (1 - 0.45 * k)
            painter.setPen(QPen(QColor(120, 118, 140, 230), max(1.2, bw * 0.012)))
            painter.setBrush(QColor(252, 252, 255, 240))
            painter.save()
            painter.translate(0.0, fy)
            painter.rotate(k * 24)
            painter.drawRoundedRect(QRectF(-s / 2, -s * 0.62, s, s * 1.24), s * 0.12, s * 0.12)
            # 折角和两道字纹
            painter.setBrush(QColor(214, 212, 232, 240))
            painter.drawPolygon(QPolygonF([QPointF(s * 0.5 - s * 0.3, -s * 0.62),
                                           QPointF(s * 0.5, -s * 0.62 + s * 0.3),
                                           QPointF(s * 0.5, -s * 0.62)]))
            for i in (0, 1):
                yy = -s * 0.15 + i * s * 0.3
                painter.drawRect(QRectF(-s * 0.3, yy, s * 0.6, s * 0.07))
            painter.restore()
            return
        if p < 0.55:
            # 嘴边崩碎屑 左右交替
            q = (p - 0.15) / 0.4
            painter.setPen(Qt.PenStyle.NoPen)
            for k in range(5):
                ph = (q * 3 + k * 0.37) % 1.0
                side = 1 if k % 2 == 0 else -1
                x = side * (bw * 0.1 + ph * bw * 0.22)
                y = mouth_y + ph * bh * 0.3 - math.sin(ph * math.pi) * bh * 0.12
                col = QColor(_INK)
                col.setAlpha(max(0, int(200 * (1 - ph))))
                painter.setBrush(col)
                r = bw * 0.014 * (1 - ph * 0.5)
                painter.drawEllipse(QPointF(x, y), r, r)
            return
        if p < 0.75:
            # 咕咚 一个圈从嘴滑到肚子
            q = (p - 0.55) / 0.2
            y = mouth_y + q * bh * 0.34
            alpha = max(0, int(150 * math.sin(q * math.pi)))
            pen = QPen(QColor(150, 170, 215, alpha))
            pen.setWidthF(max(1.2, bw * 0.014))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0.0, y), bw * 0.1 * (1 - q * 0.3), bh * 0.045 * (1 - q * 0.3))
            return
        # 打嗝小星星往上飘
        q = (p - 0.75) / 0.25
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            ph = max(0.0, q - k * 0.18)
            if ph <= 0:
                continue
            x = (k - 1) * bw * 0.16 + math.sin(ph * math.pi * 2 + k) * bw * 0.05
            y = -bh * 0.55 - ph * bh * 0.5
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(max(0, int(230 * (1 - ph))))
            painter.setBrush(col)
            r = bw * (0.030 - 0.008 * k)
            star = QPolygonF()
            for i in range(8):
                ang = i * math.pi / 4 - math.pi / 2
                rad = r if i % 2 == 0 else r * 0.45
                star.append(QPointF(x + math.cos(ang) * rad, y + math.sin(ang) * rad))
            painter.drawPolygon(star)

    def _fx_notes(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        for k in range(4):
            ph = (p * 1.7 + k / 4.0) % 1.0
            side = 1 if k % 2 == 0 else -1
            x = side * (bw * 0.46 + bw * 0.10 * math.sin(self._t * 3 + k))
            y = -bh * 0.18 - ph * bh * 0.95
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(max(0, int(math.sin(ph * math.pi) * 230)))
            draw_note(painter, QPointF(x, y), bw, bh, col, double=(k % 2 == 0))

    def _fx_confetti(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        n = 14
        for k in range(n):
            ang = -math.pi / 2 + (k - n / 2) / n * 2.4
            spd = 0.7 + ((k * 37) % 11) / 11.0 * 0.6
            launch = bw * 0.85 * spd
            x = math.cos(ang) * launch * p
            y = -bh * 0.55 + math.sin(ang) * launch * p + bh * 2.0 * p * p
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            edge = _edge_alpha(self._fx_origin_y + y, self._win_h)
            col.setAlpha(max(0, int(255 * (1 - p * 0.6) * edge)))
            painter.setBrush(col)
            painter.save()
            painter.translate(x, y)
            painter.rotate((self._t * 260 + k * 53) % 360)
            painter.drawRect(QRectF(-bw * 0.022, -bw * 0.013, bw * 0.044, bw * 0.026))
            painter.restore()

    def _fx_swoosh(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        pen = QPen(QColor(150, 170, 215, max(0, int(190 * (1 - p)))))
        pen.setWidthF(max(1.5, bw * 0.018))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        base = self._t * 680
        rect = QRectF(-bw * 0.62, -bh * 0.78, bw * 1.24, bh * 1.5)
        for k in range(3):
            painter.drawArc(rect, int((base + k * 120) * 16), int(54 * 16))

    def _fx_shock(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        k = max(0.0, 1.0 - p / 0.55)
        if k <= 0.02:
            return
        pen = QPen(QColor(90, 92, 110, int(230 * k)))
        pen.setWidthF(max(1.5, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        oy = -bh * 0.72
        for deg in range(0, 360, 45):
            a = math.radians(deg)
            r0 = bh * (0.18 + 0.12 * (1 - k))
            r1 = r0 + bh * 0.18
            painter.drawLine(QPointF(math.cos(a) * r0, oy + math.sin(a) * r0 * 0.7),
                             QPointF(math.cos(a) * r1, oy + math.sin(a) * r1 * 0.7))

    def _fx_ring(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        r = (0.35 + ease_out(p) * 0.45) * bw
        pen = QPen(QColor(150, 180, 230, max(0, int(235 * (1 - p) ** 0.7))))
        pen.setWidthF(max(2.0, bw * 0.03) * (1 - p * 0.5))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0.0, 0.0), r, r * 0.82)

    def _fx_gloom(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            ph = (p * 1.3 + k * 0.26) % 1.0
            x = bw * 0.34 + ph * bw * 0.40
            y = -bh * 0.08 - ph * bh * 0.30
            r = bh * (0.05 + 0.09 * ph)
            painter.setBrush(QColor(172, 177, 188, max(0, int(150 * math.sin(ph * math.pi)))))
            painter.drawEllipse(QPointF(x, y), r, r * 0.8)
