# 记忆天气粒子层 全屏穿透 根据情绪/环境信号在宠物附近画轻量粒子

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

# ── 天气配置 ──────────────────────────────────────────────


@dataclass
class _WeatherProfile:
    shapes: list[str]                       # "dot" / "line" / "star4" / "ring"
    count: tuple[int, int]                  # (min, max) 粒子数
    colors: list[str]                       # hex 颜色池
    drift_x: float = 0.0                   # 水平漂移 px/s
    drift_y: float = 0.0                   # 垂直漂移 px/s
    drift_jitter: float = 20.0             # 速度随机抖动范围
    size_range: tuple[float, float] = (2.0, 5.0)
    lifetime_range: tuple[float, float] = (3.0, 6.0)
    spread: int = 120                       # 生成半径 px


_PROFILES: dict[str, _WeatherProfile] = {
    "clear": _WeatherProfile(shapes=[], count=(0, 0), colors=[]),
    "rain": _WeatherProfile(
        shapes=["line"], count=(6, 10),
        colors=["#8899bb", "#7788aa", "#99aabb"],
        drift_x=15.0, drift_y=80.0, drift_jitter=10.0,
        size_range=(6.0, 12.0), lifetime_range=(2.0, 3.5), spread=140,
    ),
    "fog": _WeatherProfile(
        shapes=["dot"], count=(3, 5),
        colors=["#aaa8a0", "#bbb9b2", "#9e9c94"],
        drift_x=12.0, drift_y=2.0, drift_jitter=5.0,
        size_range=(8.0, 16.0), lifetime_range=(5.0, 8.0), spread=160,
    ),
    "stars": _WeatherProfile(
        shapes=["star4"], count=(4, 7),
        colors=["#ffc452", "#ffe08a", "#ffd060"],
        drift_x=3.0, drift_y=-8.0, drift_jitter=4.0,
        size_range=(2.5, 4.5), lifetime_range=(4.0, 7.0), spread=130,
    ),
    "warm": _WeatherProfile(
        shapes=["dot", "ring"], count=(5, 8),
        colors=["#f0a080", "#f0b890", "#e89878"],
        drift_x=5.0, drift_y=-3.0, drift_jitter=8.0,
        size_range=(2.0, 5.0), lifetime_range=(3.0, 5.0), spread=110,
    ),
    "static": _WeatherProfile(
        shapes=["line"], count=(4, 6),
        colors=["#cccccc", "#bbbbbb", "#dddddd"],
        drift_x=0.0, drift_y=0.0, drift_jitter=40.0,
        size_range=(3.0, 7.0), lifetime_range=(0.8, 1.8), spread=100,
    ),
    "gentle": _WeatherProfile(
        shapes=["dot"], count=(3, 5),
        colors=["#88c4a0", "#90d0a8", "#78b898"],
        drift_x=2.0, drift_y=-1.5, drift_jitter=3.0,
        size_range=(2.0, 4.0), lifetime_range=(4.0, 7.0), spread=100,
    ),
}

# ── 粒子 ─────────────────────────────────────────────────


@dataclass
class _Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: float = 1.0
    age: float = 0.0
    lifetime: float = 4.0
    shape: str = "dot"
    color: QColor = field(default_factory=lambda: QColor(255, 255, 255))
    draining: bool = False   # True = 天气已变 正在淡出 不再补


# ── 粒子层 ───────────────────────────────────────────────


