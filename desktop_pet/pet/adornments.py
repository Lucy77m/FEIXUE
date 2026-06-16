# author: bdth
# email: 2074055628@qq.com
# 持续状态装饰绘制 被子雨伞扇子蛋糕等

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from desktop_pet.pet import palette
from desktop_pet.pet.behaviors.easing import ease_out

_INK = palette.INK
_SKIN = palette.SKIN
_OUTLINE = palette.OUTLINE
_SLEEP_BREATH_HZ = 0.9


def _hand_pen(bw: float) -> QPen:
    pen = QPen(_OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.018))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def draw_blush(painter: QPainter, bw: float, bh: float, k: float) -> None:
    """脸颊两团红晕"""
    if k <= 0.01:
        return
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(244, 142, 162, int(72 * k)))
    for sx in (-1, 1):
        painter.drawEllipse(QPointF(sx * bw * 0.31, bh * 0.17), bw * 0.085, bh * 0.05)


def draw_shy_hands(painter: QPainter, bw: float, bh: float, e: float, t: float) -> None:
    """双手从下面升起来捂住眼"""
    k = ease_out(e)
    dx, ey = bw * 0.24, bh * 0.05
    start_y = bh * 0.42
    painter.setPen(_hand_pen(bw))
    painter.setBrush(_SKIN)
    wob = math.sin(t * 2.2) * bh * 0.012  # 捂着也会微微动
    for sx in (-1, 1):
        hx = sx * dx * (1.25 - 0.25 * k)
        hy = start_y + (ey - start_y) * k + wob
        painter.drawEllipse(QPointF(hx, hy), bw * 0.115, bw * 0.10)


def draw_weather(painter: QPainter, bw: float, bh: float, kind: str, e: float, t: float) -> None:
    """天气装饰 雨伞 雪人 化水"""
    kind = kind or ("rain" if e > 0 else "")
    if kind == "rain":
        # 伞偏左、举在左手里 罩住头 周围雨丝
        k = ease_out(e)
        ux = -bw * 0.20                 # 伞往左偏 不在正中
        top = -bh * (0.55 + 0.32 * k)
        painter.setPen(QPen(_INK, max(1.5, bw * 0.015)))
        painter.setBrush(QColor(122, 108, 255, int(235 * e)))
        span = bw * 0.5
        painter.drawChord(QRectF(ux - span, top, span * 2, bh * 0.5), 0, 180 * 16)
        # 伞骨尖
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            px = ux - span + span * i
            painter.drawLine(QPointF(px, top + bh * 0.25), QPointF(px, top + bh * 0.28))
        # 长伞柄：从伞面一路斜下来 到左下方的左手（手臂高度 不在头上）
        hand_x, hand_y = -bw * 0.36, bh * 0.22
        painter.drawLine(QPointF(ux, top + bh * 0.25), QPointF(hand_x, hand_y))
        # 左手攥住伞柄末端
        bob = math.sin(t * 1.6) * bh * 0.008
        painter.setPen(_hand_pen(bw))
        painter.setBrush(_SKIN)
        painter.drawEllipse(QPointF(hand_x, hand_y + bob), bw * 0.095, bw * 0.088)
        # 雨丝 伞外落
        pen = QPen(QColor(140, 180, 235, int(190 * e)))
        pen.setWidthF(max(1.3, bw * 0.012))
        painter.setPen(pen)
        for i in range(5):
            ph = (t * 0.9 + i * 0.23) % 1.0
            side = -1 if i % 2 == 0 else 1
            rx = ux + side * (bw * 0.5 + (i % 3) * bw * 0.08)
            ry = -bh * 0.5 + ph * bh * 1.0
            painter.drawLine(QPointF(rx, ry), QPointF(rx - bw * 0.02, ry + bh * 0.07))
    elif kind == "snow":
        # 脚边小雪人 头顶飘雪
        k = ease_out(e)
        sx0, sy0 = bw * 0.72, bh * 0.36
        painter.setPen(QPen(QColor(150, 160, 186, int(230 * e)), max(1.3, bw * 0.013)))
        painter.setBrush(QColor(250, 250, 254, int(240 * e)))
        painter.drawEllipse(QPointF(sx0, sy0), bw * 0.13 * k, bh * 0.085 * k)
        painter.drawEllipse(QPointF(sx0, sy0 - bh * 0.115 * k), bw * 0.085 * k, bh * 0.06 * k)
        if k > 0.6:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(40, 38, 48, int(255 * e)))
            for ex in (-1, 1):
                painter.drawEllipse(QPointF(sx0 + ex * bw * 0.022, sy0 - bh * 0.125), bw * 0.008, bw * 0.008)
            painter.setBrush(QColor(238, 140, 70, int(255 * e)))
            painter.drawPolygon(QPolygonF([
                QPointF(sx0, sy0 - bh * 0.105), QPointF(sx0 + bw * 0.045, sy0 - bh * 0.095),
                QPointF(sx0, sy0 - bh * 0.085)]))
        # 飘雪
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(220 * e)))
        for i in range(4):
            ph = (t * 0.35 + i * 0.27) % 1.0
            fx2 = math.sin((ph * 2.5 + i) * math.pi) * bw * 0.4
            fy = -bh * 0.85 + ph * bh * 1.1
            painter.drawEllipse(QPointF(fx2, fy), bw * 0.014, bw * 0.014)
    elif kind == "melt":
        # 身底一摊水渍 加汗
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(150, 200, 240, int(90 * e)))
        painter.drawEllipse(QPointF(0, bh * 0.46), bw * 0.55 * e, bh * 0.05 * e)
        ph = (t * 0.5) % 1.0
        a = int(200 * e * math.sin(min(ph * 3, 1.0, (1 - ph) * 4) * math.pi / 2))
        if a > 0:
            painter.setBrush(QColor(140, 190, 240, a))
            painter.drawEllipse(QPointF(bw * 0.40, -bh * 0.28 + ph * bh * 0.4), bw * 0.024, bw * 0.030)


