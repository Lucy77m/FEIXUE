# author: bdth
# email: 2074055628@qq.com
# 桌宠道具服装的矢量绘制 咖啡 书 耳机 钓鱼 望远镜等装扮画法

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet import palette
from desktop_pet.pet.behaviors.easing import ease_in, ease_out


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


def draw_bubbles(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹泡泡 蘸->吹->看着飘->啵地破"""
    wand = QPointF(bw * 0.30, bh * 0.08)
    # 嘴边的小吹圈(蘸了泡泡水的环)
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
        if i == popped and age > 0.4:  # 啵——小爆裂
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
    """攥着气球 抓->晃->拽->飘"""
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


def draw_icecream(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举个甜筒 舔->融化滴"""
    cx = bw * 0.30
    cone_top = bh * 0.06
    cw = bw * 0.15
    painter.setPen(QPen(QColor(190, 140, 80), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 175, 110))
    painter.drawPolygon(QPolygonF([QPointF(cx - cw, cone_top), QPointF(cx + cw, cone_top),
                                   QPointF(cx, cone_top + bh * 0.36)]))
    painter.setPen(QPen(QColor(180, 130, 75, 160), max(0.8, bw * 0.005)))
    for k in (-1, 0, 1):
        painter.drawLine(QPointF(cx + k * cw * 0.5, cone_top), QPointF(cx + k * cw * 0.18, cone_top + bh * 0.32))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(245, 200, 215))
    painter.drawEllipse(QPointF(cx, cone_top - bh * 0.01), cw * 1.05, bh * 0.16)
    painter.setBrush(QColor(250, 236, 205))
    painter.drawEllipse(QPointF(cx, cone_top - bh * 0.15), cw * 0.82, bh * 0.13)
    painter.setBrush(QColor(232, 96, 112))  # 樱桃
    painter.drawEllipse(QPointF(cx, cone_top - bh * 0.26), cw * 0.18, cw * 0.18)
    if stage == "melt":
        d = ease_out(stage_p)
        painter.setBrush(QColor(245, 200, 215, 220))
        painter.drawEllipse(QPointF(cx + cw * 0.7, cone_top + bh * 0.05 + d * bh * 0.10),
                            bw * 0.02, bh * 0.04 + d * bh * 0.05)


