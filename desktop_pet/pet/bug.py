# author: bdth
# email: 2074055628@qq.com
# 垃圾虫 在桌宠旁爬 点死触发真清理

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from desktop_pet.eyes import capture
from desktop_pet.pet.fx import make_floating

_SIZE = 72
_TICK_MS = 16
_WANDER = 90  # 出生点附近活动半径
_LIFE_S = 600.0  # 没人理这么久就溜了
_SPOOK_DIST = 80.0  # 鼠标逼近到这距离会受惊逃窜
_SQUISH_DUR = 0.65
_INK = QColor(40, 38, 48)
_SHELL = QColor(72, 66, 92)
_SHELL_HI = QColor(118, 110, 146)
_HEAD = QColor(52, 48, 66)


class BugWindow(QWidget):
    squished = Signal()
    escaped = Signal()

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.resize(_SIZE, _SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self._born = time.time()
        self._phase = random.uniform(0, math.tau)
        self._home = QPointF()
        self._pos = QPointF()
        self._heading = random.uniform(0, math.tau)
        self._speed = 0.0
        self._spook = 0.0  # >0 受惊逃窜中
        self._pause = 0.0  # >0 停下来东张西望
        self._squish = -1.0  # >=0 死亡动画
        self._splats: list[tuple[float, float, float, float]] = []  # 溅墨方向 速度 大小 旋转
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def closeEvent(self, event) -> None:
        # 注销自家窗口登记 别让死句柄堆在 capture._own_hwnds 里 句柄会被回收复用误伤别家窗口
        capture.unregister_own_window(int(self.winId()))
        super().closeEvent(event)

    def spawn_near(self, x: int, y: int, screen) -> None:
        """在某点附近落地开爬"""
        self._home = QPointF(x, y)
        self._pos = QPointF(x, y)
        self._born = time.time()
        self._screen = screen
        self.move(int(x - _SIZE / 2), int(y - _SIZE / 2))
        self.show()
        self._timer.start(_TICK_MS)

    def _tick(self) -> None:
        dt = _TICK_MS / 1000.0
        self._t += dt
        if self._squish >= 0:
            self._squish += dt
            if self._squish > _SQUISH_DUR:
                self._timer.stop()
                self.close()
                self.squished.emit()
                return
            self.update()
            return
        if time.time() - self._born > _LIFE_S:
            self._timer.stop()
            self.close()
            self.escaped.emit()
            return
        # 鼠标逼近受惊 往反方向窜
        try:
            cur = QCursor.pos()
            dxm, dym = cur.x() - self._pos.x(), cur.y() - self._pos.y()
            dist = math.hypot(dxm, dym)
            if dist < _SPOOK_DIST and self._spook <= 0:
                self._spook = 0.55
                self._pause = 0.0
                self._heading = math.atan2(-dym, -dxm) + random.uniform(-0.4, 0.4)
        except Exception:
            pass
        if self._spook > 0:
            self._spook -= dt
            target = 120.0
        elif self._pause > 0:
            self._pause -= dt
            target = 0.0
        else:
            if random.random() < 0.008:  # 偶尔停下来东张西望
                self._pause = random.uniform(0.5, 1.4)
            if random.random() < 0.03:
                self._heading += random.uniform(-1.4, 1.4)
            target = 26.0 * (0.55 + 0.45 * math.sin(self._t * 1.7 + self._phase))
        self._speed += (target - self._speed) * min(1.0, dt * 10)  # 加减速平滑
        self._pos += QPointF(math.cos(self._heading) * self._speed * dt,
                             math.sin(self._heading) * self._speed * dt)
        off = self._pos - self._home
        if math.hypot(off.x(), off.y()) > _WANDER:  # 出圈掉头回家
            self._heading = math.atan2(-off.y(), -off.x()) + random.uniform(-0.5, 0.5)
        scr = getattr(self, "_screen", None)
        if scr is not None:
            self._pos.setX(max(scr.left() + _SIZE, min(self._pos.x(), scr.right() - _SIZE)))
            self._pos.setY(max(scr.top() + _SIZE, min(self._pos.y(), scr.bottom() - _SIZE)))
        self.move(int(self._pos.x() - _SIZE / 2), int(self._pos.y() - _SIZE / 2))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._squish < 0:
            self._squish = 0.0
            # 随机一批溅墨参数 方向避开正上 往两侧和下溅更像被拍
            self._splats = [
                (random.uniform(0, math.tau), random.uniform(26, 64),
                 random.uniform(2.0, 4.2), random.uniform(0, 360))
                for _ in range(9)
            ]
        event.accept()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(_SIZE / 2, _SIZE / 2)
        if self._squish >= 0:
            self._paint_squish(painter)
            return
        # 贴地影子 不随身体转
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(40, 38, 48, 36))
        painter.drawEllipse(QPointF(0, 15), 13.0, 4.0)

        painter.rotate(math.degrees(self._heading) + 90)  # 头朝前进方向
        moving = self._speed > 4.0
        gait = self._t * (16 if self._spook > 0 else 10)
        swing = math.sin(gait + self._phase) if moving else 0.0
        bob = abs(math.sin(gait + self._phase)) * 1.0 if moving else math.sin(self._t * 2.5) * 0.4
        sway = math.sin(gait * 0.5 + self._phase) * (2.5 if moving else 0.0)
        painter.rotate(sway)
        painter.translate(0, -bob)

        # 六条两段腿 三角步态 同组同相
        pen = QPen(_INK)
        pen.setWidthF(2.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for side in (-1, 1):
            for i in range(3):
                tripod = (i % 2 == 0) == (side > 0)
                ph = swing if tripod else -swing
                hip = QPointF(side * 5.5, -7.5 + i * 7.0)
                knee = QPointF(hip.x() + side * (4.6 + 1.0 * ph), hip.y() + 0.8 + 0.8 * ph)
                lift = max(0.0, ph if tripod else -ph) * 1.8  # 摆动腿微抬
                foot = QPointF(knee.x() + side * (3.8 + 1.6 * ph), knee.y() + 4.6 - 2.4 * ph - lift)
                painter.drawLine(hip, knee)
                painter.drawLine(knee, foot)

        # 触角 两段 末端小球 停下时试探摆
        ant_w = math.sin(self._t * (6.0 if not moving else 3.0) + self._phase) * (2.2 if not moving else 1.2)
        thin = QPen(_INK)
        thin.setWidthF(1.5)
        thin.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(thin)
        for side in (-1, 1):
            a0 = QPointF(side * 2.6, -12.5)
            a1 = QPointF(side * (5.0 + ant_w * 0.4), -16.5)
            a2 = QPointF(side * (6.5 + ant_w), -20.0 + abs(ant_w) * 0.3)
            painter.drawLine(a0, a1)
            painter.drawLine(a1, a2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_INK)
            painter.drawEllipse(a2, 1.4, 1.4)
            painter.setPen(thin)

        # 腹部 渐变带横纹
        painter.setPen(QPen(_INK, 1.5))
        grad = QLinearGradient(-8, 0, 8, 0)
        grad.setColorAt(0.0, _SHELL)
        grad.setColorAt(0.38, _SHELL_HI)
        grad.setColorAt(1.0, _SHELL)
        painter.setBrush(grad)
        painter.drawEllipse(QPointF(0, 5.5), 7.6, 9.6)
        painter.setPen(QPen(QColor(34, 32, 44, 130), 1.1))
        for i in range(3):
            yy = 2.0 + i * 3.4
            w = 7.0 - i * 0.9
            painter.drawArc(QRectF(-w, yy, w * 2, 3.2), 200 * 16, 140 * 16)
        # 胸节
        painter.setPen(QPen(_INK, 1.4))
        painter.setBrush(_HEAD)
        painter.drawEllipse(QPointF(0, -5.5), 5.6, 5.2)
        # 头 带两个小眼点
        painter.drawEllipse(QPointF(0, -11.0), 4.4, 3.8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(235, 232, 245))
        painter.drawEllipse(QPointF(-1.8, -11.6), 1.0, 1.0)
        painter.drawEllipse(QPointF(1.8, -11.6), 1.0, 1.0)
        # 背脊高光
        painter.setPen(QPen(QColor(150, 142, 180, 120), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(0, 0.5), QPointF(0, 12.0))

    def _paint_squish(self, painter: QPainter) -> None:
        """三段死亡 压扁X眼 泪滴溅墨 化墨渍淡出"""
        p = min(1.0, self._squish / _SQUISH_DUR)
        # 地上的墨渍 越到后面越淡
        stain = max(0.0, (p - 0.25) / 0.75)
        if stain > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(50, 46, 64, int(110 * (1 - stain * 0.9))))
            painter.drawEllipse(QPointF(0, 6), 12.0 + 5 * stain, 4.5 + 1.5 * stain)
        # 本体 被拍瞬间压扁 然后渐隐
        squash = min(1.0, p / 0.18)
        alpha = max(0, int(255 * (1 - max(0.0, (p - 0.3) / 0.45))))
        if alpha > 0:
            painter.setPen(QPen(QColor(_INK.red(), _INK.green(), _INK.blue(), alpha), 1.4))
            painter.setBrush(QColor(_SHELL.red(), _SHELL.green(), _SHELL.blue(), alpha))
            bw_, bh_ = 9.0 + 7.0 * squash, max(2.2, 10.0 * (1 - squash * 0.78))
            painter.drawEllipse(QPointF(0, 4), bw_, bh_)
            # X眼
            xp = QPen(QColor(235, 232, 245, alpha))
            xp.setWidthF(1.6)
            xp.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(xp)
            for sx in (-1, 1):
                cx = sx * 4.5
                painter.drawLine(QPointF(cx - 1.6, 2.4), QPointF(cx + 1.6, 5.6))
                painter.drawLine(QPointF(cx + 1.6, 2.4), QPointF(cx - 1.6, 5.6))
        # 泪滴溅墨 沿各自方向飞 带一点下坠
        painter.setPen(Qt.PenStyle.NoPen)
        fly = min(1.0, p / 0.5)
        fade = max(0, int(225 * (1 - fly)))
        if fade > 0:
            for ang, spd, size, rot in self._splats:
                r = spd * fly
                x = math.cos(ang) * r
                y = math.sin(ang) * r + 14 * fly * fly  # 重力
                painter.save()
                painter.translate(x, y)
                painter.rotate(math.degrees(ang) + rot * fly)
                painter.setBrush(QColor(50, 46, 64, fade))
                painter.drawEllipse(QPointF(0, 0), size * (1.5 - 0.5 * fly), size * 0.62)
                painter.restore()
