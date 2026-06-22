# 带阶段演出的活动道具 咖啡 看书 听歌 钓鱼 打游戏 观星 侦探 还有讲课教鞭

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet import palette
from desktop_pet.pet.behaviors.easing import ease_in, ease_out
from desktop_pet.pet.props.common import draw_note, draw_spark


def draw_coffee(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画咖啡 pour 倒水 sip lift 端起来喝"""
    p = stage_p
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.02))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    cw, ch = bw * 0.34, bh * 0.32


    if stage == "sip":
        sip_lift = (math.sin(p * math.pi * 3) * 0.5 + 0.5)  # 抿三口
        mug_y = bh * 0.30 - sip_lift * bh * 0.20
        fill = 0.85
    elif stage == "lift":
        mug_y = bh * 0.30 - ease_out(p) * bh * 0.06
        fill = 0.85
    else:  # pour 液面随 p 涨
        mug_y = bh * 0.34
        fill = 0.15 + 0.7 * p
    cup = QRectF(-cw / 2, mug_y, cw, ch)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(cup.right() - bw * 0.02, cup.center().y() - bh * 0.085, bw * 0.13, bh * 0.17))
    painter.setBrush(QColor(238, 240, 244))
    painter.drawRoundedRect(cup, bw * 0.055, bw * 0.055)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(96, 60, 36))
    surf_h = (ch - bh * 0.05) * fill
    painter.drawRoundedRect(
        QRectF(cup.left() + bw * 0.04, cup.bottom() - bh * 0.03 - surf_h, cup.width() - bw * 0.08, surf_h),
        bw * 0.02, bw * 0.02,
    )
    painter.setPen(pen)
    painter.setBrush(palette.SKIN)
    painter.drawEllipse(QPointF(cup.left() + bw * 0.005, cup.bottom() - bh * 0.05), bw * 0.075, bw * 0.075)

    if stage == "pour":
        _draw_kettle(painter, bw, bh, cup, p)


def _draw_kettle(painter: QPainter, bw: float, bh: float, cup: QRectF, p: float) -> None:
    """画倒水的壶 滑入悬停出水再滑出"""
    enter = ease_out(min(p / 0.25, 1.0))
    leave = max(0.0, (p - 0.8) / 0.2)
    kx = bw * 0.30 + (1 - enter) * bw * 0.5 + leave * bw * 0.5
    ky = -bh * 0.30 - (1 - enter) * bh * 0.3
    tilt = -38 * enter * (1 - leave)
    painter.save()
    painter.translate(kx, ky)
    painter.rotate(tilt)
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.02))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QColor(70, 130, 180))
    painter.drawRoundedRect(QRectF(-bw * 0.12, -bh * 0.11, bw * 0.24, bh * 0.22), bw * 0.05, bw * 0.05)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(-bw * 0.08, -bh * 0.22, bw * 0.16, bh * 0.16), 0, 180 * 16)
    spout = QPolygonF([
        QPointF(-bw * 0.12, -bh * 0.04), QPointF(-bw * 0.24, bh * 0.04), QPointF(-bw * 0.12, bh * 0.05),
    ])
    painter.setBrush(QColor(70, 130, 180))
    painter.drawPolygon(spout)
    painter.restore()

    if 0.2 < p < 0.85:  # 壶稳住这段才画水流
        stream = QPen(QColor(120, 80, 50))
        stream.setWidthF(max(1.5, bw * 0.016))
        stream.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(stream)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(kx - bw * 0.22, ky + bh * 0.04)
        path.quadTo(cup.center().x() + bw * 0.05, cup.top() - bh * 0.1, cup.center().x(), cup.top() + bh * 0.02)
        painter.drawPath(path)


def draw_book(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画翻书 open 从合到摊 其余阶段偶尔翻页"""
    p = stage_p

    opened = ease_out(p) if stage == "open" else 1.0
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.02))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    top = bh * 0.40
    spine = bh * 0.06 * opened
    outer = bh * 0.20 * opened
    ph = bh * 0.22
    pages = QColor(247, 245, 239)
    cover = QColor(150, 70, 64)
    line = QPen(QColor(176, 176, 182))
    line.setWidthF(max(1.0, bw * 0.01))


    painter.setPen(pen)
    painter.setBrush(cover)
    cov = bh * 0.215 * max(0.18, opened)
    painter.drawPolygon(QPolygonF([
        QPointF(-cov, top + spine - bh * 0.01), QPointF(cov, top + spine - bh * 0.01),
        QPointF(cov, top + ph + bh * 0.015), QPointF(-cov, top + ph + bh * 0.015),
    ]))

    def page(x_in: float, x_out: float, lift: float = 0.0) -> None:
        """画一页"""
        poly = QPolygonF([
            QPointF(x_in, top + spine - lift), QPointF(x_out, top - lift),
            QPointF(x_out, top - lift + ph), QPointF(x_in, top + spine + ph),
        ])
        painter.setPen(pen)
        painter.setBrush(pages)
        painter.drawPolygon(poly)
        if opened > 0.55:
            painter.setPen(line)
            for i in range(3):
                fy = (i + 1) / 4.0
                painter.drawLine(
                    QPointF(x_in + (x_out - x_in) * 0.16, top + spine - lift + (ph - spine) * fy + spine * 0.2),
                    QPointF(x_out - (x_out - x_in) * 0.12, top - lift + ph * fy),
                )

    page(0.0, -outer)
    page(0.0, outer)
    if stage != "open":
        turn = (math.sin(t * 0.7) + 1) * 0.5
        if turn > 0.6:  # sin 后段才掀页
            page(0.0, outer * (1 - (turn - 0.6) / 0.4 * 1.6), lift=bh * 0.05 * (turn - 0.6) / 0.4)
    painter.setPen(pen)
    painter.setBrush(palette.SKIN)
    hold = max(outer, bh * 0.05) * 0.86
    painter.drawEllipse(QPointF(-hold, top + spine + ph - bh * 0.01), bw * 0.07, bw * 0.07)
    painter.drawEllipse(QPointF(hold, top + spine + ph - bh * 0.01), bw * 0.07, bw * 0.07)

    if stage == "good":
        draw_spark(painter, QPointF(outer + bw * 0.12, top - bh * 0.16), bw, bh, p)


