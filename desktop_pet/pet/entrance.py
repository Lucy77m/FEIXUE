# author: bdth
# email: 2074055628@qq.com
# 桌宠出场动画:定义多种登场方式(掉落/淡入/滑入/升起/开门/传送/降落伞)及其窗口与形体变换

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from desktop_pet.pet.character import BLOB_HALF_H
from desktop_pet.settings import DATA_DIR

ENTRANCE_KINDS = ("drop", "fade_pop", "slide", "rise", "door", "teleport", "parachute")

_DURATION = {
    "drop": 1.1,
    "fade_pop": 0.7,
    "slide": 0.85,
    "rise": 0.95,
    "door": 1.4,
    "teleport": 0.95,
    "parachute": 1.7,
}
_DEFAULT_DURATION = 1.0

_LAST_ENTRANCE_PATH = DATA_DIR / "last_entrance.txt"


def next_entrance_kind() -> str:
    """随机挑一种出场方式 —— 落盘记住上次，避免连着两回同一种(只有 1 种时退化全集)。"""
    try:
        last = _LAST_ENTRANCE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        last = ""
    choices = [k for k in ENTRANCE_KINDS if k != last] or list(ENTRANCE_KINDS)
    kind = random.choice(choices)
    try:
        _LAST_ENTRANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_ENTRANCE_PATH.write_text(kind, encoding="utf-8")
    except OSError:
        pass  # 写不进去(只读盘/权限)就算了，大不了下次可能重样
    return kind


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _ease_in(p: float) -> float:
    return p * p


def _ease_out_back(p: float) -> float:
    """回弹缓动：先冲过头再收回，c=1.70158 是常见的过冲量(约 10%)，给 pop/传送一点弹性。"""
    c = 1.70158
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2


def _clamp01(p: float) -> float:
    return max(0.0, min(1.0, p))


def _seg(p: float, a: float, b: float) -> float:
    """把全程进度 p 切出 [a,b] 这一小段并重映射回 0~1 —— 多段动画各管各的时间窗，靠它分段。"""
    return _clamp01((p - a) / (b - a)) if b > a else 0.0  # b<=a 防 0 除，直接当没开始


