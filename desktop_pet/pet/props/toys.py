# author: bdth
# email: 2074055628@qq.com
# 玩具游戏类 气球 风筝 积木 套圈 飞盘这些

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet.behaviors.easing import ease_in, ease_out


def draw_bubbles(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹泡泡 蘸 吹 看着飘 啵地破"""
    wand = QPointF(bw * 0.30, bh * 0.08)
    # 嘴边蘸了泡泡水的小吹圈
    if stage in ("dip", "blow"):
        painter.setPen(QPen(QColor(180, 150, 120), max(1.4, bw * 0.02)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(wand, bw * 0.07, bw * 0.07)
        painter.drawLine(QPointF(wand.x() + bw * 0.06, wand.y() + bw * 0.05),
                         QPointF(wand.x() + bw * 0.14, wand.y() + bw * 0.14))
    base = QPointF(wand.x() + bw * 0.02, wand.y() - bw * 0.02)
    count = 6
    popped = int(stage_p * count) % count if stage == "pop" else -1
    for i in range(count):
        if stage == "dip":
            continue
        age = max(0.0, stage_p - i * 0.13) * 1.3 if stage == "blow" else ((t * 0.35 + i * 0.17) % 1.0)
        if age <= 0.0 or age >= 1.0:
            continue
        x = base.x() + bw * (0.05 + 0.45 * age) + math.sin(t * 1.8 + i * 1.3) * bw * 0.05
        y = base.y() - bh * (0.15 + 1.25 * age)
        r = bw * (0.05 + 0.045 * ((i * 7) % 3)) * (0.7 + 0.5 * age)
        alpha = int(165 * (1.0 - age) ** 0.6)
        if i == popped and age > 0.4:  # 啵的一下小爆裂
            painter.setPen(QPen(QColor(150, 200, 235, alpha), max(1.0, bw * 0.012)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for a in range(6):
                ang = a * math.pi / 3
                painter.drawLine(QPointF(x + math.cos(ang) * r * 0.7, y + math.sin(ang) * r * 0.7),
                                 QPointF(x + math.cos(ang) * r * 1.4, y + math.sin(ang) * r * 1.4))
            continue
        painter.setPen(QPen(QColor(150, 200, 235, min(255, alpha + 40)), max(1.0, bw * 0.01)))
        painter.setBrush(QColor(195, 228, 246, int(alpha * 0.45)))
        painter.drawEllipse(QPointF(x, y), r, r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(alpha * 0.85)))
        painter.drawEllipse(QPointF(x - r * 0.32, y - r * 0.32), r * 0.24, r * 0.24)


def draw_balloon(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """攥着气球 抓 晃 拽 飘"""
    lift = ease_out(stage_p) if stage == "float" else 0.0
    sway = math.sin(t * 1.5) * bw * 0.06
    bx = bw * 0.34 + sway
    by = -bh * (0.78 + 0.55 * lift)
    hand = QPointF(bw * 0.22, bh * 0.20)
    pen = QPen(QColor(120, 120, 135), max(1.0, bw * 0.008))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(hand)
    path.cubicTo(QPointF(bx - bw * 0.10, by + bh * 0.55), QPointF(bx + bw * 0.10, by + bh * 0.35),
                 QPointF(bx, by + bh * 0.18))
    painter.drawPath(path)
    rw, rh = bw * 0.18, bh * 0.30
    painter.setPen(QPen(QColor(190, 70, 90), max(1.2, bw * 0.01)))
    painter.setBrush(QColor(232, 96, 112))
    painter.drawEllipse(QPointF(bx, by), rw, rh)
    painter.setBrush(QColor(210, 80, 96))
    painter.drawPolygon(QPolygonF([QPointF(bx - rw * 0.14, by + rh * 0.92),
                                   QPointF(bx + rw * 0.14, by + rh * 0.92), QPointF(bx, by + rh * 1.14)]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 150))
    painter.drawEllipse(QPointF(bx - rw * 0.36, by - rh * 0.34), rw * 0.28, rh * 0.20)


def draw_paperplane(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """折 掷 弧线滑翔的小纸飞机"""
    if stage == "fold":
        x, y, ang, sc = bw * 0.28, bh * 0.02, -10.0, 0.8
    elif stage == "throw":
        x, y, ang, sc = bw * (0.10 + 0.5 * stage_p), -bh * (0.10 + 0.3 * stage_p), -20.0, 1.0
    else:  # glide
        x = bw * (0.45 + 0.5 * math.sin(stage_p * math.pi))
        y = -bh * (0.6 + 0.3 * math.sin(stage_p * math.pi * 2))
        ang, sc = -15.0 + math.sin(t * 2) * 8, 1.0
    painter.save()
    painter.translate(x, y)
    painter.rotate(ang)
    s = bw * 0.16 * sc
    painter.setPen(QPen(QColor(150, 155, 170), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(245, 247, 252))
    painter.drawPolygon(QPolygonF([QPointF(-s, 0), QPointF(s, -s * 0.2), QPointF(-s * 0.2, s * 0.12)]))
    painter.setBrush(QColor(224, 228, 238))
    painter.drawPolygon(QPolygonF([QPointF(-s, 0), QPointF(-s * 0.2, s * 0.12), QPointF(-s * 0.5, s * 0.42)]))
    painter.setPen(QPen(QColor(170, 175, 190), max(0.8, bw * 0.005)))
    painter.drawLine(QPointF(-s, 0), QPointF(s, -s * 0.2))
    painter.restore()


def draw_kite(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """放风筝 跑 放线 高飞"""
    sway = math.sin(t * 1.2) * bw * 0.10
    if stage == "run":
        kx = bw * (0.15 + 0.32 * stage_p) + sway
        ky = -bh * (0.45 + 0.5 * stage_p)
    else:
        kx, ky = bw * 0.46 + sway, -bh * 0.98
    hand = QPointF(bw * 0.20, bh * 0.12)
    pen = QPen(QColor(150, 150, 165), max(0.9, bw * 0.006))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(hand)
    path.quadTo(QPointF((hand.x() + kx) / 2, ky + bh * 0.55), QPointF(kx, ky + bw * 0.18))
    painter.drawPath(path)
    s = bw * 0.16
    painter.save()
    painter.translate(kx, ky)
    painter.rotate(sway * 0.5)
    painter.setPen(QPen(QColor(180, 90, 80), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(236, 120, 108))
    painter.drawPolygon(QPolygonF([QPointF(0, -s * 1.3), QPointF(s, 0), QPointF(0, s * 1.05), QPointF(-s, 0)]))
    painter.setPen(QPen(QColor(160, 80, 72, 180), max(0.8, bw * 0.005)))
    painter.drawLine(QPointF(0, -s * 1.3), QPointF(0, s * 1.05))
    painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
    painter.restore()
    pen2 = QPen(QColor(236, 120, 108), max(0.9, bw * 0.006))
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen2)
    tail = QPainterPath(QPointF(kx, ky + s * 1.05))
    for j in range(1, 4):
        tail.lineTo(QPointF(kx + math.sin(t * 3 + j) * bw * 0.05, ky + s * 1.05 + j * bh * 0.13))
    painter.drawPath(tail)


def draw_yoyo(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩悠悠球 抛 空转 收"""
    hand = QPointF(bw * 0.28, bh * 0.04)
    if stage == "throw":
        d = ease_out(stage_p)
    elif stage == "sleep":
        d = 1.0 + math.sin(t * 2.2) * 0.04
    else:  # back
        d = 1.0 - ease_in(stage_p)
    yx, yy = hand.x() + bw * 0.02, hand.y() + bh * (0.12 + 0.52 * d)
    painter.setPen(QPen(QColor(160, 160, 175), max(0.8, bw * 0.005)))
    painter.drawLine(hand, QPointF(yx, yy))
    painter.save()
    painter.translate(yx, yy)
    painter.rotate((t * 420) % 360)
    painter.setPen(QPen(QColor(60, 110, 170), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(88, 152, 222))
    painter.drawEllipse(QPointF(0, 0), bw * 0.09, bw * 0.09)
    painter.setPen(QPen(QColor(255, 255, 255, 160), max(1.0, bw * 0.01)))
    painter.drawLine(QPointF(-bw * 0.05, 0), QPointF(bw * 0.05, 0))
    painter.restore()


def draw_blocks(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """堆积木 一块块往上摞"""
    bx = bw * 0.34
    s = bw * 0.13
    cols = [QColor(232, 120, 120), QColor(120, 180, 230), QColor(245, 205, 110), QColor(140, 200, 150)]
    placed = int(stage_p * 4) + 1 if stage == "stack" else 4
    placed = max(1, min(4, placed))
    for i in range(placed):
        y = bh * 0.30 - i * s
        off = math.sin(t * 1.5 + i) * bw * 0.01
        painter.setPen(QPen(QColor(90, 90, 100), max(0.9, bw * 0.006)))
        painter.setBrush(cols[i % len(cols)])
        painter.drawRoundedRect(QRectF(bx - s / 2 + off, y - s, s, s), bw * 0.012, bw * 0.012)
    if stage == "stack" and placed < 4:
        carry = QPointF(bw * 0.10, bh * 0.30 - placed * s - bh * (0.2 * (1 - stage_p % 0.25 * 4)))
        painter.setPen(QPen(QColor(90, 90, 100), max(0.9, bw * 0.006)))
        painter.setBrush(cols[placed % len(cols)])
        painter.drawRoundedRect(QRectF(carry.x() - s / 2, carry.y() - s, s, s), bw * 0.012, bw * 0.012)


def draw_pinwheel(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """风车 举着转 风一吹就快"""
    cx, cy = bw * 0.34, -bh * 0.08
    painter.setPen(QPen(QColor(180, 150, 120), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(cx, cy), QPointF(cx - bw * 0.03, bh * 0.30))
    spin = (t * (260 if stage == "spin" else 90)) % 360
    cols = [QColor(232, 120, 120), QColor(120, 180, 230), QColor(245, 205, 110), QColor(140, 200, 150)]
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(spin)
    r = bw * 0.13
    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(4):
        painter.setBrush(cols[i])
        painter.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(r, -r * 0.35), QPointF(r * 0.7, r * 0.2)]))
        painter.rotate(90)
    painter.setBrush(QColor(90, 90, 100))
    painter.drawEllipse(QPointF(0, 0), bw * 0.02, bw * 0.02)
    painter.restore()


def draw_rubik(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩魔方 拧顶层"""
    cx, cy = bw * 0.30, 0.0
    s = bw * 0.10
    cols = [QColor(232, 90, 90), QColor(245, 205, 110), QColor(120, 180, 230),
            QColor(140, 200, 150), QColor(248, 248, 248), QColor(255, 150, 80)]
    twist = math.sin(t * 3) * s * 0.5 if stage == "turn" else 0.0
    for ry in range(3):
        for rx in range(3):
            x, y = (rx - 1) * s, (ry - 1) * s
            if stage == "turn" and ry == 0:
                x += twist
            painter.setPen(QPen(QColor(40, 40, 45), max(1.0, bw * 0.007)))
            painter.setBrush(cols[(rx + ry * 3) % len(cols)])
            painter.drawRoundedRect(QRectF(cx + x - s * 0.46, cy + y - s * 0.46, s * 0.92, s * 0.92), s * 0.12, s * 0.12)


def draw_ringtoss(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """套圈 一个个圈往桩子上飞"""
    px = bw * 0.38
    painter.setPen(QPen(QColor(170, 120, 80), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(px, bh * 0.30), QPointF(px, -bh * 0.18))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(170, 120, 80))
    painter.drawEllipse(QPointF(px, -bh * 0.18), bw * 0.03, bw * 0.02)
    cols = [QColor(232, 120, 120), QColor(120, 180, 230), QColor(245, 205, 110)]
    landed = int(stage_p * 3) if stage == "toss" else 3
    for i in range(landed):
        y = bh * 0.26 - i * bh * 0.07
        painter.setPen(QPen(cols[i % 3], max(1.6, bw * 0.014)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(px, y), bw * 0.10, bw * 0.045)
    if stage == "toss" and landed < 3:
        ph = (t * 1.2) % 1.0
        fx = bw * 0.12 + (px - bw * 0.12) * ph
        fy = bh * 0.1 - bh * 0.4 * math.sin(ph * math.pi)
        painter.setPen(QPen(cols[landed % 3], max(1.6, bw * 0.014)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(fx, fy), bw * 0.10, bw * 0.045)


def draw_spintop(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩陀螺 嗡嗡转"""
    cx, cy = bw * 0.32, bh * 0.18
    wob = math.sin(t * 3) * bw * 0.02 if stage == "spin" else 0.0
    painter.save()
    painter.translate(cx + wob, cy)
    painter.rotate(math.sin(t * 1.5) * 8 if stage == "spin" else 12)
    painter.setPen(QPen(QColor(150, 90, 60), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 152, 92))
    painter.drawChord(QRectF(-bw * 0.10, -bh * 0.12, bw * 0.20, bh * 0.18), 0, 180 * 16)
    painter.setBrush(QColor(202, 132, 82))
    painter.drawPolygon(QPolygonF([QPointF(-bw * 0.10, -bh * 0.03), QPointF(bw * 0.10, -bh * 0.03), QPointF(0, bh * 0.10)]))
    if stage == "spin":
        painter.setPen(QPen(QColor(120, 180, 230, 180), max(1.0, bw * 0.008)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(-bw * 0.12, -bh * 0.10, bw * 0.24, bh * 0.06), 200 * 16, 80 * 16)
    painter.restore()
    if stage == "spin":
        painter.setPen(QPen(QColor(180, 180, 195, 160), max(0.8, bw * 0.005)))
        for s in (-1, 1):
            painter.drawArc(QRectF(cx - bw * 0.16, cy - bh * 0.08, bw * 0.32, bh * 0.16), (90 + s * 40) * 16, 30 * 16)


def draw_cards(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩扑克 摊开一把牌"""
    cx, cy = bw * 0.30, bh * 0.08
    pips = [QColor(60, 60, 70), QColor(214, 70, 72), QColor(60, 60, 70), QColor(214, 70, 72), QColor(214, 70, 72)]
    spread = 16 if stage == "fan" else 8
    for i in range(5):
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-(spread * 2) + i * spread)
        painter.setPen(QPen(QColor(190, 190, 200), max(0.8, bw * 0.005)))
        painter.setBrush(QColor(252, 252, 255))
        painter.drawRoundedRect(QRectF(-bw * 0.055, -bh * 0.22, bw * 0.11, bh * 0.22), bw * 0.015, bw * 0.015)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pips[i])
        painter.drawEllipse(QPointF(0, -bh * 0.13), bw * 0.02, bw * 0.024)
        painter.restore()


def draw_matryoshka(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """套娃 一开俩"""
    def doll(dx, scale):
        cx = bw * 0.30 + dx
        painter.setPen(QPen(QColor(190, 90, 80), max(1.0, bw * 0.007)))
        painter.setBrush(QColor(232, 120, 100))
        painter.drawEllipse(QPointF(cx, 0), bw * 0.12 * scale, bh * 0.22 * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(252, 224, 200))
        painter.drawEllipse(QPointF(cx, -bh * 0.10 * scale), bw * 0.07 * scale, bh * 0.09 * scale)
        painter.setBrush(QColor(60, 55, 70))
        painter.drawEllipse(QPointF(cx - bw * 0.025 * scale, -bh * 0.10 * scale), bw * 0.01 * scale, bw * 0.013 * scale)
        painter.drawEllipse(QPointF(cx + bw * 0.025 * scale, -bh * 0.10 * scale), bw * 0.01 * scale, bw * 0.013 * scale)
        painter.setBrush(QColor(245, 205, 110))
        painter.drawEllipse(QPointF(cx, bh * 0.05 * scale), bw * 0.035 * scale, bw * 0.035 * scale)
    if stage == "open":
        doll(-bw * 0.17, 0.62)
        doll(bw * 0.03, 1.0)
    else:
        doll(0.0, 1.0)


def draw_frisbee(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩飞盘 划弧飞出去"""
    ph = stage_p if stage == "throw" else (t * 0.6) % 1.0
    fx = bw * 0.10 + ph * bw * 0.5
    fy = bh * 0.05 - bh * 0.5 * math.sin(ph * math.pi)
    painter.save()
    painter.translate(fx, fy)
    painter.rotate(math.sin(t * 4) * 10)
    painter.setPen(QPen(QColor(180, 90, 90), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(232, 120, 120))
    painter.drawEllipse(QPointF(0, 0), bw * 0.11, bw * 0.045)
    painter.setBrush(QColor(248, 182, 182))
    painter.drawEllipse(QPointF(0, -bw * 0.008), bw * 0.07, bw * 0.025)
    painter.restore()
    if stage == "throw":
        painter.setPen(QPen(QColor(200, 150, 150, 120), max(0.8, bw * 0.005)))
        painter.drawLine(QPointF(fx - bw * 0.12, fy + bw * 0.02), QPointF(fx - bw * 0.06, fy))


def draw_paperboat(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """放纸船 在水波上漂"""
    cx, cy = bw * 0.32, bh * 0.14
    bob = math.sin(t * 1.6) * bh * 0.02
    painter.setPen(QPen(QColor(150, 195, 225, 180), max(1.0, bw * 0.008)))
    for k in range(2):
        painter.drawArc(QRectF(cx - bw * 0.22, cy + bh * 0.08 + k * bh * 0.05, bw * 0.18, bh * 0.04), 0, 180 * 16)
        painter.drawArc(QRectF(cx + bw * 0.04, cy + bh * 0.08 + k * bh * 0.05, bw * 0.18, bh * 0.04), 0, 180 * 16)
    painter.save()
    painter.translate(0, bob)
    painter.setPen(QPen(QColor(150, 155, 170), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(248, 250, 255))
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.15, cy + bh * 0.04), QPointF(cx + bw * 0.15, cy + bh * 0.04),
                                   QPointF(cx + bw * 0.10, cy + bh * 0.12), QPointF(cx - bw * 0.10, cy + bh * 0.12)]))
    painter.setBrush(QColor(236, 238, 245))
    painter.drawPolygon(QPolygonF([QPointF(cx, cy - bh * 0.12), QPointF(cx, cy + bh * 0.04), QPointF(cx - bw * 0.12, cy + bh * 0.04)]))
    painter.setBrush(QColor(224, 228, 238))
    painter.drawPolygon(QPolygonF([QPointF(cx, cy - bh * 0.12), QPointF(cx, cy + bh * 0.04), QPointF(cx + bw * 0.12, cy + bh * 0.04)]))
    painter.restore()


def draw_darts(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩飞镖 镖飞向靶心"""
    bx, by = bw * 0.40, -bh * 0.05
    painter.setPen(Qt.PenStyle.NoPen)
    for r, c in ((bw * 0.15, QColor(60, 70, 60)), (bw * 0.11, QColor(240, 235, 225)),
                 (bw * 0.07, QColor(60, 70, 60)), (bw * 0.035, QColor(232, 90, 90))):
        painter.setBrush(c)
        painter.drawEllipse(QPointF(bx, by), r, r)
    if stage == "throw":
        ph = (t * 1.5) % 1.0
        dx, dy = bw * 0.1 + (bx - bw * 0.1) * ph, bh * 0.05 - (bh * 0.05 - by) * ph
    else:
        dx, dy = bx + bw * 0.03, by - bw * 0.03
    painter.setPen(QPen(QColor(80, 80, 90), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(dx - bw * 0.06, dy + bw * 0.06), QPointF(dx, dy))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(232, 120, 90))
    painter.drawPolygon(QPolygonF([QPointF(dx - bw * 0.06, dy + bw * 0.06), QPointF(dx - bw * 0.095, dy + bw * 0.04),
                                   QPointF(dx - bw * 0.04, dy + bw * 0.095)]))


def draw_snowglobe(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """雪花球 摇一摇 雪花落"""
    cx, cy = bw * 0.30, 0.0
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(150, 110, 80))
    painter.drawRoundedRect(QRectF(cx - bw * 0.12, bh * 0.14, bw * 0.24, bh * 0.08), bw * 0.02, bw * 0.02)
    painter.setPen(QPen(QColor(180, 200, 220), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(206, 226, 240, 170))
    painter.drawEllipse(QPointF(cx, cy), bw * 0.15, bh * 0.18)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(112, 172, 112))
    painter.drawPolygon(QPolygonF([QPointF(cx, cy - bh * 0.06), QPointF(cx - bw * 0.06, cy + bh * 0.06),
                                   QPointF(cx + bw * 0.06, cy + bh * 0.06)]))
    painter.setBrush(QColor(255, 255, 255, 220))
    for k in range(7):
        ph = (t * 0.5 + k * 0.14) % 1.0
        sx = cx + math.sin(k * 2.0) * bw * 0.10
        sy = cy - bh * 0.14 + ph * bh * 0.30
        painter.drawEllipse(QPointF(sx, sy), bw * 0.012, bw * 0.012)
    painter.setBrush(QColor(255, 255, 255, 120))
    painter.drawEllipse(QPointF(cx - bw * 0.06, cy - bh * 0.08), bw * 0.03, bh * 0.03)


def draw_piggybank(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """存钱罐 投硬币"""
    cx, cy = bw * 0.30, bh * 0.06
    painter.setPen(QPen(QColor(220, 150, 170), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(244, 180, 200))
    painter.drawEllipse(QPointF(cx, cy), bw * 0.16, bh * 0.16)
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.10, cy - bh * 0.10), QPointF(cx - bw * 0.03, cy - bh * 0.13),
                                   QPointF(cx - bw * 0.05, cy - bh * 0.05)]))
    painter.setBrush(QColor(238, 165, 188))
    painter.drawEllipse(QPointF(cx + bw * 0.14, cy), bw * 0.05, bh * 0.06)
    for dx in (-0.08, 0.06):
        painter.drawRect(QRectF(cx + dx * bw, cy + bh * 0.12, bw * 0.04, bh * 0.05))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(206, 138, 158))
    painter.drawEllipse(QPointF(cx + bw * 0.132, cy - bh * 0.01), bw * 0.011, bw * 0.011)
    painter.drawEllipse(QPointF(cx + bw * 0.150, cy - bh * 0.01), bw * 0.011, bw * 0.011)
    painter.setPen(QPen(QColor(190, 120, 140), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(cx - bw * 0.03, cy - bh * 0.14), QPointF(cx + bw * 0.03, cy - bh * 0.14))
    if stage == "save":
        ph = (t * 1.0) % 1.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(245, 205, 110))
        painter.drawEllipse(QPointF(cx, cy - bh * 0.30 + ph * bh * 0.15), bw * 0.03, bw * 0.035)


def draw_sheep(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """数羊 蓬蓬羊跳过去"""
    ph = (t * 0.5) % 1.0
    sx = bw * 0.5 - ph * bw * 0.95
    sy = -bh * 0.55 - abs(math.sin(ph * math.pi * 3)) * bh * 0.10
    painter.save()
    painter.translate(sx, sy)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(248, 248, 250))
    for a in range(0, 360, 60):
        aa = math.radians(a)
        painter.drawEllipse(QPointF(math.cos(aa) * bw * 0.05, math.sin(aa) * bw * 0.04), bw * 0.05, bw * 0.05)
    painter.drawEllipse(QPointF(0, 0), bw * 0.08, bw * 0.07)
    painter.setBrush(QColor(72, 66, 82))
    painter.drawEllipse(QPointF(-bw * 0.09, -bw * 0.01), bw * 0.035, bw * 0.045)
    painter.setPen(QPen(QColor(72, 66, 82), max(1.0, bw * 0.008)))
    for dx in (-0.04, 0.04):
        painter.drawLine(QPointF(dx * bw, bw * 0.06), QPointF(dx * bw, bw * 0.12))
    painter.restore()


def draw_crane(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """折纸鹤 棱角分明的小纸鹤"""
    cx, cy = bw * 0.30, bh * 0.02
    bob = math.sin(t * 2) * bh * 0.02 if stage == "fold" else 0.0
    painter.save()
    painter.translate(cx, cy + bob)
    painter.setPen(QPen(QColor(200, 120, 150), max(0.9, bw * 0.006)))
    painter.setBrush(QColor(245, 202, 216))
    painter.drawPolygon(QPolygonF([QPointF(0, -bh * 0.06), QPointF(bw * 0.08, 0), QPointF(0, bh * 0.08), QPointF(-bw * 0.08, 0)]))
    painter.setBrush(QColor(249, 217, 228))
    painter.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(-bw * 0.16, -bh * 0.10), QPointF(-bw * 0.02, -bh * 0.02)]))
    painter.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(bw * 0.16, -bh * 0.10), QPointF(bw * 0.02, -bh * 0.02)]))
    painter.setPen(QPen(QColor(200, 120, 150), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(-bw * 0.06, bh * 0.02), QPointF(-bw * 0.14, -bh * 0.05))
    painter.drawLine(QPointF(bw * 0.06, bh * 0.02), QPointF(bw * 0.13, bh * 0.07))
    painter.restore()


def draw_lantern(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """提红灯笼 微微晃 点亮发光"""
    cx, cy = bw * 0.32, -bh * 0.04
    painter.setPen(QPen(QColor(150, 110, 70), max(1.0, bw * 0.008)))
    painter.drawLine(QPointF(bw * 0.18, bh * 0.06), QPointF(cx, cy - bh * 0.22))
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(math.sin(t * 1.3) * 5)
    if stage == "light":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 200, 120, 70))
        painter.drawEllipse(QPointF(0, 0), bw * 0.22, bw * 0.22)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(240, 205, 110))
    painter.drawRect(QRectF(-bw * 0.06, -bh * 0.21, bw * 0.12, bh * 0.035))
    painter.drawRect(QRectF(-bw * 0.06, bh * 0.16, bw * 0.12, bh * 0.035))
    painter.setPen(QPen(QColor(170, 40, 40), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 72, 72))
    painter.drawEllipse(QPointF(0, 0), bw * 0.13, bh * 0.18)
    painter.setPen(QPen(QColor(180, 50, 50, 170), max(0.7, bw * 0.004)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(0, 0), bw * 0.06, bh * 0.18)
    painter.setPen(QPen(QColor(220, 180, 80), max(1.0, bw * 0.007)))
    painter.drawLine(QPointF(0, bh * 0.20), QPointF(0, bh * 0.30))
    painter.restore()
