# author: bdth
# email: 2074055628@qq.com
# 天气情绪和奇幻类环境特效 彩带 雨云 虚空 分身 流星 魔法这些

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet.behaviors.easing import ease_in, ease_out


def draw_confetti(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    colors = (QColor(245, 90, 120), QColor(90, 200, 140), QColor(90, 160, 240), QColor(255, 210, 80))
    for i in range(10):
        phase = (t * 1.3 + i * 0.27) % 1.0
        x = -bw * 0.6 + ((i * 0.135) % 1.0) * bw * 1.2
        y = -bh * 0.7 + phase * bh * 1.7
        painter.save()
        painter.translate(x, y)
        painter.rotate((t * 200 + i * 40) % 360)
        painter.setBrush(colors[i % 4])
        painter.drawRect(QRectF(-bw * 0.018, -bw * 0.03, bw * 0.036, bw * 0.06))
        painter.restore()


def draw_raincloud(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    cloud_y = -bh * 0.8
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(150, 155, 165))
    for dx2, rx, ry in (
        (-bw * 0.2, bh * 0.17, bh * 0.13),
        (0.0, bh * 0.22, bh * 0.17),
        (bw * 0.2, bh * 0.17, bh * 0.13),
    ):
        painter.drawEllipse(QPointF(dx2, cloud_y), rx, ry)
    painter.setBrush(QColor(118, 168, 228))
    for i in range(4):
        phase = (t * 2.0 + i * 0.27) % 1.0
        x = -bw * 0.22 + i * bw * 0.15
        y = cloud_y + bh * 0.16 + phase * bh * 0.45
        painter.drawEllipse(QPointF(x, y), bw * 0.016, bh * 0.04)


def draw_sweat(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    phase = (t * 1.4) % 1.0
    x, y = bw * 0.34, -bh * 0.22 + phase * bh * 0.5
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(120, 190, 240, 230))
    painter.drawEllipse(QPointF(x, y), bw * 0.04, bh * 0.065)
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(x - bw * 0.018, y - bh * 0.04),
                QPointF(x + bw * 0.018, y - bh * 0.04),
                QPointF(x, y - bh * 0.11),
            ]
        )
    )