class Entrance:
    """一次出场动画的状态机：拿全程进度 p(0~1)，吐出窗口位置/透明度、形体变换、道具绘制。"""

    def __init__(self, kind: str, screen, rest, win_w: int, win_h: int) -> None:
        self.kind = kind
        self.duration = _DURATION.get(kind, _DEFAULT_DURATION)
        self._screen = screen
        self._rest = rest
        self._w = win_w
        self._h = win_h
        # 落点偏屏幕哪半边 —— slide 据此决定从左还是从右飞进来，省得横穿整屏
        self._from_right = rest.x() + win_w / 2 >= screen.center().x()

    def window_state(self, p: float):
        """整窗的位移/透明度。各 kind 自己算起点，默认就停在落点 rest 上(door/teleport 走这条)。"""
        rx, ry = float(self._rest.x()), float(self._rest.y())
        x, y, opacity = rx, ry, 1.0
        if self.kind == "drop":
            start_y = self._screen.top() - self._h  # 从屏幕上沿外侧起跳，保证整窗在外看不见
            y = start_y + (ry - start_y) * _ease_in(_seg(p, 0.0, 0.78))  # ease_in=越掉越快，像自由落体
        elif self.kind == "parachute":
            start_y = self._screen.top() - self._h
            y = start_y + (ry - start_y) * _seg(p, 0.0, 0.9)  # 匀速飘 —— 伞嘛，慢慢下，到 0.9 落地
        elif self.kind == "rise":
            start_y = float(self._screen.bottom())
            bounce = math.sin(_seg(p, 0.0, 1.0) * math.pi) * self._h * 0.06  # 半个正弦的小过冲，冒头时颠一下
            y = start_y + (ry - start_y) * _ease_out(_seg(p, 0.0, 0.85)) - bounce
        elif self.kind == "slide":
            start_x = float(self._screen.right()) if self._from_right else float(self._screen.left() - self._w)
            over = math.sin(_seg(p, 0.0, 1.0) * math.pi) * self._w * 0.05 * (-1 if self._from_right else 1)  # 冲过头再回弹，方向跟着来向取反
            x = start_x + (rx - start_x) * _ease_out(_seg(p, 0.0, 0.85)) + over
        elif self.kind == "fade_pop":
            opacity = _seg(p, 0.0, 0.4)  # 前 40% 淡入，剩下交给 blob_transform 弹大
        return QPointF(x, y), _clamp01(opacity)

    def blob_transform(self, p: float):
        """形体自身的缩放/纵偏(sx,sy,oy,rot) —— 跟 window_state 叠加，落地挤压、pop 弹大都在这。"""
        sx = sy = 1.0
        oy = rot = 0.0
        if self.kind in ("drop", "rise", "parachute"):
            land = _seg(p, 0.82, 1.0)  # 最后 18% 才触发落地挤压，前面纯位移
            if land > 0:
                s = math.sin(land * math.pi)  # 半正弦：挤扁→弹回，单峰，结束自动归位
                sx, sy = 1 + 0.22 * s, 1 - 0.22 * s  # 横胖纵扁，体积感觉守恒(果冻 squash)
        elif self.kind == "fade_pop":
            sx = sy = _ease_out_back(_seg(p, 0.0, 1.0))  # 从 0 弹出并过冲，配合前面的淡入
        elif self.kind == "teleport":
            sx = sy = _ease_out_back(_seg(p, 0.45, 0.85))  # 前半截在传送光圈里(0~0.45)还没显形
        elif self.kind == "door":
            g = _seg(p, 0.32, 0.72)
            sx = sy = g  # 门开到一定程度(0.32)才开始长出来
            oy = (1 - g) * self._h * 0.12  # 没长全时往下压一点，像还卡在门框里
        return sx, sy, oy, rot

    def draw_props(self, painter: QPainter, w: int, h: int, p: float) -> None:
        """画在形体「身后」的道具(门/传送火花/降落伞)，没有就直接 no-op。"""
        if self.kind == "door":
            self._draw_door(painter, w, h, p)
        elif self.kind == "teleport":
            self._draw_teleport(painter, w, h, p)
        elif self.kind == "parachute":
            self._draw_parachute(painter, w, h, p)

    def draw_overlay(self, painter: QPainter, w: int, h: int, p: float) -> None:
        """画在形体「上面」的覆盖层 —— 目前只有传送那圈扩散光环。"""
        if self.kind == "teleport":
            flash = _seg(p, 0.45, 0.82)  # 形体显形那一刻(0.45)起爆一圈
            if 0 < flash < 1:
                ring = QPen(QColor(205, 232, 255, int(220 * (1 - flash))))  # 越扩越淡
                ring.setWidthF(w * 0.03)
                painter.setPen(ring)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                r = min(w, h) * 0.42 * flash
                painter.drawEllipse(QPointF(w / 2, h * 0.5), r, r)

    def _draw_door(self, painter: QPainter, w: int, h: int, p: float) -> None:
        """门框+往一侧滑开的门板，最后 1/4 整体淡出，把舞台留给走出来的桌宠。"""
        fade = 1.0 - _seg(p, 0.75, 1.0)
        if fade <= 0:
            return  # 0.75 之后门已淡没，别白画一帧
        cx = w / 2
        dw, dh = w * 0.72, h * 0.82
        x0, y0 = cx - dw / 2, h * 0.5 - dh / 2
        radius = dw * 0.12
        painter.setPen(Qt.PenStyle.NoPen)
        frame = QColor(74, 56, 40); frame.setAlphaF(fade)
        painter.setBrush(frame)
        painter.drawRoundedRect(QRectF(x0 - w * 0.03, y0 - h * 0.02, dw + w * 0.06, dh + h * 0.02), radius, radius)
        interior = QColor(34, 30, 30); interior.setAlphaF(fade)
        painter.setBrush(interior)
        painter.drawRoundedRect(QRectF(x0, y0, dw, dh), radius * 0.7, radius * 0.7)
        open_amt = _seg(p, 0.3, 0.62)  # 0.3~0.62 门板从满宽收到 0，看着像往边上拉开
        panel_w = dw * (1 - open_amt)
        if panel_w > 1:  # 收没了(<1px)就别画门板和门把手了
            panel = QColor(120, 92, 60); panel.setAlphaF(fade)
            painter.setBrush(panel)
            painter.drawRoundedRect(QRectF(x0, y0, panel_w, dh), radius * 0.6, radius * 0.6)
            knob = QColor(60, 44, 28); knob.setAlphaF(fade)
            painter.setBrush(knob)
            painter.drawEllipse(QPointF(x0 + panel_w * 0.82, h * 0.5), w * 0.018, w * 0.018)

    def _draw_teleport(self, painter: QPainter, w: int, h: int, p: float) -> None:
        """一圈火花从外往中心聚拢(0~0.55)，聚完正好接 draw_overlay 的爆环+形体显形。"""
        cx, cy = w / 2, h * 0.5
        radius = min(w, h) * 0.45
        conv = _seg(p, 0.0, 0.55)
        painter.setPen(Qt.PenStyle.NoPen)
        if conv < 1.0:  # 聚拢完就收手，剩下交给 overlay
            count = 12
            for i in range(count):
                ang = i / count * 2 * math.pi + p * 3.0  # 均分一圈再叠个旋转，火花边转边收
                dist = radius * (1 - _ease_in(conv))  # 半径往里收，ease_in 让收尾那段加速吸进去
                spark = QColor(150, 200, 255); spark.setAlphaF(1 - conv)
                painter.setBrush(spark)
                painter.drawEllipse(QPointF(cx + math.cos(ang) * dist, cy + math.sin(ang) * dist), w * 0.022, w * 0.022)

    def _draw_parachute(self, painter: QPainter, w: int, h: int, p: float) -> None:
        """半圆伞盖+几根伞绳吊着桌宠。落地(0.82)后伞脱钩往上飘走并淡出。"""
        detach = _seg(p, 0.82, 1.0)
        if detach >= 1.0:
            return  # 飘没了，整伞不画
        alpha = 1 - detach
        cx = w / 2
        cy = h * 0.2 - detach * h * 0.5
        cw = w * 0.46
        canopy = QColor(232, 110, 122); canopy.setAlphaF(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(canopy)
        dome = QPainterPath()
        dome.moveTo(cx - cw / 2, cy)
        dome.arcTo(QRectF(cx - cw / 2, cy - cw * 0.42, cw, cw * 0.84), 0, 180)
        dome.closeSubpath()
        painter.drawPath(dome)
        string = QPen(QColor(90, 70, 60, int(255 * alpha)))
        string.setWidthF(max(1.0, w * 0.007))
        painter.setPen(string)
        blob_top = h / 2 - BLOB_HALF_H  # 伞绳下端连到形体头顶，别穿进身体里
        for f in (-0.42, -0.14, 0.14, 0.42):
            painter.drawLine(
                QPointF(cx + cw / 2 * f, cy),
                QPointF(cx + cw * 0.12 * (1 if f > 0 else -1), blob_top),
            )