def draw_headphones(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画耳机 on 滑下戴上 vibe 随拍子动并飘音符"""
    p = stage_p
    slide = -(1.0 - ease_out(p)) * bh * 0.55 if stage == "on" else 0.0
    beat = math.sin(t * 6.2)
    cup_s = 1.0 + (0.10 * (beat * 0.5 + 0.5) if stage == "vibe" else 0.0)

    painter.save()
    painter.translate(0.0, slide)
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.024))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(-bw * 0.46, -bh * 0.64, bw * 0.92, bh * 0.72), 20 * 16, 140 * 16)

    for side in (-1, 1):
        cw, chh = bw * 0.17 * cup_s, bh * 0.34 * cup_s
        # 右耳罩缩放时往内补偏移
        cx = (-bw * 0.52 if side < 0 else bw * 0.35) + (bw * 0.17 - cw) * (0.0 if side < 0 else 1.0)
        cup = QRectF(cx, -chh * 0.5 + bh * 0.05, cw, chh)
        painter.setPen(pen)
        painter.setBrush(QColor(58, 62, 72))
        painter.drawRoundedRect(cup, bw * 0.05, bw * 0.05)
        if stage == "vibe":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(120, 220, 170))
            for i in range(3):
                h = chh * (0.25 + 0.30 * (math.sin(t * 7 + i * 1.7 + side) * 0.5 + 0.5))
                bx = cup.left() + cup.width() * (0.24 + 0.26 * i)
                painter.drawRoundedRect(QRectF(bx, cup.center().y() + chh * 0.30 - h, cup.width() * 0.13, h),
                                        bw * 0.01, bw * 0.01)
    painter.restore()

    if stage == "vibe":
        _draw_music_notes(painter, bw, bh, t)


def _draw_music_notes(painter: QPainter, bw: float, bh: float, t: float) -> None:
    """三枚音符交替往上飘"""
    for k in range(3):
        phase = (t * 0.45 + k / 3.0) % 1.0
        side = 1 if k % 2 == 0 else -1
        x = side * (bw * 0.5 + phase * bw * 0.30)
        y = bh * 0.05 - phase * bh * 1.05
        alpha = max(0, int(math.sin(phase * math.pi) * 220))
        col = QColor(palette.DREAM_COLORS[k % len(palette.DREAM_COLORS)])
        col.setAlpha(alpha)
        draw_note(painter, QPointF(x, y), bw, bh, col, double=(k % 2 == 0))


def draw_fishing(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画钓鱼 抛竿 等待 咬钩 收线 拉鱼"""
    p = stage_p
    _draw_fisher_hat(painter, bw, bh)


    water_y = bh * 0.42
    pool_cx = bw * 0.92
    float_x = bw * 0.84

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(120, 175, 225, 70))
    painter.drawRoundedRect(QRectF(pool_cx - bw * 0.34, water_y, bw * 0.68, bh * 0.13), bh * 0.04, bh * 0.04)


    if stage == "cast":
        rod_angle = -1.0 + 1.6 * ease_out(p)
    elif stage == "reel":
        rod_angle = 1.0 - 1.4 * ease_out(p)
    else:
        rod_angle = 0.6 + math.sin(t * 0.8) * 0.05
    rod_lo = QPointF(bw * 0.16, bh * 0.30)
    tip_dx = bw * 0.66 * math.cos(rod_angle * 1.1)
    tip_dy = -bh * 0.46 + bw * 0.30 * math.sin(rod_angle)
    rod_hi = QPointF(rod_lo.x() + tip_dx, tip_dy)


    bite_dip = 0.0
    fish = None  # None 没上钩 非 None 是鱼出水进度
    if stage in ("wait", "cast"):
        bob_y = water_y + bh * 0.02 + math.sin(t * 1.3) * bh * 0.02
    elif stage == "bite":
        bite_dip = ease_in(p) * bh * 0.12
        bob_y = water_y + bh * 0.02 + bite_dip
    elif stage == "reel":
        bob_y = water_y - ease_out(p) * bh * 0.25
    else:
        bob_y = water_y - bh * 0.2
        fish = ease_out(min(p / 0.6, 1.0))
    bob = QPointF(float_x, bob_y)

    if fish is None:
        ripple = QPen(QColor(150, 195, 235, 150))
        ripple.setWidthF(max(1.0, bw * 0.009))
        painter.setPen(ripple)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for r in (0.05, 0.09):
            painter.drawEllipse(QPointF(bob.x(), water_y + bh * 0.03), bw * r, bh * r * 0.45)

    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.022))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(rod_lo, rod_hi)
    line = QPen(QColor(120, 120, 128))
    line.setWidthF(max(1.0, bw * 0.008))
    painter.setPen(line)
    if fish is None:
        painter.drawLine(rod_hi, bob)
        painter.setPen(QPen(QColor(150, 40, 40), max(1.5, bw * 0.012)))
        painter.setBrush(QColor(232, 84, 84))
        painter.drawEllipse(bob, bw * 0.05, bw * 0.05)
    else:
        fy = water_y - fish * bh * 0.55
        fx = float_x + math.sin(t * 12) * bw * 0.03 * (1 - fish)
        painter.drawLine(rod_hi, QPointF(fx, fy))
        _draw_fish(painter, bw, bh, QPointF(fx, fy))

    painter.setPen(pen)
    painter.setBrush(palette.SKIN)
    painter.drawEllipse(rod_lo, bw * 0.08, bw * 0.08)


