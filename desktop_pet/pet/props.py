# author: bdth
# email: 2074055628@qq.com
# 桌宠道具/服装的矢量绘制：咖啡、书、耳机、钓鱼、望远镜等各装扮的 QPainter 画法

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet import palette
from desktop_pet.pet.behaviors.easing import ease_in, ease_out


def draw_note(painter: QPainter, at: QPointF, bw: float, bh: float, col: QColor, double: bool) -> None:
    """画一个音符：单符带符尾，double 时再接一个并用横梁连成八分音符。"""
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
    """四角闪光：尺寸跟 p 走 sin 半周，先涨后缩。复用于「看书有所得/赢了」的高光。"""
    s = (math.sin(p * math.pi)) * bh * 0.16
    if s <= 0.5:  # 太小就别画了——单像素闪光反而像噪点
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
    """咖啡：pour 阶段水壶往杯里倒、液面随 p 涨；sip/lift 杯子端起来喝，液面保持满。"""
    p = stage_p
    pen = QPen(palette.OUTLINE)
    pen.setWidthF(max(2.0, bw * 0.02))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    cw, ch = bw * 0.34, bh * 0.32


    if stage == "sip":
        sip_lift = (math.sin(p * math.pi * 3) * 0.5 + 0.5)  # 抿三口——sin 跑三个半周
        mug_y = bh * 0.30 - sip_lift * bh * 0.20
        fill = 0.85
    elif stage == "lift":
        mug_y = bh * 0.30 - ease_out(p) * bh * 0.06
        fill = 0.85
    else:  # pour：液面从 0.15 灌到 0.85
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
    """倒水的壶：前 25% 滑入并倾斜，中段悬停出水流，后 20% 滑出画面。"""
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

    if 0.2 < p < 0.85:  # 只有壶稳住、还没开始撤的这段才挂水流，否则水线会甩在半空
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
    """翻书：open 阶段从合到摊（opened 0→1 驱动书脊/外缘张开），其余阶段随时间偶尔翻页。"""
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
        """画一页：x_in 贴书脊、x_out 是外缘；lift 是翻页时这页被掀起的高度。"""
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
        if turn > 0.6:  # 只在 sin 后段才掀一页，省得一直翻——大半时间书是静的
            page(0.0, outer * (1 - (turn - 0.6) / 0.4 * 1.6), lift=bh * 0.05 * (turn - 0.6) / 0.4)
    painter.setPen(pen)
    painter.setBrush(palette.SKIN)
    hold = max(outer, bh * 0.05) * 0.86
    painter.drawEllipse(QPointF(-hold, top + spine + ph - bh * 0.01), bw * 0.07, bw * 0.07)
    painter.drawEllipse(QPointF(hold, top + spine + ph - bh * 0.01), bw * 0.07, bw * 0.07)

    if stage == "good":
        draw_spark(painter, QPointF(outer + bw * 0.12, top - bh * 0.16), bw, bh, p)


def draw_headphones(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """耳机：on 阶段从头顶滑下戴上；vibe 阶段耳罩随拍子缩放、亮起频谱条并飘音符。"""
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
        # 右耳罩缩放时往内补偏移，让两侧外缘钉死不动——不然 vibe 一抖整个耳机就变宽
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
    """三枚音符左右交替往上飘，phase 走 sin 控透明度——飘到顶自然淡出。"""
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
    """钓鱼：抛竿→等待浮漂晃→咬钩下沉→收线→拉出鱼。fish 不为 None 表示已上钩、改画鱼。"""
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
    fish = None  # None=浮漂还在水里；非 None=鱼出水的进度(0→1)，下面据此切两套画法
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
    """打游戏：掌机屏上一颗球来回弹(spd 控速)；tense 时机身微抖，win 时屏幕闪绿放烟花。"""
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
    """望远镜：满天闪烁星点 + 镜身。aim 抬向天空，wow 时手抖兴奋并划过一颗流星。"""
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
    """侦探：猎鹿帽 + 地上一串猫爪印 + 放大镜。closer 凑近放大、aha 举起恍然，镜里裁出放大的爪印。"""
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
        painter.setClipPath(clip)  # 裁到镜片圆内，放大的爪印才不会溢出镜框
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
    """五角星轮廓，从正上方那个尖起。内半径 0.42r——再小尖太瘦、再大就钝得不像星。"""
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(QPointF(cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    return QPolygonF(pts)


def draw_void(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """虚空一跃：身体旁裂开的靛紫漩涡，张开→脉动→闭合。"""
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
    """半透明分身：照本体的圆角方块轮廓 + 两眼，alpha 控整体淡入淡出。给 clone 用。"""
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
    """影分身：本体旁分裂出半透明分身，镜像舞、换位、再合体。"""
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
    """接流星：一颗星从左上坠下，被接住后捧在身前发光，再放飞。"""
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
    """种花：挖坑播种浇水→等待→破土→绽放。慢而治愈。"""
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


# 装扮注册表：每项 = (worn 画法, ambient 画法)。worn 是「穿在身上」的(画在身体那层)，
# ambient 是「环境氛围」的(撒在身体周围，如彩纸/雨云/虚空)，二者互斥——一个槽只填一个。
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
}
COSTUMES = frozenset(COSTUME_LAYERS)
WORN_COSTUMES = frozenset(name for name, (worn, _ambient) in COSTUME_LAYERS.items() if worn)