def _star_poly(cx: float, cy: float, r: float) -> QPolygonF:
    """五角星轮廓"""
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(QPointF(cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    return QPolygonF(pts)


def draw_void(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画虚空漩涡 张开脉动闭合"""
    if stage == "notice":
        open_ = 0.25 * ease_out(stage_p)
    elif stage == "crack":
        open_ = 0.25 + 0.75 * ease_out(stage_p)
    elif stage == "seal":
        open_ = 1.0 - ease_in(stage_p)
    else:
        open_ = 1.0
    if open_ <= 0.01:
        return
    rw, rh = bw * 0.42 * open_, bh * 0.40 * open_
    painter.save()
    painter.translate(bw * 0.73, bh * 0.10)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(120, 90, 230, int(70 * open_)))
    painter.drawEllipse(QRectF(-rw * 0.78, -rh * 0.78, rw * 1.56, rh * 1.56))

    pen = QPen(QColor(150, 120, 245))
    pen.setWidthF(max(1.5, bw * 0.014))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(4):
        f = 1.0 - i * 0.22
        painter.save()
        painter.rotate((t * 60 + i * 40) % 360)
        painter.drawArc(QRectF(-rw * f, -rh * f, rw * 2 * f, rh * 2 * f), 0, 300 * 16)
        painter.restore()

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(12, 8, 28))
    painter.drawEllipse(QRectF(-rw, -rh, rw * 2, rh * 2))

    for k in range(7):
        a = t * 2.2 + k * (math.tau / 7)
        r = (t * 0.6 + k * 0.31) % 1.0
        pr = 1.0 - r
        x, y = math.cos(a) * rw * 1.4 * r, math.sin(a) * rh * 1.4 * r
        painter.setBrush(QColor(190, 170, 255, int(220 * pr)))
        painter.drawEllipse(QPointF(x, y), bw * 0.02 * pr + 0.5, bw * 0.02 * pr + 0.5)

    if stage == "gone":
        pulse = 0.5 + 0.5 * math.sin(t * 6.0)
        painter.setPen(QPen(QColor(200, 180, 255, int(160 * pulse)), max(1.5, bw * 0.02)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(-rw * 1.1, -rh * 1.1, rw * 2.2, rh * 2.2))
    painter.restore()


def _ghost_body(painter: QPainter, bw: float, bh: float, gx: float, gy: float, alpha: int) -> None:
    """画半透明分身"""
    painter.save()
    painter.translate(gx, gy)
    pen = QPen(QColor(120, 110, 220, alpha))
    pen.setWidthF(max(1.5, bw * 0.016))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QColor(150, 140, 235, int(alpha * 0.45)))
    painter.drawRoundedRect(QRectF(-bw / 2, -bh / 2, bw, bh), bh * 0.48, bh * 0.48)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(80, 70, 170, alpha))
    painter.drawEllipse(QPointF(-bw * 0.16, -bh * 0.02), bw * 0.05, bw * 0.05)
    painter.drawEllipse(QPointF(bw * 0.16, -bh * 0.02), bw * 0.05, bw * 0.05)
    painter.restore()


def draw_clone(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画影分身 分裂 镜像 换位 合体"""
    if stage == "split":
        a = ease_out(stage_p)
        gx, gy = 0.16 * bw * a, 0.0
    elif stage == "mirror":
        a = 1.0
        gx, gy = -math.sin(t * 3.0) * 0.18 * bw, 0.0
    elif stage == "swap":
        a = 1.0
        gx, gy = -math.cos(t * 1.8) * 0.22 * bw, -math.sin(t * 1.8) * 0.10 * bh
    elif stage == "merge":
        a = 1.0 - ease_in(stage_p)
        gx, gy = 0.16 * bw * (1.0 - ease_out(stage_p)), 0.0
    else:
        return
    if a <= 0.01:
        return
    _ghost_body(painter, bw, bh, gx, gy, int(200 * a))


def draw_meteor(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画接流星 坠下 接住 捧着 放飞"""
    twinkle = 0.8 + 0.2 * math.sin(t * 9.0)
    if stage == "spot":
        sx, sy, r, a = -0.55 * bw, -1.0 * bh, bw * 0.10, 1.0
    elif stage == "fall":
        e = ease_in(stage_p)
        sx = -0.55 * bw + e * 0.75 * bw
        sy = -1.0 * bh + e * 0.45 * bh
        r, a = bw * 0.11, 1.0
    elif stage == "scramble":
        sx = 0.20 * bw + math.sin(t * 5.0) * 0.03 * bw
        sy = -0.55 * bh + math.sin(t * 7.0) * 0.02 * bh
        r, a = bw * 0.11, 1.0
    elif stage == "catch":
        e = ease_out(min(stage_p / 0.5, 1.0))
        sx = 0.18 * bw - e * 0.03 * bw
        sy = -0.50 * bh + e * 0.42 * bh
        r, a = bw * 0.12, 1.0
    elif stage == "cradle":
        sx, sy = 0.12 * bw, -0.08 * bh + math.sin(t * 2.0) * 0.03 * bh
        r, a = bw * 0.13, 1.0
    elif stage == "release":
        e = ease_in(stage_p)
        sx, sy = 0.12 * bw, -0.08 * bh - e * 0.9 * bh
        r, a = bw * 0.13, 1.0 - e
    else:
        return
    if a <= 0.01:
        return
    painter.save()
    if stage == "fall":
        trail = QPen(QColor(255, 220, 130, 120))
        trail.setWidthF(max(1.5, bw * 0.02))
        trail.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(trail)
        painter.drawLine(QPointF(sx - bw * 0.12, sy - bh * 0.16), QPointF(sx, sy))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 230, 150, int(80 * a * twinkle)))
    painter.drawEllipse(QPointF(sx, sy), r * 1.8, r * 1.8)
    painter.setBrush(QColor(255, 220, 110, int(255 * a)))
    painter.drawPolygon(_star_poly(sx, sy, r * twinkle))
    painter.restore()


def draw_sprout(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画种花 播种 浇水 破土 绽放"""
    base_x, base_y = bw * 0.32, bh * 0.46
    if stage == "sprout":
        grow = ease_out(stage_p)
    elif stage in ("bloom", "sniff"):
        grow = 1.0
    else:
        grow = 0.0
    bloom = ease_out(stage_p) if stage == "bloom" else (1.0 if stage == "sniff" else 0.0)
    painter.save()

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(120, 85, 55))
    painter.drawChord(QRectF(base_x - bw * 0.14, base_y - bh * 0.05, bw * 0.28, bh * 0.16), 0, 180 * 16)

    if stage == "plant":
        seed_y = base_y - bh * 0.30 * (1.0 - ease_in(stage_p))
        painter.setBrush(QColor(90, 70, 50))
        painter.drawEllipse(QPointF(base_x, seed_y), bw * 0.022, bw * 0.022)
    if stage == "water":
        painter.setBrush(QColor(120, 190, 240, 220))
        for k in range(3):
            ph = (t * 1.6 + k * 0.33) % 1.0
            wy = base_y - bh * 0.34 + ph * bh * 0.30
            painter.drawEllipse(QPointF(base_x - bw * 0.05 + k * bw * 0.05, wy), bw * 0.018, bh * 0.03)

    stem_h = grow * bh * 0.55
    if stem_h > 1.0:
        sway = math.sin(t * 1.4) * bw * 0.03 * grow
        top = QPointF(base_x + sway, base_y - stem_h)
        pen = QPen(QColor(70, 150, 70))
        pen.setWidthF(max(1.8, bw * 0.02))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(base_x, base_y)
        path.quadTo(base_x + sway * 0.5, base_y - stem_h * 0.5, top.x(), top.y())
        painter.drawPath(path)
        if stem_h > bh * 0.22:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(90, 170, 90))
            ly = base_y - stem_h * 0.5
            painter.drawEllipse(QRectF(base_x + sway * 0.5 - bw * 0.10, ly - bh * 0.02, bw * 0.10, bh * 0.07))
            painter.drawEllipse(QRectF(base_x + sway * 0.5, ly - bh * 0.05, bw * 0.10, bh * 0.07))
        if bloom > 0.0:
            pr = bw * 0.06 * bloom
            painter.setBrush(QColor(240, 130, 170))
            for i in range(5):
                ang = t * 0.5 + i * (math.tau / 5)
                px, py = top.x() + math.cos(ang) * pr, top.y() + math.sin(ang) * pr
                painter.drawEllipse(QPointF(px, py), pr * 0.7, pr * 0.7)
            painter.setBrush(QColor(250, 215, 90))
            painter.drawEllipse(top, pr * 0.55, pr * 0.55)
            if stage == "sniff":
                painter.setBrush(QColor(255, 200, 90, int(180 * (0.5 + 0.5 * math.sin(t * 5.0)))))
                painter.drawEllipse(QPointF(top.x() + bw * 0.12, top.y() - bh * 0.10), bw * 0.012, bw * 0.012)
    painter.restore()


def draw_yarn(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画毛线球 盯 拍 追 缠 抱"""
    ground = bh * 0.40
    r = bw * 0.15
    tangle_k = 0.0
    if stage == "eye":
        bx, roll = bw * 0.60, math.sin(t * 3) * 4
    elif stage == "bat":
        sw = math.sin(stage_p * math.pi * 4)
        bx = bw * 0.42 + sw * bw * 0.30
        roll = sw * 230
    elif stage == "chase":
        bx = math.sin(stage_p * math.pi * 2) * bw * 0.80
        roll = stage_p * 720
    elif stage == "tangle":
        bx, roll = bw * 0.34, 90 + stage_p * 60
        tangle_k = ease_out(stage_p)
    else:  # rest
        bx, roll = bw * 0.38, 150.0
    # 缠到身上的线圈
    if tangle_k > 0.01:
        pen = QPen(QColor(214, 110, 124, int(230 * tangle_k)))
        pen.setWidthF(max(1.8, bw * 0.020))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            sweep = 200 * tangle_k
            painter.drawArc(QRectF(-bw * 0.52, -bh * 0.10 + i * bh * 0.14, bw * 1.04, bh * 0.16),
                            int((20 + i * 30) * 16), int(sweep * 16))
    # 线头 从球往身边拖一条松线
    pen = QPen(QColor(214, 110, 124, 235))
    pen.setWidthF(max(1.8, bw * 0.020))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(bx - r * 0.6, ground + r * 0.4))
    path.cubicTo(QPointF(bx - bw * 0.32, ground + r * 0.85 + math.sin(t * 2.5) * bh * 0.02),
                 QPointF(bx - bw * 0.52, ground - r * 0.2),
                 QPointF(bx - bw * 0.72, ground + r * 0.45))
    painter.drawPath(path)
    # 球体带绕线纹
    painter.save()
    painter.translate(bx, ground)
    painter.rotate(roll)
    painter.setPen(QPen(QColor(150, 64, 78), max(1.4, bw * 0.014)))
    painter.setBrush(QColor(226, 128, 142))
    painter.drawEllipse(QPointF(0, 0), r, r)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    pen2 = QPen(QColor(170, 78, 92, 220))
    pen2.setWidthF(max(1.4, bw * 0.016))
    painter.setPen(pen2)
    painter.drawArc(QRectF(-r, -r * 0.95, r * 2, r * 1.4), 30 * 16, 130 * 16)
    painter.drawArc(QRectF(-r * 0.95, -r * 0.5, r * 1.9, r * 1.5), 190 * 16, 140 * 16)
    painter.drawArc(QRectF(-r * 0.6, -r, r * 1.4, r * 2), 70 * 16, 120 * 16)
    painter.restore()


def draw_magic(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """变魔术 礼帽+魔杖 噗地冒星星"""
    def spark(c, sz, col):
        painter.setPen(QPen(col, max(1.0, sz * 0.3)))
        for a in range(4):
            ang = a * math.pi / 4
            painter.drawLine(QPointF(c.x() - math.cos(ang) * sz, c.y() - math.sin(ang) * sz),
                             QPointF(c.x() + math.cos(ang) * sz, c.y() + math.sin(ang) * sz))
    hx = bw * 0.22
    painter.setPen(QPen(QColor(40, 40, 50), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(58, 58, 70))
    painter.drawRect(QRectF(hx - bw * 0.08, -bh * 0.16, bw * 0.16, bh * 0.20))
    painter.drawRoundedRect(QRectF(hx - bw * 0.13, bh * 0.02, bw * 0.26, bh * 0.05), bw * 0.02, bw * 0.02)
    painter.setBrush(QColor(200, 80, 90))
    painter.drawRect(QRectF(hx - bw * 0.08, -bh * 0.02, bw * 0.16, bh * 0.035))
    wx, wy = bw * 0.44, -bh * 0.12
    painter.setPen(QPen(QColor(40, 40, 50), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(wx - bw * 0.07, bh * 0.05), QPointF(wx, wy))
    spark(QPointF(wx, wy), bw * 0.03, QColor(250, 215, 120))
    if stage == "poof":
        for sgn in range(6):
            ang = sgn * math.pi / 3 + t
            rr = bw * 0.06 + stage_p * bw * 0.22
            spark(QPointF(hx + math.cos(ang) * rr, -bh * 0.14 + math.sin(ang) * rr),
                  bw * 0.025, QColor(250, 215, 120, int(220 * (1 - stage_p))))


def draw_crystalball(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """凝视水晶球 里头打转"""
    cx, cy = bw * 0.30, -bh * 0.02
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(150, 120, 90))
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.10, bh * 0.22), QPointF(cx + bw * 0.10, bh * 0.22),
                                   QPointF(cx + bw * 0.06, bh * 0.14), QPointF(cx - bw * 0.06, bh * 0.14)]))
    painter.setPen(QPen(QColor(170, 195, 230), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(190, 210, 240, 200))
    painter.drawEllipse(QPointF(cx, cy), bw * 0.15, bw * 0.15)
    painter.setPen(QPen(QColor(150, 180, 230, 170), max(0.9, bw * 0.006)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(cx - bw * 0.08, cy - bh * 0.04, bw * 0.16, bh * 0.10), (int(t * 40) % 360) * 16, 160 * 16)
    if stage == "gaze":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        for k in range(3):
            a = t + k * 2.0
            painter.drawEllipse(QPointF(cx + math.cos(a) * bw * 0.07, cy + math.sin(a) * bw * 0.07), bw * 0.012, bw * 0.012)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 130))
    painter.drawEllipse(QPointF(cx - bw * 0.05, cy - bh * 0.05), bw * 0.035, bw * 0.03)


def draw_fishmoon(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """钓月亮 弯月高挂 钓线垂去勾它"""
    mx, my = bw * 0.42, -bh * 0.95
    moon = QPainterPath()
    moon.setFillRule(Qt.FillRule.OddEvenFill)
    moon.addEllipse(QPointF(mx, my), bw * 0.13, bw * 0.13)
    moon.addEllipse(QPointF(mx + bw * 0.06, my - bw * 0.02), bw * 0.12, bw * 0.12)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(248, 222, 130))
    painter.drawPath(moon)
    hand = QPointF(bw * 0.18, bh * 0.12)
    rod_tip = QPointF(bw * 0.30, -bh * 0.36)
    painter.setPen(QPen(QColor(150, 110, 70), max(1.2, bw * 0.01)))
    painter.drawLine(hand, rod_tip)
    sway = math.sin(t * 1.5) * bw * 0.03
    painter.setPen(QPen(QColor(150, 150, 165), max(0.7, bw * 0.005)))
    painter.drawLine(rod_tip, QPointF(mx - bw * 0.10 + sway, my + bw * 0.08))


def draw_butterfly(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """追蝴蝶 蝴蝶在头顶绕飞 翅膀扇"""
    bx = bw * (0.1 + 0.4 * math.sin(t * 1.5))
    by = -bh * (0.7 + 0.28 * math.sin(t * 2.2))
    flap = 0.5 + 0.5 * abs(math.sin(t * 8))
    painter.save()
    painter.translate(bx, by)
    painter.setPen(QPen(QColor(200, 120, 160), max(0.8, bw * 0.005)))
    for sgn in (-1, 1):
        painter.setBrush(QColor(236, 140, 180, 220))
        painter.drawEllipse(QPointF(sgn * bw * 0.05 * flap, -bw * 0.02), bw * 0.05 * flap, bw * 0.04)
        painter.setBrush(QColor(246, 182, 206, 220))
        painter.drawEllipse(QPointF(sgn * bw * 0.04 * flap, bw * 0.03), bw * 0.035 * flap, bw * 0.03)
    painter.setPen(QPen(QColor(80, 60, 70), max(1.0, bw * 0.006)))
    painter.drawLine(QPointF(0, -bw * 0.04), QPointF(0, bw * 0.05))
    painter.restore()


def draw_fireworks(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """放烟花 升空炸开"""
    if stage == "launch":
        y = bh * 0.1 - bh * 1.3 * stage_p
        painter.setPen(QPen(QColor(255, 210, 120), max(1.4, bw * 0.012)))
        painter.drawLine(QPointF(bw * 0.12, y + bh * 0.12), QPointF(bw * 0.12, y))
        return
    cols = [QColor(255, 140, 120), QColor(140, 200, 255), QColor(255, 225, 130), QColor(190, 165, 255)]
    for bi, (bx, by, off) in enumerate(((-bw * 0.05, -bh * 1.18, 0.0), (bw * 0.40, -bh * 0.82, 0.45))):
        p = (stage_p + off) % 1.0
        rad = bw * 0.05 + p * bw * 0.42
        col = QColor(cols[bi % len(cols)])
        col.setAlpha(int(225 * (1.0 - p)))
        for a in range(12):
            ang = a * math.pi / 6
            painter.setPen(QPen(col, max(1.0, bw * 0.008)))
            painter.drawLine(QPointF(bx + math.cos(ang) * rad * 0.42, by + math.sin(ang) * rad * 0.42),
                             QPointF(bx + math.cos(ang) * rad, by + math.sin(ang) * rad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(col)
            painter.drawEllipse(QPointF(bx + math.cos(ang) * rad, by + math.sin(ang) * rad), bw * 0.015, bw * 0.015)