def _draw_fisher_hat(painter: QPainter, bw: float, bh: float) -> None:
    top = -bh * 0.5
    pen = QPen(QColor(70, 92, 70))
    pen.setWidthF(max(2.0, bw * 0.016))
    painter.setPen(pen)
    painter.setBrush(QColor(120, 150, 110))
    painter.drawEllipse(QRectF(-bw * 0.42, top + bh * 0.02, bw * 0.84, bh * 0.13))
    painter.setBrush(QColor(135, 165, 122))
    painter.drawRoundedRect(QRectF(-bw * 0.26, top - bh * 0.24, bw * 0.52, bh * 0.30), bh * 0.1, bh * 0.1)
    painter.setBrush(QColor(95, 120, 88))
    painter.drawRect(QRectF(-bw * 0.26, top - bh * 0.02, bw * 0.52, bh * 0.05))


def _draw_fish(painter: QPainter, bw: float, bh: float, at: QPointF) -> None:
    painter.save()
    painter.translate(at.x(), at.y())
    painter.rotate(-25)
    painter.setPen(QPen(QColor(180, 90, 30), max(1.5, bw * 0.012)))
    painter.setBrush(QColor(240, 140, 60))
    painter.drawEllipse(QRectF(-bw * 0.11, -bh * 0.06, bw * 0.22, bh * 0.12))
    painter.drawPolygon(QPolygonF([
        QPointF(-bw * 0.10, 0.0), QPointF(-bw * 0.20, -bh * 0.06), QPointF(-bw * 0.20, bh * 0.06),
    ]))
    painter.setBrush(palette.INK)
    painter.drawEllipse(QPointF(bw * 0.06, -bh * 0.01), bw * 0.015, bw * 0.015)
    painter.restore()


