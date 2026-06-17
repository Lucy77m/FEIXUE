# author: bdth
# email: 2074055628@qq.com
# 吃的喝的一挂 冰淇淋 奶茶 寿司 烤红薯什么的

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from desktop_pet.pet.behaviors.easing import ease_out


def draw_icecream(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举个甜筒 一口一口往下啃 最后一点在化"""
    cx = bw * 0.30
    cone_top = bh * 0.06
    cw = bw * 0.15
    # 甜筒始终在
    painter.setPen(QPen(QColor(190, 140, 80), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 175, 110))
    painter.drawPolygon(QPolygonF([QPointF(cx - cw, cone_top), QPointF(cx + cw, cone_top),
                                   QPointF(cx, cone_top + bh * 0.36)]))
    painter.setPen(QPen(QColor(180, 130, 75, 160), max(0.8, bw * 0.005)))
    for k in (-1, 0, 1):
        painter.drawLine(QPointF(cx + k * cw * 0.5, cone_top), QPointF(cx + k * cw * 0.18, cone_top + bh * 0.32))

    # 吃到哪了 hold 没动 bite 一口一口往下啃 melt 剩甜筒口一点在化
    if stage == "bite":
        eaten = stage_p
    elif stage == "melt":
        eaten = 1.0
    else:
        eaten = 0.0
    n = 5
    bites = min(n, int(eaten * n + 1e-6))  # 离散一口口 不是平滑缩
    food_top = cone_top - bh * 0.26 - cw * 0.18  # 樱桃顶上一点
    bite_y = food_top + (cone_top - food_top) * (bites / n)  # 啃线一格格下移到甜筒口

    if bites < n:
        # 啃线以下才画 上面被吃掉了
        painter.save()
        painter.setClipRect(QRectF(cx - cw * 1.4, bite_y, cw * 2.8, bh))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(245, 200, 215))  # 粉球
        painter.drawEllipse(QPointF(cx, cone_top - bh * 0.01), cw * 1.05, bh * 0.16)
        painter.setBrush(QColor(250, 236, 205))  # 奶油球
        painter.drawEllipse(QPointF(cx, cone_top - bh * 0.15), cw * 0.82, bh * 0.13)
        painter.setBrush(QColor(232, 96, 112))  # 樱桃
        painter.drawEllipse(QPointF(cx, cone_top - bh * 0.26), cw * 0.18, cw * 0.18)
        painter.restore()
        if bites > 0:
            # 啃线上一排小扇贝 露出被咬的断面
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 228, 238))
            scn = 4
            sw = cw * 1.8 / scn
            for i in range(scn):
                painter.drawEllipse(QPointF(cx - cw * 0.9 + sw * (i + 0.5), bite_y), sw * 0.55, bh * 0.024)

    if stage == "melt":
        # 甜筒口残留的一点在化 往下滴
        d = ease_out(stage_p)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(245, 200, 215, 230))
        painter.drawEllipse(QPointF(cx, cone_top - bh * 0.02), cw * 0.5 * (1 - d * 0.5), bh * 0.04)
        painter.setBrush(QColor(245, 200, 215, 200))
        painter.drawEllipse(QPointF(cx + cw * 0.55, cone_top + d * bh * 0.08),
                            bw * 0.018, bh * 0.03 + d * bh * 0.05)


def draw_bubbletea(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """奶茶 举杯吸珍珠"""
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
    """糖葫芦 举串一颗颗咬"""
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


def draw_watermelon(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """举西瓜片 一口口啃 红瓤往尖端缩"""
    cx = bw * 0.30
    apex = QPointF(cx - bw * 0.02, bh * 0.30)      # 拿在手里朝下的尖角
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


def draw_lollipop(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """棒棒糖 举着舔 转圈纹"""
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
    """爆米花 捧桶抛着吃"""
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


def draw_donut(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """甜甜圈 举着啃 中间是真空心 环形路径不用背景色挖洞"""
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


def draw_popsicle(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吃冰棍 一口口咬"""
    cx = bw * 0.30
    top, bot = -bh * 0.12, bh * 0.16
    eaten = ease_out(stage_p) * (bot - top) * 0.7 if stage == "bite" else 0.0
    painter.setPen(QPen(QColor(200, 170, 130), max(1.4, bw * 0.012)))
    painter.drawLine(QPointF(cx, bot), QPointF(cx, bh * 0.32))
    painter.setPen(QPen(QColor(120, 170, 210), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(152, 206, 236))
    painter.drawRoundedRect(QRectF(cx - bw * 0.09, top + eaten, bw * 0.18, (bot - top) - eaten), bw * 0.04, bw * 0.04)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 120))
    if (bot - top) - eaten > bh * 0.04:
        painter.drawRoundedRect(QRectF(cx - bw * 0.06, top + eaten + bh * 0.02, bw * 0.028, ((bot - top) - eaten) * 0.5),
                                bw * 0.01, bw * 0.01)


