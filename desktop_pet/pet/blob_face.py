# author: bdth
# email: 2074055628@qq.com
# 形象绘制mixin 身体眼睛嘴 睡颜 进食 装扮和问号

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)

from desktop_pet.pet import adornments
from desktop_pet.pet.props.registry import COSTUME_LAYERS
from desktop_pet.pet.behaviors.easing import ease_out
from desktop_pet.pet.blob_defs import (
    _BLINK_DUR,
    _INK,
    _OUTLINE,
    _SKIN,
    _ZZZ_ALPHA_MAX,
    _ZZZ_CYCLE,
    _ZZZ_INK,
    _ZZZ_STAGGER,
)


class FaceMixin:
    """身体五官和装扮的具体画法"""

    def _draw_zzz(self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float, e: float) -> None:
        painter.save()
        painter.translate(cx + bw * 0.28, head_y - bh * 0.42)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            ph = ((self._t / _ZZZ_CYCLE) - i * _ZZZ_STAGGER) % 1.0  # 三个z错相位飘
            a = math.sin(ph * math.pi)
            if a <= 0.0:
                continue
            sz = bh * (0.13 + i * 0.07)
            x, y = i * bw * 0.16, -i * bh * 0.34 - bh * 0.25 * (1 - a)
            pen = QPen(QColor(_ZZZ_INK.red(), _ZZZ_INK.green(), _ZZZ_INK.blue(), int(_ZZZ_ALPHA_MAX * a * e)))
            pen.setWidthF(max(1.5, sz * 0.16))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(
                QPolygonF([QPointF(x, y), QPointF(x + sz, y), QPointF(x, y + sz), QPointF(x + sz, y + sz)])
            )
        painter.restore()

    def _draw_body(self, painter: QPainter, bw: float, bh: float) -> None:
        grad = QLinearGradient(0.0, -bh / 2, 0.0, bh / 2)
        grad.setColorAt(0.0, _SKIN)
        grad.setColorAt(1.0, QColor(233, 236, 242))
        painter.setBrush(grad)
        pen = QPen(_OUTLINE)
        pen.setWidthF(max(2.0, bw * 0.018))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(-bw / 2, -bh / 2, bw, bh), bh * 0.48, bh * 0.48)

    def _draw_eyes(self, painter: QPainter, bw: float, bh: float) -> None:
        # 按表情画眼
        if self._sleep_e > 0.0:
            self._draw_sleeping_eyes(painter, bw, bh, self._sleep_e)
            return
        eat_p = self._eating_progress()
        if eat_p is not None:
            self._draw_eating_eyes(painter, eat_p, bw, bh)
            return
        if self._react is not None:
            rname, relapsed, rdur = self._react
            rp = min(1.0, relapsed / max(rdur, 0.001))
            gate = math.sin(min(rp * 3, 1.0, (1 - rp) * 3) * math.pi / 2)  # 进出渐变
            if rname in ("giggle", "purr", "snuggle"):
                adornments.draw_blush(painter, bw, bh, gate)
                dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
                self._eye_arc(painter, -dx, ey, ew, eh)
                self._eye_arc(painter, dx, ey, ew, eh)
                return
            if rname in ("happy_wiggle", "cheer", "celebrate", "bounce", "hop2", "dance", "headbang", "wave"):
                # 开心系反应统一笑眼 表演感拉满
                dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
                self._eye_arc(painter, -dx, ey, ew, eh)
                self._eye_arc(painter, dx, ey, ew, eh)
                return
            if rname == "splat" and rp < 0.55:
                # 摔懵了 X眼
                pen = QPen(_INK)
                pen.setWidthF(max(2.0, bw * 0.022))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                dx, ey = bw * 0.24, bh * 0.05
                r = bw * 0.055
                for sx in (-1, 1):
                    cx = sx * dx
                    painter.drawLine(QPointF(cx - r, ey - r), QPointF(cx + r, ey + r))
                    painter.drawLine(QPointF(cx + r, ey - r), QPointF(cx - r, ey + r))
                return
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        shift = self._turn * bw * 0.1           # 朝向偏移眼珠 远侧眼压扁
        scale_l = 1 - max(self._turn, 0.0) * 0.55
        scale_r = 1 - max(-self._turn, 0.0) * 0.55
        expr = self._expr

        if expr == "happy":
            self._eye_arc(painter, -dx + shift, ey, ew * scale_l, eh)
            self._eye_arc(painter, dx + shift, ey, ew * scale_r, eh)
            return
        if expr == "sad":
            self._eye_oval(painter, -dx + shift, ey + bh * 0.04, ew * scale_l, eh * 0.6)
            self._eye_oval(painter, dx + shift, ey + bh * 0.04, ew * scale_r, eh * 0.6)
            return
        if expr == "thinking":
            up = ey - eh * 0.3
            self._eye_oval(painter, -dx + shift, up, ew * scale_l, eh)
            self._eye_oval(painter, dx + shift, up, ew * scale_r, eh)
            return
        if expr == "confused":
            opening = self._blink_open()
            self._eye_oval(painter, -dx + shift, ey, ew * scale_l, eh * opening)
            self._eye_oval(painter, dx + shift, ey + bh * 0.02, ew * scale_r, eh * 0.4)
            return

        opening = self._blink_open()
        if expr == "surprised":
            ew, eh, opening = ew * 1.35, eh * 1.3, 1.0
        self._eye_oval(painter, -dx + shift, ey, ew * scale_l, max(eh * opening, eh * 0.08))
        self._eye_oval(painter, dx + shift, ey, ew * scale_r, max(eh * opening, eh * 0.08))

    def _eye_oval(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_INK)
        painter.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), w / 2, w / 2)

    def _eye_arc(self, painter: QPainter, cx: float, cy: float, ew: float, eh: float) -> None:
        pen = QPen(_INK)
        pen.setWidthF(eh * 0.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(cx - ew, cy - eh * 0.4, ew * 2, eh * 0.9), 20 * 16, 140 * 16)

    def _draw_sleeping_eyes(self, painter: QPainter, bw: float, bh: float, e: float) -> None:
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        oh = eh * (1 - e)
        for sx in (-1, 1):
            cx = sx * dx
            if oh > eh * 0.06:
                self._eye_oval(painter, cx, ey, ew, oh)
            if e > 0.1:
                pen = QPen(_INK)
                pen.setWidthF(max(1.5, eh * 0.3 * e))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawArc(QRectF(cx - ew, ey - eh * 0.1, ew * 2, eh * 0.5), 200 * 16, 140 * 16)

    def _draw_eating_eyes(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """吃东西的眼神 追着文件看 咀嚼眯眼 吞咽闭眼 打嗝瞪圆再变笑"""
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        if p < 0.15:
            # 圆睁 视线从头顶追到嘴边
            k = ease_out(p / 0.15)
            look = -eh * 0.3 + k * eh * 0.55
            scale = 1.15 + 0.1 * math.sin(p * 50)  # 好奇放大
            self._eye_oval(painter, -dx, ey + look, ew * scale, eh * scale)
            self._eye_oval(painter, dx, ey + look, ew * scale, eh * scale)
            return
        if p < 0.55:
            # 满足地眯起 弧线随咀嚼微颤
            q = (p - 0.15) / 0.4
            wob = math.sin(q * math.pi * 12 - math.pi / 2) * eh * 0.03
            self._eye_arc(painter, -dx, ey + wob, ew, eh)
            self._eye_arc(painter, dx, ey + wob, ew, eh)
            return
        if p < 0.75:
            # 咽下去那一下闭紧
            pen = QPen(_INK)
            pen.setWidthF(max(2.0, eh * 0.18))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for sx in (-1, 1):
                painter.drawLine(QPointF(sx * dx - ew * 0.5, ey), QPointF(sx * dx + ew * 0.5, ey))
            return
        q = (p - 0.75) / 0.25
        if q < 0.45:
            # 打嗝把自己惊到 瞪圆
            self._eye_oval(painter, -dx, ey - eh * 0.06, ew * 1.3, eh * 1.25)
            self._eye_oval(painter, dx, ey - eh * 0.06, ew * 1.3, eh * 1.25)
            return
        # 回味的笑眼
        self._eye_arc(painter, -dx, ey, ew, eh)
        self._eye_arc(painter, dx, ey, ew, eh)

    def _eating_progress(self) -> float | None:
        """正在吃就给进度 不在吃给None"""
        if self._react is not None and self._react[0] == "eating":
            _name, elapsed, dur = self._react
            return min(1.0, elapsed / max(dur, 0.001))
        return None

    def _draw_mouth(self, painter: QPainter, bw: float, bh: float) -> None:
        my = bh * 0.26
        eat_p = self._eating_progress()
        if eat_p is not None:
            self._draw_eating_mouth(painter, eat_p, bw, bh, my)
            return
        if self._talking:
            opening = (math.sin(self._t * 18) + 1) / 2
            mw, mh = bw * 0.1, bh * 0.03 + bh * 0.1 * opening
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_INK)
            painter.drawRoundedRect(QRectF(-mw / 2, my, mw, mh), mw * 0.4, mw * 0.4)
            return
        pen = QPen(_INK)
        pen.setWidthF(max(1.8, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mw = bw * 0.16
        box = QRectF(-mw / 2, my - bh * 0.05, mw, bh * 0.12)
        if self._expr == "happy":
            painter.drawArc(box, 200 * 16, 140 * 16)
        elif self._expr in ("sad", "confused"):
            painter.drawArc(box, 20 * 16, 140 * 16)
        elif self._expr == "surprised":
            painter.setBrush(_INK)
            painter.drawEllipse(QPointF(0.0, my + bh * 0.01), bh * 0.05, bh * 0.05)

    def _draw_eating_mouth(self, painter: QPainter, p: float, bw: float, bh: float, my: float) -> None:
        """吃东西的嘴 张大等 咀嚼开合 吞咽抿线 满足圆嘴变笑"""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_INK)
        if p < 0.15:
            k = ease_out(p / 0.15)
            mw, mh = bw * (0.08 + 0.07 * k), bh * (0.02 + 0.12 * k)
            painter.drawEllipse(QRectF(-mw / 2, my - mh * 0.2, mw, mh))
            return
        if p < 0.55:
            q = (p - 0.15) / 0.4
            opening = (math.sin(q * math.pi * 12 - math.pi / 2) + 1) / 2  # 六次开合
            mw = bw * (0.12 - 0.04 * opening)
            mh = bh * 0.02 + bh * 0.1 * opening
            painter.drawRoundedRect(QRectF(-mw / 2, my, mw, mh), mw * 0.35, mw * 0.35)
            return
        pen = QPen(_INK)
        pen.setWidthF(max(1.8, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if p < 0.75:
            q = (p - 0.55) / 0.2
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            wob = math.sin(q * math.pi) * bh * 0.015  # 咽下去那一下嘴角动一动
            painter.drawLine(QPointF(-bw * 0.05, my + bh * 0.03 + wob), QPointF(bw * 0.05, my + bh * 0.03 - wob))
            return
        q = (p - 0.75) / 0.25
        if q < 0.45:  # 打嗝小圆嘴
            painter.drawEllipse(QPointF(0.0, my + bh * 0.02), bh * 0.035, bh * 0.035)
        else:  # 回味的笑
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mw = bw * 0.16
            painter.drawArc(QRectF(-mw / 2, my - bh * 0.05, mw, bh * 0.12), 200 * 16, 140 * 16)


    def _draw_costume_worn(self, painter: QPainter, bw: float, bh: float) -> None:
        layers = COSTUME_LAYERS.get(self._costume)
        if layers and layers[0]:
            layers[0](painter, bw, bh, self._t, self._stage, self._stage_p)


    def _draw_costume_ambient(
        self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float
    ) -> None:
        layers = COSTUME_LAYERS.get(self._costume)
        if not (layers and layers[1]):
            return
        painter.save()
        painter.translate(cx, head_y)
        layers[1](painter, bw, bh, self._t, self._stage, self._stage_p)
        painter.restore()

    def _draw_question(self, painter: QPainter, cx: float, cy: float, bw: float, bh: float) -> None:
        font = QFont()
        font.setPixelSize(int(bh * 0.42))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_INK)
        painter.drawText(
            QRectF(cx + bw * 0.3, cy - bh * 0.95, bh * 0.5, bh * 0.5),
            Qt.AlignmentFlag.AlignCenter,
            "?",
        )

    def _blink_open(self) -> float:
        # 眼睛睁开度 眨眼走v形
        if not self._blinking:
            return 1.0
        return abs(self._blink_e / _BLINK_DUR - 0.5) * 2