def draw_gaming(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画打游戏 屏上球来回弹 tense 微抖 win 闪绿放烟花"""
    p = stage_p
    if stage == "tense":
        dx, dy, spd = math.sin(t * 9) * bw * 0.015, -bh * 0.05, 7.5
    elif stage == "win":
        dx, dy, spd = 0.0, -bh * 0.22, 0.0
    else:
        dx, dy, spd = math.sin(t * 16) * bw * 0.012, math.sin(t * 13) * bh * 0.008, 3.6
    painter.save()
    painter.translate(dx, dy)
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.02))
    painter.setPen(pen)


    painter.setBrush(QColor(72, 76, 86))
    body = QRectF(-bw * 0.30, bh * 0.18, bw * 0.60, bh * 0.40)
    painter.drawRoundedRect(body, bh * 0.07, bh * 0.07)

    screen = QRectF(-bw * 0.22, bh * 0.22, bw * 0.44, bh * 0.19)
    won = stage == "win"
    flash = won and (math.sin(t * 18) > 0)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(150, 240, 170) if flash else QColor(28, 40, 34))
    painter.drawRoundedRect(screen, bh * 0.02, bh * 0.02)
    if won:
        draw_spark(painter, QPointF(0.0, screen.center().y()), bw, bh, p)
    else:
        net = QPen(QColor(90, 110, 100))
        net.setWidthF(max(1.0, bw * 0.006))
        net.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(net)
        painter.drawLine(QPointF(0.0, screen.top() + bh * 0.02), QPointF(0.0, screen.bottom() - bh * 0.02))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(150, 240, 170))
        bx = math.sin(t * spd) * screen.width() * 0.40
        by = screen.center().y() + math.sin(t * spd * 1.7) * screen.height() * 0.32
        painter.drawEllipse(QPointF(bx, by), bw * 0.018, bw * 0.018)


    painter.setBrush(QColor(232, 96, 96))
    painter.drawEllipse(QPointF(bw * 0.15, bh * 0.495), bw * 0.026, bw * 0.026)
    painter.setBrush(QColor(120, 200, 140))
    painter.drawEllipse(QPointF(bw * 0.205, bh * 0.495), bw * 0.026, bw * 0.026)
    painter.setBrush(QColor(206, 208, 214))
    painter.drawRect(QRectF(-bw * 0.215, bh * 0.485, bw * 0.085, bh * 0.024))
    painter.drawRect(QRectF(-bw * 0.184, bh * 0.457, bw * 0.024, bh * 0.080))
    painter.restore()


def draw_telescope(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画望远镜和星空 aim 抬向天空 wow 划流星"""
    p = stage_p
    if stage == "aim":
        angle = -32 + (1 - ease_out(p)) * 40
    elif stage == "wow":
        angle = -32 + math.sin(t * 9) * 3
    else:
        angle = -32 + math.sin(t * 0.4) * 10


    sky = ((bw * 0.45, -bh * 0.95), (bw * 0.78, -bh * 0.70), (bw * 0.30, -bh * 0.62),
           (bw * 0.95, -bh * 1.02), (bw * 0.62, -bh * 1.10), (bw * 0.20, -bh * 0.92))
    painter.setPen(Qt.PenStyle.NoPen)
    for i, (sx, sy) in enumerate(sky):
        tw = math.sin(t * (1.6 + i * 0.4) + i) * 0.5 + 0.5
        r = bh * (0.022 + 0.030 * tw)
        col = QColor(255, 244, 200)
        col.setAlpha(int(120 + 135 * tw))
        painter.setBrush(col)
        painter.drawEllipse(QPointF(sx, sy), r, r)
    if stage == "wow":
        _draw_shooting_star(painter, bw, bh, p)

    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.022))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.save()
    painter.translate(bw * 0.16, -bh * 0.02)
    painter.rotate(angle)
    painter.setBrush(QColor(72, 76, 86))
    painter.drawRoundedRect(QRectF(0.0, -bh * 0.06, bw * 0.5, bh * 0.12), bh * 0.04, bh * 0.04)
    painter.setBrush(QColor(150, 190, 235))
    painter.drawEllipse(QRectF(bw * 0.44, -bh * 0.075, bw * 0.06, bh * 0.15))
    painter.restore()
    painter.setBrush(palette.SKIN)
    painter.drawEllipse(QPointF(bw * 0.15, 0.0), bw * 0.07, bw * 0.07)