def draw_cottoncandy(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """棉花糖 纸筒上一大坨粉云"""
    cx = bw * 0.30
    painter.setPen(QPen(QColor(200, 170, 140), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(236, 226, 212))
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.05, bh * 0.06), QPointF(cx + bw * 0.05, bh * 0.06),
                                   QPointF(cx, bh * 0.30)]))
    eaten = ease_out(stage_p) * 0.4 if stage == "eat" else 0.0
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(248, 182, 206))
    r = bw * 0.13 * (1 - eaten)
    cy = -bh * 0.04
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        painter.drawEllipse(QPointF(cx + math.cos(a) * r * 0.6, cy + math.sin(a) * r * 0.6), r * 0.55, r * 0.55)
    painter.drawEllipse(QPointF(cx, cy), r * 0.82, r * 0.82)


def draw_burger(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吃汉堡 层层叠"""
    cx, cy = bw * 0.30, bh * 0.04
    if stage == "munch":
        cy += math.sin(t * 5) * bh * 0.015
    w = bw * 0.28
    painter.setPen(QPen(QColor(200, 150, 90), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(228, 180, 112))
    painter.drawRoundedRect(QRectF(cx - w / 2, cy + bh * 0.10, w, bh * 0.07), bw * 0.025, bw * 0.025)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(120, 78, 52))
    painter.drawRoundedRect(QRectF(cx - w * 0.54, cy + bh * 0.07, w * 1.08, bh * 0.05), bw * 0.02, bw * 0.02)
    painter.setBrush(QColor(248, 205, 100))
    painter.drawPolygon(QPolygonF([QPointF(cx - w * 0.5, cy + bh * 0.06), QPointF(cx + w * 0.5, cy + bh * 0.06),
                                   QPointF(cx + w * 0.4, cy + bh * 0.12), QPointF(cx - w * 0.4, cy + bh * 0.12)]))
    painter.setBrush(QColor(142, 198, 122))
    lp = QPainterPath(QPointF(cx - w * 0.55, cy + bh * 0.07))
    for k in range(7):
        lp.lineTo(QPointF(cx - w * 0.55 + k * w * 0.18, cy + bh * 0.07 + (bh * 0.018 if k % 2 else -bh * 0.008)))
    lp.lineTo(QPointF(cx + w * 0.55, cy + bh * 0.085))
    lp.lineTo(QPointF(cx - w * 0.55, cy + bh * 0.085))
    lp.closeSubpath()
    painter.drawPath(lp)
    painter.setPen(QPen(QColor(200, 150, 90), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(234, 188, 120))
    dome = QPainterPath()
    dome.moveTo(cx - w / 2, cy + bh * 0.05)
    dome.quadTo(cx, cy - bh * 0.10, cx + w / 2, cy + bh * 0.05)
    dome.closeSubpath()
    painter.drawPath(dome)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(250, 240, 210))
    for dx, dy in ((-0.16, -0.01), (0.0, -0.05), (0.16, -0.01)):
        painter.drawEllipse(QPointF(cx + dx * w, cy - bh * 0.0 + dy * bh), bw * 0.012, bw * 0.008)


def draw_noodles(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吃面 筷子挑面 热气腾腾"""
    cx = bw * 0.28
    painter.setPen(QPen(QColor(150, 160, 180), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(222, 232, 242))
    painter.drawChord(QRectF(cx - bw * 0.15, bh * 0.04, bw * 0.30, bh * 0.26), 0, -180 * 16)
    painter.setPen(QPen(QColor(240, 215, 140), max(1.2, bw * 0.01)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for k in range(3):
        painter.drawArc(QRectF(cx - bw * 0.10 + k * bw * 0.02, bh * 0.07, bw * 0.16, bh * 0.10), 20 * 16, 140 * 16)
    lift = bh * 0.18 if stage == "slurp" else bh * 0.10
    painter.setPen(QPen(QColor(240, 215, 140), max(1.0, bw * 0.008)))
    for dx in (-0.01, 0.02, 0.05):
        painter.drawLine(QPointF(cx + dx * bw, bh * 0.08 - lift + bh * 0.02),
                         QPointF(cx + dx * bw + math.sin(t * 2 + dx) * bw * 0.01, bh * 0.08 - lift + bh * 0.13))
    painter.setPen(QPen(QColor(180, 130, 90), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(cx - bw * 0.02, bh * 0.08 - lift), QPointF(cx + bw * 0.05, bh * 0.10))
    painter.drawLine(QPointF(cx + bw * 0.02, bh * 0.08 - lift), QPointF(cx + bw * 0.09, bh * 0.10))
    if stage == "slurp":
        painter.setPen(QPen(QColor(220, 220, 230, 130), max(0.8, bw * 0.005)))
        for s in range(2):
            painter.drawArc(QRectF(cx - bw * 0.06 + s * bw * 0.09, -bh * 0.10, bw * 0.05, bh * 0.12), 0, 180 * 16)


def draw_tea(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """喝茶 茶杯+碟+热气"""
    cx, cy = bw * 0.30, bh * 0.10
    painter.setPen(QPen(QColor(180, 170, 160), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(240, 236, 228))
    painter.drawEllipse(QPointF(cx, cy + bh * 0.10), bw * 0.16, bw * 0.05)
    painter.setBrush(QColor(250, 248, 242))
    painter.drawChord(QRectF(cx - bw * 0.11, cy - bh * 0.06, bw * 0.22, bh * 0.20), 0, -180 * 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(182, 132, 82, 210))
    painter.drawEllipse(QPointF(cx, cy - bh * 0.015), bw * 0.085, bw * 0.03)
    painter.setPen(QPen(QColor(200, 190, 180), max(1.2, bw * 0.01)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(cx + bw * 0.08, cy - bh * 0.04, bw * 0.08, bh * 0.10), -80 * 16, 180 * 16)
    if stage in ("sip", "steam"):
        painter.setPen(QPen(QColor(220, 220, 230, 140), max(0.8, bw * 0.005)))
        for s in range(2):
            painter.drawArc(QRectF(cx - bw * 0.05 + s * bw * 0.07, cy - bh * 0.24, bw * 0.05, bh * 0.16), 0, 180 * 16)


def draw_marshmallow(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """烤棉花糖 篝火上举棒子烤"""
    fx = bw * 0.16
    flick = 0.8 + 0.2 * math.sin(t * 9)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(245, 150, 60, 220))
    painter.drawPolygon(QPolygonF([QPointF(fx - bw * 0.06, bh * 0.30), QPointF(fx + bw * 0.06, bh * 0.30),
                                   QPointF(fx, bh * 0.30 - bh * 0.18 * flick)]))
    painter.setBrush(QColor(250, 212, 92, 230))
    painter.drawPolygon(QPolygonF([QPointF(fx - bw * 0.03, bh * 0.30), QPointF(fx + bw * 0.03, bh * 0.30),
                                   QPointF(fx, bh * 0.30 - bh * 0.10 * flick)]))
    painter.setPen(QPen(QColor(140, 100, 70), max(1.2, bw * 0.01)))
    painter.drawLine(QPointF(fx - bw * 0.08, bh * 0.32), QPointF(fx + bw * 0.06, bh * 0.30))
    painter.drawLine(QPointF(fx - bw * 0.06, bh * 0.30), QPointF(fx + bw * 0.08, bh * 0.32))
    tip = QPointF(fx + bw * 0.02, bh * 0.30 - bh * 0.20)
    painter.setPen(QPen(QColor(170, 130, 90), max(1.0, bw * 0.008)))
    painter.drawLine(QPointF(bw * 0.44, bh * 0.05), tip)
    painter.setPen(QPen(QColor(210, 190, 160), max(0.9, bw * 0.006)))
    painter.setBrush(QColor(228, 200, 150) if stage == "roast" else QColor(250, 246, 236))
    painter.drawRoundedRect(QRectF(tip.x() - bw * 0.04, tip.y() - bh * 0.05, bw * 0.08, bh * 0.10), bw * 0.02, bw * 0.02)


def draw_sweetpotato(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """烤红薯 热腾腾 掰开露橙瓤"""
    cx, cy = bw * 0.30, bh * 0.04
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(-18)
    painter.setPen(QPen(QColor(150, 90, 60), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(188, 122, 86))
    painter.drawEllipse(QPointF(0, 0), bw * 0.15, bh * 0.10)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(122, 78, 54))
    for dx, dy in ((-0.06, 0.0), (0.04, 0.02), (0.08, -0.01)):
        painter.drawEllipse(QPointF(dx * bw, dy * bh), bw * 0.015, bw * 0.012)
    if stage == "eat":
        painter.setBrush(QColor(240, 162, 92))
        painter.drawEllipse(QPointF(0, 0), bw * 0.10 * stage_p, bh * 0.05 * stage_p)
    painter.restore()
    painter.setPen(QPen(QColor(220, 220, 230, 120), max(0.8, bw * 0.005)))
    for s in range(2):
        painter.drawArc(QRectF(cx - bw * 0.05 + s * bw * 0.07, cy - bh * 0.20, bw * 0.05, bh * 0.14), 0, 180 * 16)


def draw_cupcake(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吹蜡烛 小蛋糕 一吹冒烟"""
    cx, cy = bw * 0.30, bh * 0.10
    painter.setPen(QPen(QColor(200, 150, 120), max(1.0, bw * 0.007)))
    painter.setBrush(QColor(228, 176, 150))
    painter.drawPolygon(QPolygonF([QPointF(cx - bw * 0.10, cy), QPointF(cx + bw * 0.10, cy),
                                   QPointF(cx + bw * 0.07, cy + bh * 0.16), QPointF(cx - bw * 0.07, cy + bh * 0.16)]))
    painter.setPen(QPen(QColor(210, 160, 130, 150), max(0.6, bw * 0.004)))
    for k in (-1, 0, 1):
        painter.drawLine(QPointF(cx + k * bw * 0.05, cy), QPointF(cx + k * bw * 0.035, cy + bh * 0.16))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(246, 196, 210))
    painter.drawEllipse(QPointF(cx, cy - bh * 0.02), bw * 0.11, bh * 0.07)
    painter.drawEllipse(QPointF(cx, cy - bh * 0.08), bw * 0.08, bh * 0.05)
    painter.setBrush(QColor(150, 180, 230))
    painter.drawRect(QRectF(cx - bw * 0.01, cy - bh * 0.20, bw * 0.02, bh * 0.08))
    if stage == "blow" and stage_p > 0.4:
        painter.setPen(QPen(QColor(200, 200, 210, 150), max(0.8, bw * 0.005)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(cx - bw * 0.02, cy - bh * 0.30, bw * 0.04, bh * 0.10), 0, 180 * 16)
    else:
        painter.setBrush(QColor(250, 200, 90))
        painter.drawEllipse(QPointF(cx, cy - bh * 0.23), bw * 0.02, bh * 0.04 * (1.0 + math.sin(t * 10) * 0.1))


def draw_pizza(painter: QPainter, bw: float, bh: float, t: float, stage: str, stage_p: float) -> None:
    """吃披萨 一角 啃掉里头"""
    cx, cy = bw * 0.30, bh * 0.04
    if stage == "munch":
        cy += math.sin(t * 5) * bh * 0.015
    apex = QPointF(cx - bw * 0.02, bh * 0.26)
    L, R = QPointF(cx - bw * 0.16, -bh * 0.10), QPointF(cx + bw * 0.16, -bh * 0.06)
    painter.setPen(QPen(QColor(210, 170, 110), max(1.0, bw * 0.008)))
    painter.setBrush(QColor(240, 205, 130))
    painter.drawPolygon(QPolygonF([apex, L, R]))
    bite = ease_out(stage_p) * 0.55 if stage == "munch" else 0.0
    mL = QPointF(L.x() + (apex.x() - L.x()) * (0.18 + bite), L.y() + (apex.y() - L.y()) * (0.18 + bite))
    mR = QPointF(R.x() + (apex.x() - R.x()) * (0.18 + bite), R.y() + (apex.y() - R.y()) * (0.18 + bite))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(248, 222, 140))
    painter.drawPolygon(QPolygonF([apex, mL, mR]))
    painter.setBrush(QColor(214, 80, 72))
    for fx in (0.4, 0.62, 0.46):
        c = QPointF(apex.x() + ((mL.x() + mR.x()) / 2 - apex.x()) * fx,
                    apex.y() + (((L.y() + R.y()) / 2) - apex.y()) * fx)
        painter.drawEllipse(QPointF(c.x() + (fx - 0.5) * bw * 0.1, c.y()), bw * 0.02, bw * 0.02)