def draw_cake(
    painter: QPainter, cx: float, head_y: float, bw: float, bh: float,
    e: float, lit: bool, smoke: float, t: float,
) -> None:
    """纪念日小蛋糕 两层三蜡烛 火苗会摆 吹灭冒烟"""
    k = ease_out(e)
    gx = cx + bw * 0.72
    gy = head_y + bh * 0.46 + (1 - k) * bh * 0.35  # 从下面端上来
    painter.save()
    painter.translate(gx, gy)
    alpha = int(255 * min(1.0, e * 1.4 + (0.4 if smoke > 0 else 0.0)))
    # 托盘
    painter.setPen(QPen(QColor(120, 108, 96, alpha), max(1.3, bw * 0.012)))
    painter.setBrush(QColor(238, 234, 244, alpha))
    painter.drawEllipse(QPointF(0, bh * 0.020), bw * 0.30, bh * 0.045)
    # 下层
    painter.setBrush(QColor(248, 226, 198, alpha))
    painter.drawRoundedRect(QRectF(-bw * 0.24, -bh * 0.10, bw * 0.48, bh * 0.12), 4, 4)
    # 上层
    painter.setBrush(QColor(252, 238, 214, alpha))
    painter.drawRoundedRect(QRectF(-bw * 0.16, -bh * 0.19, bw * 0.32, bh * 0.10), 4, 4)
    # 奶油波边
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(244, 168, 184, alpha))
    for i in range(5):
        px = -bw * 0.20 + i * bw * 0.10
        painter.drawEllipse(QPointF(px, -bh * 0.10), bw * 0.030, bh * 0.020)
    # 三根蜡烛
    for i, px in enumerate((-bw * 0.09, 0.0, bw * 0.09)):
        painter.setBrush(QColor(168, 196, 240, alpha))
        painter.drawRect(QRectF(px - bw * 0.012, -bh * 0.265, bw * 0.024, bh * 0.075))
        if lit:
            # 火苗 各自摆
            fx_off = math.sin(t * 7 + i * 2.1) * bw * 0.008
            fl = QColor(252, 186, 86, alpha)
            painter.setBrush(fl)
            painter.drawEllipse(QPointF(px + fx_off, -bh * 0.295), bw * 0.016, bh * 0.026)
            painter.setBrush(QColor(255, 232, 150, alpha))
            painter.drawEllipse(QPointF(px + fx_off, -bh * 0.288), bw * 0.008, bh * 0.013)
    # 吹灭的烟
    if smoke > 0.0:
        k2 = 1 - smoke / 2.2
        painter.setPen(Qt.PenStyle.NoPen)
        for i, px in enumerate((-bw * 0.09, 0.0, bw * 0.09)):
            ph = min(1.0, k2 * 1.6 + i * 0.08)
            sa = max(0, int(150 * (1 - ph)))
            painter.setBrush(QColor(170, 170, 184, sa))
            sy = -bh * 0.30 - ph * bh * 0.22
            sx2 = px + math.sin(ph * 5 + i) * bw * 0.02
            painter.drawEllipse(QPointF(sx2, sy), bw * 0.014 + ph * bw * 0.012, bh * 0.018)
    painter.restore()