def draw_paperplane(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """折->掷->弧线滑翔的小纸飞机"""
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
    """放风筝 跑->放线->高飞"""
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


def draw_camera(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举相机拍照 取景->咔嚓闪光"""
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


def draw_bubbletea(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """奶茶 举杯->吸珍珠"""
    cx = bw * 0.30
    top, bot = -bh * 0.08, bh * 0.30
    wt, wbo = bw * 0.13, bw * 0.10
    painter.setPen(QPen(QColor(180, 150, 140), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(228, 205, 180, 238))
    painter.drawPolygon(QPolygonF([QPointF(cx - wt, top), QPointF(cx + wt, top),
                                   QPointF(cx + wbo, bot), QPointF(cx - wbo, bot)]))
    painter.setBrush(QColor(210, 225, 235, 235))
    painter.drawRoundedRect(QRectF(cx - wt - bw * 0.012, top - bh * 0.045, (wt + bw * 0.012) * 2, bh * 0.05), 2, 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(74, 56, 50))
    for dx, dy in ((-0.05, 0.0), (0.03, 0.01), (-0.01, 0.045), (0.055, 0.04), (-0.06, 0.05), (0.005, 0.075)):
        painter.drawEllipse(QPointF(cx + dx * bw, bot - bh * 0.05 + dy * bh), bw * 0.023, bw * 0.023)
    painter.setPen(QPen(QColor(225, 110, 120), max(1.4, bw * 0.014)))
    painter.drawLine(QPointF(cx + bw * 0.04, top - bh * 0.18), QPointF(cx - bw * 0.02, bot - bh * 0.05))


def draw_tanghulu(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """糖葫芦 举串->一颗颗咬"""
    base = QPointF(bw * 0.16, bh * 0.30)
    tip = QPointF(bw * 0.44, -bh * 0.34)
    painter.setPen(QPen(QColor(196, 174, 142), max(1.2, bw * 0.01)))
    painter.drawLine(base, tip)
    n = 5
    eaten = int(stage_p * n) if stage == "bite" else 0
    for i in range(eaten, n):
        f = i / (n - 1)
        c = QPointF(base.x() + (tip.x() - base.x()) * f, base.y() + (tip.y() - base.y()) * f)
        painter.setPen(QPen(QColor(150, 40, 40), max(0.8, bw * 0.005)))
        painter.setBrush(QColor(214, 50, 52))
        painter.drawEllipse(c, bw * 0.062, bw * 0.062)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 205, 195, 160))
        painter.drawEllipse(QPointF(c.x() - bw * 0.02, c.y() - bw * 0.02), bw * 0.02, bw * 0.02)


def draw_dandelion(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹蒲公英 举着->吹散->看种子飘"""
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


def draw_guitar(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """抱吉他 调弦->扫弦(带音符)"""
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


def draw_watermelon(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举西瓜片 一口口啃(红瓤往尖端缩)"""
    cx = bw * 0.30
    apex = QPointF(cx - bw * 0.02, bh * 0.30)      # 拿在手里的尖角(朝下)
    L = QPointF(cx - bw * 0.18, -bh * 0.10)
    R = QPointF(cx + bw * 0.16, -bh * 0.06)
    painter.setPen(QPen(QColor(60, 130, 70), max(1.1, bw * 0.009)))
    painter.setBrush(QColor(96, 174, 100))         # 绿皮
    painter.drawPolygon(QPolygonF([apex, L, R]))
    painter.setPen(QPen(QColor(225, 240, 220), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(243, 250, 240))        # 白边
    painter.drawPolygon(QPolygonF([apex,
                                   QPointF(L.x() + (apex.x() - L.x()) * 0.14, L.y() + (apex.y() - L.y()) * 0.14),
                                   QPointF(R.x() + (apex.x() - R.x()) * 0.14, R.y() + (apex.y() - R.y()) * 0.14)]))
    eaten = ease_out(stage_p) * 0.62 if stage == "bite" else 0.0
    mL = QPointF(L.x() + (apex.x() - L.x()) * (0.22 + eaten), L.y() + (apex.y() - L.y()) * (0.22 + eaten))
    mR = QPointF(R.x() + (apex.x() - R.x()) * (0.22 + eaten), R.y() + (apex.y() - R.y()) * (0.22 + eaten))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(233, 88, 96))          # 红瓤
    painter.drawPolygon(QPolygonF([apex, mL, mR]))
    painter.setBrush(QColor(58, 44, 40))           # 籽
    for fx, fy in ((0.34, 0.34), (0.55, 0.40), (0.40, 0.58)):
        sx = apex.x() + (((mL.x() + mR.x()) / 2) - apex.x()) * fy
        sy = apex.y() + ((((L.y() + R.y()) / 2)) - apex.y()) * fy
        painter.drawEllipse(QPointF(sx + (fx - 0.45) * bw * 0.18, sy), bw * 0.011, bw * 0.017)


def draw_fireworks(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """放烟花 升空->炸开"""
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


def draw_yoyo(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """玩悠悠球 抛->空转->收"""
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


def draw_watering(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """浇花 举喷壶->浇水->嫩芽冒头"""
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


def draw_lollipop(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """棒棒糖 举着->舔(转圈纹)"""
    head = QPointF(bw * 0.30, -bh * 0.06)
    painter.setPen(QPen(QColor(230, 225, 220), max(1.4, bw * 0.012)))
    painter.drawLine(head, QPointF(head.x() - bw * 0.04, bh * 0.28))
    r = bw * 0.13
    painter.setPen(QPen(QColor(210, 90, 110), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(244, 150, 170))
    painter.drawEllipse(head, r, r)
    painter.save()
    painter.translate(head)
    painter.rotate((t * 60) % 360 if stage == "lick" else 20)
    pen = QPen(QColor(232, 110, 130), max(1.2, bw * 0.012))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(0, 0))
    for a in range(1, 70):
        rr = r * 0.92 * a / 70.0
        ang = a * 0.5
        path.lineTo(QPointF(math.cos(ang) * rr, math.sin(ang) * rr))
    painter.drawPath(path)
    painter.restore()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 140))
    painter.drawEllipse(QPointF(head.x() - r * 0.35, head.y() - r * 0.35), r * 0.22, r * 0.22)


def draw_popcorn(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """爆米花 捧桶->抛着吃"""
    cx = bw * 0.30
    painter.setPen(QPen(QColor(190, 70, 80), max(1.0, bw * 0.008)))
    for k in range(5):
        painter.setBrush(QColor(232, 96, 102) if k % 2 == 0 else QColor(248, 246, 240))
        x = cx - bw * 0.12 + k * bw * 0.048
        painter.drawPolygon(QPolygonF([QPointF(x, bh * 0.06), QPointF(x + bw * 0.048, bh * 0.06),
                                       QPointF(x + bw * 0.038, bh * 0.30), QPointF(x + bw * 0.01, bh * 0.30)]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(250, 232, 170))
    for dx, dy in ((-0.08, -0.02), (-0.02, -0.05), (0.04, -0.03), (0.09, -0.01), (0.0, 0.0), (0.06, 0.02)):
        painter.drawEllipse(QPointF(cx + dx * bw, bh * 0.02 + dy * bh), bw * 0.03, bw * 0.028)
    if stage == "toss":
        ph = (t * 1.4) % 1.0
        fy = bh * 0.02 - bh * 0.30 * math.sin(ph * math.pi)
        painter.setBrush(QColor(250, 232, 170))
        painter.drawEllipse(QPointF(cx + bw * 0.02, fy), bw * 0.03, bw * 0.028)


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


def draw_donut(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """甜甜圈 举着啃 中间是真空心(环形路径 不用背景色挖洞)"""
    cx, cy = bw * 0.30, bh * 0.02
    if stage == "munch":
        cy += math.sin(t * 5) * bh * 0.02
    R, ri = bw * 0.15, bw * 0.056
    dough = QPainterPath()
    dough.setFillRule(Qt.FillRule.OddEvenFill)
    dough.addEllipse(QPointF(cx, cy), R, R)
    dough.addEllipse(QPointF(cx, cy), ri, ri)
    painter.setPen(QPen(QColor(190, 140, 90), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 170, 110))
    painter.drawPath(dough)
    frost = QPainterPath()
    frost.setFillRule(Qt.FillRule.OddEvenFill)
    frost.addEllipse(QPointF(cx, cy - bh * 0.004), R * 0.96, R * 0.92)
    frost.addEllipse(QPointF(cx, cy), ri * 1.2, ri * 1.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(236, 130, 160))
    painter.drawPath(frost)
    for i, c in enumerate((QColor(120, 180, 230), QColor(245, 205, 110), QColor(140, 200, 150),
                           QColor(255, 255, 255), QColor(232, 110, 130))):
        ang = i * 1.3 + 0.5
        sx, sy = cx + math.cos(ang) * R * 0.66, cy + math.sin(ang) * R * 0.66
        painter.setPen(QPen(c, max(1.4, bw * 0.012)))
        painter.drawLine(QPointF(sx - bw * 0.018, sy - bw * 0.01), QPointF(sx + bw * 0.018, sy + bw * 0.01))


def draw_soda(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """汽水 举杯 吸管喝 气泡往上冒"""
    cx = bw * 0.30
    top, bot = -bh * 0.14, bh * 0.30
    wt = bw * 0.11
    painter.setPen(QPen(QColor(150, 180, 200, 210), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(150, 205, 225, 150))
    painter.drawPolygon(QPolygonF([QPointF(cx - wt, top), QPointF(cx + wt, top),
                                   QPointF(cx + wt * 0.78, bot), QPointF(cx - wt * 0.78, bot)]))
    painter.setBrush(QColor(220, 240, 250, 175))
    painter.drawRect(QRectF(cx - wt * 0.2, top + bh * 0.04, wt * 0.5, wt * 0.5))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 175))
    for k in range(5):
        ph = (t * 0.9 + k * 0.27) % 1.0
        painter.drawEllipse(QPointF(cx - wt * 0.4 + k * wt * 0.2, bot - ph * (bot - top) * 0.8),
                            bw * 0.012, bw * 0.012)
    painter.setPen(QPen(QColor(232, 110, 120), max(1.4, bw * 0.014)))
    painter.drawLine(QPointF(cx + wt * 0.3, top - bh * 0.16), QPointF(cx - wt * 0.1, bot - bh * 0.04))


def draw_corn(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """啃玉米 一排排啃掉"""
    painter.save()
    painter.translate(bw * 0.30, bh * 0.04)
    painter.rotate(-25)
    cw, ch = bw * 0.10, bh * 0.26
    painter.setPen(QPen(QColor(90, 150, 80), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(132, 190, 112))
    painter.drawPolygon(QPolygonF([QPointF(0, ch), QPointF(-cw * 1.2, ch + ch * 0.5), QPointF(cw * 0.2, ch + ch * 0.2)]))
    painter.drawPolygon(QPolygonF([QPointF(0, ch), QPointF(cw * 1.2, ch + ch * 0.5), QPointF(-cw * 0.2, ch + ch * 0.2)]))
    painter.setPen(QPen(QColor(220, 180, 70), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(248, 216, 96))
    painter.drawRoundedRect(QRectF(-cw, -ch, cw * 2, ch * 2), cw * 0.7, cw * 0.7)
    eaten = int(stage_p * 4) if stage == "bite" else 0
    painter.setPen(QPen(QColor(214, 170, 60), max(0.7, bw * 0.004)))
    painter.setBrush(QColor(252, 226, 120))
    for ry in range(eaten, 7):
        for rx in range(3):
            painter.drawEllipse(QPointF(-cw * 0.55 + rx * cw * 0.55, -ch * 0.85 + ry * ch * 0.26), cw * 0.22, ch * 0.10)
    painter.restore()


def draw_sushi(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吃寿司 筷子夹起一贯"""
    cx, cy = bw * 0.30, bh * 0.06
    if stage == "eat":
        cy -= bh * 0.12 * stage_p
    painter.setPen(QPen(QColor(200, 195, 185), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(250, 248, 242))
    painter.drawRoundedRect(QRectF(cx - bw * 0.13, cy, bw * 0.26, bh * 0.12), bw * 0.03, bw * 0.03)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(248, 150, 110))
    painter.drawRoundedRect(QRectF(cx - bw * 0.14, cy - bh * 0.05, bw * 0.28, bh * 0.08), bw * 0.03, bw * 0.03)
    painter.setPen(QPen(QColor(255, 215, 190, 190), max(0.8, bw * 0.005)))
    for k in range(2):
        painter.drawLine(QPointF(cx - bw * 0.1, cy - bh * 0.035 + k * bh * 0.02),
                         QPointF(cx + bw * 0.1, cy - bh * 0.04 + k * bh * 0.02))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(58, 66, 58))
    painter.drawRect(QRectF(cx - bw * 0.03, cy - bh * 0.05, bw * 0.06, bh * 0.17))
    painter.setPen(QPen(QColor(180, 130, 90), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(cx - bw * 0.18, cy - bh * 0.20), QPointF(cx - bw * 0.02, cy + bh * 0.02))
    painter.drawLine(QPointF(cx - bw * 0.12, cy - bh * 0.22), QPointF(cx + bw * 0.02, cy + bh * 0.02))


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


# 装扮注册表 worn 穿身上 ambient 撒周围 二者互斥
COSTUME_LAYERS = {
    "sherlock": (draw_sherlock, None),
    "coffee": (draw_coffee, None),
    "book": (draw_book, None),
    "headphones": (draw_headphones, None),
    "fishing": (draw_fishing, None),
    "gaming": (draw_gaming, None),
    "telescope": (draw_telescope, None),
    "party": (None, draw_confetti),
    "raincloud": (None, draw_raincloud),
    "sweat": (None, draw_sweat),
    "void": (None, draw_void),
    "clone": (None, draw_clone),
    "meteor": (None, draw_meteor),
    "sprout": (None, draw_sprout),
    "yarn": (None, draw_yarn),
    "bubbles": (None, draw_bubbles),
    "balloon": (None, draw_balloon),
    "icecream": (None, draw_icecream),
    "paperplane": (None, draw_paperplane),
    "kite": (None, draw_kite),
    "camera": (draw_camera, None),
    "bubbletea": (None, draw_bubbletea),
    "tanghulu": (None, draw_tanghulu),
    "dandelion": (None, draw_dandelion),
    "guitar": (draw_guitar, None),
    "watermelon": (draw_watermelon, None),
    "fireworks": (None, draw_fireworks),
    "yoyo": (None, draw_yoyo),
    "painting": (None, draw_painting),
    "watering": (None, draw_watering),
    "blocks": (None, draw_blocks),
    "lollipop": (None, draw_lollipop),
    "popcorn": (None, draw_popcorn),
    "pinwheel": (None, draw_pinwheel),
    "donut": (None, draw_donut),
    "soda": (None, draw_soda),
    "corn": (draw_corn, None),
    "sushi": (None, draw_sushi),
    "rubik": (None, draw_rubik),
    "magic": (None, draw_magic),
    "knitting": (None, draw_knitting),
}
COSTUMES = frozenset(COSTUME_LAYERS)
WORN_COSTUMES = frozenset(name for name, (worn, _ambient) in COSTUME_LAYERS.items() if worn)