def _draw_shooting_star(painter: QPainter, bw: float, bh: float, p: float) -> None:
    t = min(p / 0.7, 1.0)
    hx = -bw * 0.05 + t * bw * 1.05
    hy = -bh * 1.20 + t * bh * 0.55
    tail = QPointF(hx - bw * 0.28, hy - bh * 0.15)
    fade = int(255 * math.sin(t * math.pi))
    grad = QPen(QColor(255, 255, 255, max(0, fade)))
    grad.setWidthF(max(1.2, bw * 0.012))
    grad.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(grad)
    painter.drawLine(tail, QPointF(hx, hy))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 250, 220, max(0, fade)))
    painter.drawEllipse(QPointF(hx, hy), bw * 0.022, bw * 0.022)


def draw_sherlock(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """画侦探 猎鹿帽 爪印 放大镜"""
    p = stage_p
    hat, hat_dark = QColor(126, 99, 64), QColor(72, 54, 32)
    top = -bh * 0.5
    pen = QPen(hat_dark)
    pen.setWidthF(max(2.0, bw * 0.016))
    painter.setPen(pen)
    painter.setBrush(hat)
    painter.drawEllipse(QPointF(-bw * 0.3, top + bh * 0.04), bw * 0.11, bh * 0.13)
    painter.drawEllipse(QPointF(bw * 0.3, top + bh * 0.04), bw * 0.11, bh * 0.13)
    painter.drawEllipse(QRectF(-bw * 0.42, top + bh * 0.02, bw * 0.84, bh * 0.14))
    painter.drawRoundedRect(
        QRectF(-bw * 0.32, top - bh * 0.34, bw * 0.64, bh * 0.46), bh * 0.22, bh * 0.22
    )
    painter.setBrush(hat_dark)
    painter.drawEllipse(QPointF(0.0, top - bh * 0.34), bw * 0.03, bw * 0.03)


    prints = ((bw * 0.16, bh * 0.46, -1), (bw * 0.30, bh * 0.52, 1),
              (bw * 0.45, bh * 0.45, -1), (bw * 0.59, bh * 0.51, 1))
    for fx, fy, side in prints:
        _draw_pawprint(painter, QPointF(fx, fy), bw, bh, side)


    if stage == "closer":
        mx = bw * 0.45 + bw * 0.04 * math.sin(t * 1.2)
        my = bh * 0.40
        r = bh * (0.17 + 0.06 * ease_out(p))
    elif stage == "aha":
        mx = bw * 0.50
        my = bh * 0.40 - ease_out(p) * bh * 0.34
        r = bh * 0.17
    else:
        mx = bw * (0.38 + 0.20 * math.sin(t * 1.6))
        my = bh * 0.48 + math.sin(t * 2.3) * bh * 0.03
        r = bh * 0.17
    handle = QPen(QColor(74, 50, 28))
    handle.setWidthF(bw * 0.055)
    handle.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(handle)
    painter.drawLine(QPointF(mx + r * 0.75, my + r * 0.75), QPointF(mx + r * 1.7, my + r * 1.7))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(180, 215, 255, 90))
    painter.drawEllipse(QPointF(mx, my), r, r)
    if stage in ("scan", "closer"):
        painter.save()
        clip = QPainterPath()
        clip.addEllipse(QPointF(mx, my), r, r)
        painter.setClipPath(clip)  # 裁到镜片圆内
        _draw_pawprint(painter, QPointF(mx, my + r * 0.1), bw, bh, -1, scale=2.1)
        painter.restore()
    ring = QPen(QColor(60, 60, 70))
    ring.setWidthF(bw * 0.035)
    painter.setPen(ring)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(mx, my), r, r)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 150))
    painter.drawEllipse(QPointF(mx - r * 0.35, my - r * 0.35), r * 0.16, r * 0.16)

    _draw_moustache(painter, bw, bh)


