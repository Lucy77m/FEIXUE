# author: bdth
# email: 2074055628@qq.com
# 文艺手作类 乐器 拍照 画画 写字 织毛线 浇花

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from desktop_pet.pet.behaviors.easing import ease_out
from desktop_pet.pet.props.common import draw_note


def draw_camera(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举相机拍照 取景 咔嚓闪光"""
    if stage == "flash":
        k = max(0.0, 1.0 - stage_p * 1.6)
        if k > 0.0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 235, int(120 * k)))
            rr = bw * 0.5 * (1.0 + stage_p)
            painter.drawEllipse(QPointF(-bw * 0.40, -bh * 0.10), rr, rr)
    cy = bh * 0.0
    cw, ch = bw * 0.30, bh * 0.26
    painter.setPen(QPen(QColor(70, 72, 84), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(96, 98, 112))
    painter.drawRoundedRect(QRectF(-cw, cy - ch * 0.5, cw * 2, ch), bw * 0.03, bw * 0.03)
    painter.setBrush(QColor(70, 72, 84))
    painter.drawRoundedRect(QRectF(cw * 0.35, cy - ch * 0.5 - bh * 0.05, cw * 0.55, bh * 0.05), 2, 2)
    painter.setBrush(QColor(206, 86, 86))
    painter.drawEllipse(QPointF(cw * 0.62, cy - ch * 0.5 - bh * 0.025), bw * 0.022, bw * 0.022)
    painter.setBrush(QColor(58, 60, 72))
    painter.drawEllipse(QPointF(0, cy), bw * 0.12, bw * 0.12)
    painter.setBrush(QColor(120, 142, 162))
    painter.drawEllipse(QPointF(0, cy), bw * 0.075, bw * 0.075)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 170))
    painter.drawEllipse(QPointF(-bw * 0.035, cy - bw * 0.035), bw * 0.026, bw * 0.026)


def draw_guitar(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """抱吉他 调弦 扫弦带音符"""
    painter.save()
    painter.translate(bw * 0.04, bh * 0.10)
    painter.rotate(-22)
    painter.setPen(QPen(QColor(150, 100, 60), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(198, 142, 86))
    painter.drawEllipse(QPointF(0, bh * 0.06), bw * 0.16, bh * 0.17)
    painter.drawEllipse(QPointF(0, -bh * 0.05), bw * 0.115, bh * 0.12)
    painter.setBrush(QColor(82, 56, 40))
    painter.drawEllipse(QPointF(0, bh * 0.03), bw * 0.045, bw * 0.045)
    painter.setBrush(QColor(120, 82, 52))
    painter.drawRect(QRectF(-bw * 0.018, -bh * 0.42, bw * 0.036, bh * 0.34))
    painter.drawRoundedRect(QRectF(-bw * 0.032, -bh * 0.48, bw * 0.064, bh * 0.07), 2, 2)
    sh = math.sin(t * 13) * bw * 0.005 if stage == "strum" else 0.0
    painter.setPen(QPen(QColor(232, 226, 214, 200), max(0.6, bw * 0.004)))
    for k in range(3):
        painter.drawLine(QPointF(-bw * 0.012 + k * bw * 0.012, -bh * 0.40),
                         QPointF(-bw * 0.012 + k * bw * 0.012 + sh, bh * 0.14))
    painter.restore()
    if stage == "strum":
        draw_note(painter, QPointF(bw * 0.30, -bh * 0.22 + math.sin(t * 3) * bh * 0.04),
                  bw, bh, QColor(150, 130, 210), double=False)


def draw_harmonica(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹口琴 左右拉 冒音符"""
    cx, cy = bw * 0.28, bh * 0.06
    slide = math.sin(t * 6) * bw * 0.03 if stage == "play" else 0.0
    painter.setPen(QPen(QColor(110, 120, 140), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(152, 162, 182))
    painter.drawRoundedRect(QRectF(cx - bw * 0.13 + slide, cy - bh * 0.04, bw * 0.26, bh * 0.08), bw * 0.015, bw * 0.015)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(60, 66, 78))
    for k in range(6):
        painter.drawRect(QRectF(cx - bw * 0.11 + slide + k * bw * 0.036, cy - bh * 0.015, bw * 0.022, bh * 0.03))
    if stage == "play":
        draw_note(painter, QPointF(cx + bw * 0.22, cy - bh * 0.18 + math.sin(t * 3) * bh * 0.03),
                  bw, bh, QColor(150, 130, 210), double=False)


def draw_trumpet(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹小喇叭 滴答冒音符"""
    cx, cy = bw * 0.20, bh * 0.04
    painter.setPen(QPen(QColor(200, 160, 70), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(240, 202, 98))
    painter.drawRoundedRect(QRectF(cx, cy - bh * 0.03, bw * 0.18, bh * 0.06), bw * 0.02, bw * 0.02)
    bx = cx + bw * 0.18
    painter.drawPolygon(QPolygonF([QPointF(bx, cy - bh * 0.04), QPointF(bx, cy + bh * 0.04),
                                   QPointF(bx + bw * 0.12, cy + bh * 0.11), QPointF(bx + bw * 0.12, cy - bh * 0.11)]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(200, 160, 70))
    for k in range(3):
        painter.drawRect(QRectF(cx + bw * 0.04 + k * bw * 0.04, cy - bh * 0.07, bw * 0.02, bh * 0.05))
    if stage == "play":
        draw_note(painter, QPointF(cx + bw * 0.36, cy - bh * 0.16 + math.sin(t * 3) * bh * 0.03),
                  bw, bh, QColor(150, 130, 210), double=False)


def draw_piano(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """弹钢琴 小键盘 按键冒音符"""
    cx, cy = bw * 0.30, bh * 0.08
    kw, nk = bw * 0.30, 7
    painter.setPen(QPen(QColor(180, 180, 190), max(0.8, bw * 0.005)))
    painter.setBrush(QColor(250, 250, 252))
    painter.drawRoundedRect(QRectF(cx - kw / 2, cy - bh * 0.05, kw, bh * 0.14), bw * 0.01, bw * 0.01)
    painter.setPen(QPen(QColor(205, 205, 215), max(0.7, bw * 0.004)))
    for k in range(1, nk):
        x = cx - kw / 2 + k * kw / nk
        painter.drawLine(QPointF(x, cy - bh * 0.05), QPointF(x, cy + bh * 0.09))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(50, 50, 60))
    for k in (1, 2, 4, 5, 6):
        x = cx - kw / 2 + k * kw / nk - kw / nk * 0.28
        painter.drawRect(QRectF(x, cy - bh * 0.05, kw / nk * 0.56, bh * 0.085))
    if stage == "play":
        draw_note(painter, QPointF(cx + kw * 0.5, cy - bh * 0.18 + math.sin(t * 3) * bh * 0.03),
                  bw, bh, QColor(150, 130, 210), double=False)


def draw_painting(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """支画架画画 涂涂抹抹"""
    ex = bw * 0.38
    painter.setPen(QPen(QColor(150, 110, 70), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(ex - bw * 0.10, bh * 0.34), QPointF(ex, -bh * 0.28))
    painter.drawLine(QPointF(ex + bw * 0.10, bh * 0.34), QPointF(ex, -bh * 0.28))
    painter.drawLine(QPointF(ex + bw * 0.05, bh * 0.34), QPointF(ex, -bh * 0.02))
    painter.setPen(QPen(QColor(170, 150, 120), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(250, 248, 242))
    painter.drawRect(QRectF(ex - bw * 0.14, -bh * 0.24, bw * 0.28, bh * 0.32))
    painter.setPen(Qt.PenStyle.NoPen)
    k = stage_p if stage == "paint" else 1.0
    for col, dx, dy in ((QColor(232, 110, 120), -0.04, -0.06), (QColor(120, 180, 230), 0.05, 0.02),
                        (QColor(250, 205, 110), -0.02, 0.08)):
        painter.setBrush(col)
        painter.drawEllipse(QPointF(ex + dx * bw, -bh * 0.08 + dy * bh), bw * 0.032 * k, bw * 0.032 * k)
    if stage == "paint":
        bxp = ex + math.sin(t * 4) * bw * 0.05
        painter.setPen(QPen(QColor(150, 110, 70), max(1.2, bw * 0.01)))
        painter.drawLine(QPointF(bxp, -bh * 0.04), QPointF(bxp + bw * 0.12, bh * 0.12))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(232, 110, 120))
        painter.drawEllipse(QPointF(bxp, -bh * 0.05), bw * 0.018, bw * 0.026)


def draw_calligraphy(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """写书法 宣纸+毛笔 一笔笔落墨"""
    px = bw * 0.34
    painter.setPen(QPen(QColor(210, 200, 180), max(0.8, bw * 0.005)))
    painter.setBrush(QColor(250, 248, 240))
    painter.drawRect(QRectF(px - bw * 0.12, -bh * 0.12, bw * 0.24, bh * 0.40))
    prog = stage_p if stage == "write" else 1.0
    painter.setPen(QPen(QColor(40, 40, 45), max(2.0, bw * 0.02)))
    painter.drawLine(QPointF(px, -bh * 0.06), QPointF(px, -bh * 0.06 + bh * 0.24 * min(1.0, prog * 2)))
    if prog > 0.5:
        painter.drawLine(QPointF(px - bw * 0.08, bh * 0.04),
                         QPointF(px - bw * 0.08 + bw * 0.16 * ((prog - 0.5) * 2), bh * 0.04))
    bxp = px + (math.sin(t * 2) * bw * 0.02 if stage == "write" else 0.0)
    painter.setPen(QPen(QColor(150, 110, 70), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(bxp + bw * 0.06, -bh * 0.30), QPointF(bxp, bh * 0.06))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(40, 40, 45))
    painter.drawEllipse(QPointF(bxp, bh * 0.06), bw * 0.016, bw * 0.03)


def draw_knitting(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """织毛衣 两针+织片+毛线团"""
    cx, cy = bw * 0.30, bh * 0.06
    painter.setPen(QPen(QColor(180, 110, 130), max(0.8, bw * 0.005)))
    painter.setBrush(QColor(226, 140, 160))
    painter.drawRoundedRect(QRectF(cx - bw * 0.10, cy - bh * 0.02, bw * 0.20, bh * 0.14), bw * 0.02, bw * 0.02)
    painter.setPen(QPen(QColor(200, 120, 140, 170), max(0.6, bw * 0.004)))
    for k in range(3):
        painter.drawLine(QPointF(cx - bw * 0.08, cy + bh * 0.01 + k * bh * 0.04),
                         QPointF(cx + bw * 0.08, cy + bh * 0.01 + k * bh * 0.04))
    wob = math.sin(t * 4) * 6 if stage == "knit" else 0.0
    painter.setPen(QPen(QColor(182, 152, 122), max(1.2, bw * 0.01)))
    painter.save()
    painter.translate(cx - bw * 0.06, cy - bh * 0.02)
    painter.rotate(-35 + wob)
    painter.drawLine(QPointF(0, 0), QPointF(0, -bh * 0.22))
    painter.restore()
    painter.save()
    painter.translate(cx + bw * 0.06, cy - bh * 0.02)
    painter.rotate(35 - wob)
    painter.drawLine(QPointF(0, 0), QPointF(0, -bh * 0.22))
    painter.restore()
    painter.setPen(QPen(QColor(170, 78, 92), max(0.9, bw * 0.006)))
    painter.setBrush(QColor(226, 128, 142))
    painter.drawEllipse(QPointF(cx - bw * 0.01, cy + bh * 0.21), bw * 0.06, bw * 0.06)


def draw_phone(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩手机 戳屏 冒小爱心"""
    cx, cy = bw * 0.30, bh * 0.02
    pw, pht = bw * 0.16, bh * 0.30
    painter.setPen(QPen(QColor(60, 62, 74), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(50, 52, 64))
    painter.drawRoundedRect(QRectF(cx - pw / 2, cy - pht / 2, pw, pht), bw * 0.02, bw * 0.02)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(150, 200, 250, 185 if stage == "tap" else 135))
    painter.drawRoundedRect(QRectF(cx - pw * 0.38, cy - pht * 0.40, pw * 0.76, pht * 0.72), bw * 0.01, bw * 0.01)
    if stage == "tap":
        for k in range(3):
            pp = (t * 0.8 + k * 0.33) % 1.0
            painter.setBrush(QColor(240, 120, 140, int(200 * (1 - pp))))
            painter.drawEllipse(QPointF(cx + math.sin(t + k) * bw * 0.03, cy - pht * 0.4 - pp * bh * 0.20),
                                bw * 0.02, bw * 0.02)


def draw_watering(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """浇花 举喷壶 浇水 嫩芽冒头"""
    px = bw * 0.40
    grow = ease_out(stage_p) if stage == "grow" else (0.4 if stage == "pour" else 0.2)
    painter.setPen(QPen(QColor(170, 110, 80), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(206, 134, 96))
    painter.drawPolygon(QPolygonF([QPointF(px - bw * 0.09, bh * 0.18), QPointF(px + bw * 0.09, bh * 0.18),
                                   QPointF(px + bw * 0.07, bh * 0.34), QPointF(px - bw * 0.07, bh * 0.34)]))
    painter.drawRect(QRectF(px - bw * 0.10, bh * 0.13, bw * 0.20, bh * 0.06))
    stem_top = bh * 0.16 - bh * 0.18 * grow
    painter.setPen(QPen(QColor(110, 170, 100), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(px, bh * 0.16), QPointF(px, stem_top))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(140, 196, 120))
    painter.drawEllipse(QPointF(px - bw * 0.045, stem_top + bh * 0.03), bw * 0.045, bw * 0.028)
    painter.drawEllipse(QPointF(px + bw * 0.045, stem_top + bh * 0.01), bw * 0.045, bw * 0.028)
    cx, cy = bw * 0.10, -bh * 0.12
    painter.setPen(QPen(QColor(110, 150, 180), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(152, 192, 216))
    painter.drawRoundedRect(QRectF(cx - bw * 0.10, cy - bh * 0.06, bw * 0.18, bh * 0.15), bw * 0.02, bw * 0.02)
    painter.drawLine(QPointF(cx + bw * 0.07, cy - bh * 0.02), QPointF(px - bw * 0.05, bh * 0.0))
    painter.drawArc(QRectF(cx - bw * 0.12, cy - bh * 0.05, bw * 0.10, bh * 0.12), 90 * 16, 160 * 16)
    if stage == "pour":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(150, 200, 235, 200))
        for k in range(4):
            ph = (t * 1.3 + k * 0.25) % 1.0
            painter.drawEllipse(QPointF(px - bw * 0.05 + k * bw * 0.012, bh * 0.0 + ph * bh * 0.14),
                                bw * 0.012, bw * 0.02)


def draw_dandelion(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹蒲公英 举着 吹散 看种子飘"""
    head = QPointF(bw * 0.30, -bh * 0.06)
    painter.setPen(QPen(QColor(120, 170, 110), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(head.x(), head.y() + bw * 0.05), QPointF(head.x() - bw * 0.04, bh * 0.30))
    remain = (1.0 - stage_p) if stage == "blow" else 1.0
    for k in range(28):
        if k / 28.0 > remain:
            continue
        ang = k / 28.0 * 2 * math.pi
        rr = bw * 0.09
        tipp = QPointF(head.x() + math.cos(ang) * rr, head.y() + math.sin(ang) * rr)
        painter.setPen(QPen(QColor(218, 224, 230, 200), max(0.7, bw * 0.004)))
        painter.drawLine(head, tipp)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(246, 248, 251, 225))
        painter.drawEllipse(tipp, bw * 0.012, bw * 0.012)
    if stage in ("blow", "watch"):
        for s in range(6):
            ph = (t * 0.4 + s * 0.2) % 1.0
            sx = head.x() + bw * (0.1 + 0.5 * ph)
            sy = head.y() - bh * (0.2 + 0.8 * ph)
            painter.setPen(QPen(QColor(218, 224, 230, int(150 * (1 - ph))), max(0.6, bw * 0.004)))
            painter.drawLine(QPointF(sx, sy), QPointF(sx - bw * 0.03, sy + bw * 0.03))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(246, 248, 251, int(190 * (1 - ph))))
            painter.drawEllipse(QPointF(sx, sy), bw * 0.012, bw * 0.012)


def draw_bouquet(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """捧花 一小束 微微晃"""
    cx = bw * 0.30
    sway = math.sin(t * 1.4) * bw * 0.01
    painter.setPen(QPen(QColor(200, 180, 150), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(240, 226, 200))
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.06, bh * 0.04), QPointF(cx + bw * 0.06, bh * 0.04),
                                   QPointF(cx, bh * 0.30)]))
    pos = [(-0.07, -0.06), (0.07, -0.05), (0.0, -0.12)]
    fcols = [QColor(236, 110, 130), QColor(245, 205, 110), QColor(182, 150, 230)]
    painter.setPen(QPen(QColor(120, 170, 100), max(1.0, bw * 0.007)))
    for dx, dy in pos:
        painter.drawLine(QPointF(cx, bh * 0.06), QPointF(cx + dx * bw + sway, bh * 0.04 + dy * bh))
    painter.setPen(Qt.PenStyle.NoPen)
    for i, (dx, dy) in enumerate(pos):
        fx, fy = cx + dx * bw + sway, bh * 0.04 + dy * bh
        painter.setBrush(fcols[i])
        for a in range(0, 360, 72):
            aa = math.radians(a)
            painter.drawEllipse(QPointF(fx + math.cos(aa) * bw * 0.035, fy + math.sin(aa) * bw * 0.035),
                                bw * 0.028, bw * 0.028)
        painter.setBrush(QColor(250, 235, 180))
        painter.drawEllipse(QPointF(fx, fy), bw * 0.022, bw * 0.022)