def draw_hot(painter: QPainter, bw: float, bh: float, e: float, t: float) -> None:
    """热成这样 汗滴下滑 折扇狂扇"""
    # 两滴汗 沿脸侧循环下滑
    painter.setPen(Qt.PenStyle.NoPen)
    for k, sx in ((0, -1), (1, 1)):
        ph = (t * 0.45 + k * 0.5) % 1.0
        drop_y = -bh * 0.30 + ph * bh * 0.42
        a = int(200 * e * math.sin(min(ph * 3, 1.0, (1 - ph) * 4) * math.pi / 2))
        if a <= 0:
            continue
        painter.setBrush(QColor(140, 190, 240, a))
        r = bw * 0.030
        x = sx * bw * 0.40
        painter.drawEllipse(QPointF(x, drop_y), r * 0.78, r)
        painter.drawPolygon(QPolygonF([
            QPointF(x - r * 0.5, drop_y - r * 0.5),
            QPointF(x + r * 0.5, drop_y - r * 0.5),
            QPointF(x, drop_y - r * 1.55),
        ]))
    # 右手折扇 快速摆
    k = ease_out(e)
    hand = QPointF(bw * 0.52, bh * 0.10 - k * bh * 0.06)
    painter.save()
    painter.translate(hand)
    painter.rotate(-22 + math.sin(t * 13) * 26 * e)
    fan_l = bw * 0.30
    painter.setPen(QPen(_INK, max(1.4, bw * 0.014)))
    painter.setBrush(QColor(250, 244, 226, int(245 * e)))
    path_pts = [QPointF(0, 0)]
    for i in range(7):
        ang = math.radians(-58 + i * 19)
        path_pts.append(QPointF(math.sin(ang) * fan_l, -math.cos(ang) * fan_l))
    path_pts.append(QPointF(0, 0))
    painter.drawPolygon(QPolygonF(path_pts))
    for i in range(7):  # 扇骨
        ang = math.radians(-58 + i * 19)
        painter.drawLine(QPointF(0, 0), QPointF(math.sin(ang) * fan_l, -math.cos(ang) * fan_l))
    painter.restore()
    # 手
    painter.setPen(_hand_pen(bw))
    painter.setBrush(_SKIN)
    painter.drawEllipse(hand, bw * 0.09, bw * 0.09)


def draw_squeeze_marks(painter: QPainter, bw: float, bh: float, e: float, t: float) -> None:
    """两侧压力痕 被挤的难受"""
    pen = QPen(QColor(_INK.red(), _INK.green(), _INK.blue(), int(150 * e)))
    pen.setWidthF(max(1.6, bw * 0.016))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for sx in (-1, 1):
        for i in range(3):
            x = sx * (bw * 0.56 + i * bw * 0.05)
            ln = bh * (0.16 - i * 0.035)
            y0 = -ln / 2 + math.sin(t * 9 + i) * bh * 0.012
            painter.drawLine(QPointF(x, y0), QPointF(x, y0 + ln))


def draw_blanket(painter: QPainter, bw: float, bh: float, e: float, t: float) -> None:
    """从下往上盖的小被子 波浪边带圆点花纹"""
    k = ease_out(e)
    top = bh * (0.55 - 0.42 * k)  # 被沿位置
    breathe = math.sin(t * _SLEEP_BREATH_HZ) * bh * 0.012
    top += breathe
    w = bw * 0.62
    painter.setPen(QPen(QColor(120, 108, 96, int(230 * e)), max(1.4, bw * 0.014)))
    painter.setBrush(QColor(248, 232, 198, int(240 * e)))
    # 被身
    body = QPolygonF()
    steps = 9
    for i in range(steps + 1):  # 上沿波浪
        x = -w + (2 * w) * i / steps
        y = top + math.sin(i * math.pi) * 0  # 占位直线 用弧画波浪太繁 改小圆齿
        body.append(QPointF(x, y + (bh * 0.018 if i % 2 else 0.0)))
    body.append(QPointF(w, bh * 0.62))
    body.append(QPointF(-w, bh * 0.62))
    painter.drawPolygon(body)
    # 圆点花纹
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(236, 196, 150, int(200 * e)))
    for i in range(4):
        px = -w * 0.7 + i * w * 0.46
        py = top + bh * 0.16 + (i % 2) * bh * 0.10
        if py < bh * 0.58:
            painter.drawEllipse(QPointF(px, py), bw * 0.025, bw * 0.025)


def draw_lowbatt(painter: QPainter, bw: float, bh: float, e: float, t: float) -> None:
    """头顶红色低电量图标 闪烁"""
    blink = (math.sin(t * 5) + 1) / 2
    a = int((90 + 150 * blink) * e)
    x, y = bw * 0.34, -bh * 0.72
    w, h = bw * 0.17, bh * 0.105
    painter.setPen(QPen(QColor(220, 70, 86, a), max(1.5, bw * 0.016)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(x - w / 2, y - h / 2, w, h), 2.5, 2.5)
    painter.drawRect(QRectF(x + w / 2, y - h * 0.2, w * 0.10, h * 0.4))  # 电极头
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(220, 70, 86, a))
    painter.drawRect(QRectF(x - w / 2 + w * 0.10, y - h * 0.26, w * 0.16, h * 0.52))  # 只剩一格