def _draw_pawprint(painter: QPainter, at: QPointF, bw: float, bh: float, side: int, scale: float = 1.0) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(110, 96, 84, 150 if scale > 1.5 else 90))
    pad = bw * 0.03 * scale
    painter.drawEllipse(at, pad, pad * 1.15)
    for tx, ty in ((-0.9, -1.1), (0.0, -1.45), (0.9, -1.1)):
        painter.drawEllipse(QPointF(at.x() + tx * pad, at.y() + ty * pad), pad * 0.42, pad * 0.5)


def _draw_moustache(painter: QPainter, bw: float, bh: float) -> None:
    cy = bh * 0.3
    w = bw * 0.22
    pen = QPen(palette.INK)
    pen.setWidthF(bh * 0.08)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(-w, cy - bh * 0.05)
    path.quadTo(-w * 0.5, cy + bh * 0.04, 0.0, cy - bh * 0.01)
    path.quadTo(w * 0.5, cy + bh * 0.04, w, cy - bh * 0.05)
    painter.drawPath(path)


def draw_pointer(painter: QPainter, bw: float, bh: float, t: float) -> None:
    tip_bob = math.sin(t * 2.0) * bh * 0.04
    x0, y0 = -bw * 0.3, bh * 0.48
    x1, y1 = -bw * 0.72, -bh * 0.4 + tip_bob
    pen = QPen(QColor(150, 110, 70))
    pen.setWidthF(bw * 0.028)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(70, 50, 32))
    painter.drawEllipse(QPointF(x1, y1), bw * 0.03, bw * 0.03)