class WeatherOverlay(QWidget):
    """全屏穿透层 画记忆天气粒子"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._particles: list[_Particle] = []
        self._profile = _PROFILES["clear"]
        self._kind = "clear"
        self._origin = QPoint()          # 宠物中心屏幕坐标
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._last_t = 0.0

    # ── 公开接口 ──────────────────────────────────────────

    def set_weather(self, kind: str, pet_center: QPoint) -> None:
        """切换天气种类 旧粒子渐出 新粒子渐入"""
        if kind == self._kind and self._particles:
            self._origin = pet_center
            return
        self._kind = kind
        self._profile = _PROFILES.get(kind, _PROFILES["clear"])
        self._origin = pet_center
        # 旧粒子标记 draining 让它们自然淡出
        for p in self._particles:
            if not p.draining:
                p.draining = True
                p.lifetime = min(p.lifetime, p.age + 1.0)
        if kind == "clear":
            if not self._particles:
                self._hide_immediate()
            return
        self._spawn_initial()
        self.show_layer()

    def track_pet(self, center: QPoint) -> None:
        """宠物移动时平移所有粒子"""
        dx = center.x() - self._origin.x()
        dy = center.y() - self._origin.y()
        if abs(dx) < 2 and abs(dy) < 2:
            return
        for p in self._particles:
            p.x += dx
            p.y += dy
        self._origin = center

    def show_layer(self) -> None:
        if not self.isVisible():
            scr = self.screen()
            if scr is None:
                return
            self.setGeometry(scr.virtualGeometry())
            self.show()
            self._ensure_win32_passthrough()
        if not self._timer.isActive():
            self._last_t = time.monotonic()
            self._timer.start(80)

    def hide_layer(self) -> None:
        """优雅淡出 — 标记 draining 等 _tick 发现全部死光再关"""
        for p in self._particles:
            p.draining = True
            p.lifetime = min(p.lifetime, p.age + 1.0)
        self._kind = "clear"
        self._profile = _PROFILES["clear"]

    def _hide_immediate(self) -> None:
        """无粒子时直接隐藏"""
        self._timer.stop()
        self._particles.clear()
        self.hide()

    # ── 内部 ──────────────────────────────────────────────

    def _ensure_win32_passthrough(self) -> None:
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x20 | 0x80000)
        except Exception:
            pass

    def _spawn_initial(self) -> None:
        prof = self._profile
        lo, hi = prof.count
        n = random.randint(lo, hi) if hi > lo else lo
        for _ in range(n):
            self._particles.append(self._make_particle())

    def _make_particle(self) -> _Particle:
        prof = self._profile
        angle = random.uniform(0, math.tau)
        dist = random.uniform(0, prof.spread)
        ox, oy = self._origin.x(), self._origin.y()
        x = ox + math.cos(angle) * dist
        y = oy + math.sin(angle) * dist
        vx = prof.drift_x + random.uniform(-prof.drift_jitter, prof.drift_jitter)
        vy = prof.drift_y + random.uniform(-prof.drift_jitter, prof.drift_jitter)
        size = random.uniform(*prof.size_range)
        lt = random.uniform(*prof.lifetime_range)
        shape = random.choice(prof.shapes) if prof.shapes else "dot"
        color = QColor(random.choice(prof.colors))
        return _Particle(x=x, y=y, vx=vx, vy=vy, size=size,
                         lifetime=lt, shape=shape, color=color)

    def _tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now
        if dt > 0.5:
            dt = 0.08

        prof = self._profile
        alive: list[_Particle] = []
        for p in self._particles:
            p.age += dt
            if p.age >= p.lifetime:
                continue
            # 淡入前 20% 淡出后 30%
            progress = p.age / p.lifetime
            if progress < 0.2:
                p.alpha = progress / 0.2
            elif progress > 0.7:
                p.alpha = (1.0 - progress) / 0.3
            else:
                p.alpha = 1.0
            # 静电天气抖动
            if self._kind == "static":
                p.vx += random.uniform(-60, 60) * dt
                p.vy += random.uniform(-60, 60) * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self._particles = alive

        # 只给非 draining 的天气补粒子
        non_draining = sum(1 for p in self._particles if not p.draining)
        lo, hi = prof.count
        target = random.randint(lo, hi) if hi > lo else lo
        while non_draining < target:
            self._particles.append(self._make_particle())
            non_draining += 1

        if not self._particles and self._kind == "clear":
            self._hide_immediate()
            return
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        origin = self.geometry().topLeft()
        for p in self._particles:
            a = max(0, min(255, int(p.alpha * 160)))
            if a <= 0:
                continue
            c = QColor(p.color)
            c.setAlpha(a)
            # 屏幕坐标减去窗口原点
            lx = p.x - origin.x()
            ly = p.y - origin.y()
            if p.shape == "dot":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c)
                painter.drawEllipse(QPointF(lx, ly), p.size, p.size)
            elif p.shape == "line":
                pen = QPen(c, max(1.0, p.size * 0.3))
                painter.setPen(pen)
                painter.drawLine(QPointF(lx, ly), QPointF(lx + p.size * 0.2, ly + p.size))
            elif p.shape == "star4":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c)
                _draw_star4(painter, lx, ly, p.size)
            elif p.shape == "ring":
                pen = QPen(c, max(1.0, p.size * 0.25))
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(lx, ly), p.size, p.size)

        painter.end()


def _draw_star4(painter: QPainter, cx: float, cy: float, r: float) -> None:
    """画一个简单的四角星"""
    inner = r * 0.4
    points = []
    for i in range(8):
        angle = i * math.tau / 8 - math.pi / 2
        radius = r if i % 2 == 0 else inner
        points.append(QPointF(cx + math.cos(angle) * radius,
                               cy + math.sin(angle) * radius))
    from PySide6.QtGui import QPolygonF
    painter.drawPolygon(QPolygonF(points))
