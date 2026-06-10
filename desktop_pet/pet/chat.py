# author: bdth
# email: 2074055628@qq.com
# 聊天显示组件 打字机气泡 思考气泡 思绪粒子 输入框

from __future__ import annotations

import base64
import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QEasingCurve,
    QIODevice,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QTextCursor,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_pet import i18n
from desktop_pet.pet.fx import make_floating as _make_floating

_IMAGE_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".jfif"})
_ATTACH_MAX = 8
_IMG_MAX_SIDE = 1568
_DATAURL_MAX = 2_000_000
_FILE_NAME_MAX = 22

_FONT_PX = 14
_MAX_INNER = 260
_PAD = 14
_LINE_GAP = 4
_TYPE_MS = 26
_HOLD_MS = 1000
_BLANK_MS = 240
_LINGER_MS = 1900
_BELOW_GAP = 6
_INPUT_GAP = 48
_INPUT_FADE_MS = 160
_INPUT_SLIDE = 8
_BUBBLE_FONT_PX = 13
_BUBBLE_PAD = 11
_BUBBLE_MAXW = 280
_BUBBLE_TEXT_FLAGS = int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignCenter)
_BUBBLE_DUR = 1.5
_BUBBLE_RISE = 30
_BUBBLE_STEP_HOLD = 1.3
_BUBBLE_FPS_MS = 1000 // 60
_BUBBLE_TRAIL_H = 18
_BUBBLE_MARGIN = 4
_BUBBLE_BG = QColor(255, 255, 255, 238)
_BUBBLE_INK = QColor(44, 46, 54)
_BUBBLE_EDGE = QColor(0, 0, 0, 38)
_THINK_FONT_PX = 12
_THINK_PAD = 6
_THINK_W = 184
_THINK_H = 150
_THINK_RISE = 116
_THINK_LIFE = (1.3, 1.9)
_THINK_SPAWN = (0.17, 0.34)
_THINK_MAX = 14
_THINK_DRIFT = 15
_THINK_BG = QColor(255, 255, 255, 232)
_THINK_INK = QColor(54, 58, 70)
_THINK_EDGE = QColor(0, 0, 0, 28)
_THINK_FALLBACK = ("∴", "∵", "≈", "‽", "⁇", "⁈", "✦", "✶", "❋", "↻", "⊛", "◌", "⍰", "∞", "⌾", "⊙")
_THINK_SOURCE_MAX = 600
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_CODE = re.compile(r"`+([^`]*)`+")
_MD_EMPH = re.compile(r"\*\*|\*|~~|__")
_MD_LEAD = re.compile(r"^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+)")
_DISPLAY_STRIP = re.compile(r"[。，、；：．.,;:…—～~·]+")
_LONG_CHUNK = 40

_TEXT = QColor(250, 250, 252)
_OUTLINE = QColor(20, 20, 26)
_GLOW = QColor(20, 20, 26, 110)
_OUTLINE_W = 3.5
_GLOW_W = 6.0

_INPUT_W = 372

_PANEL_STYLE = """
#card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 253, 251, 250), stop:1 rgba(247, 243, 251, 250));
    border: 1.5px solid rgba(232, 178, 198, 150);
    border-radius: 20px;
}
#card[focused="true"] {
    border: 1.7px solid rgba(235, 142, 174, 230);
}
QTextEdit#editor {
    background: transparent;
    border: none;
    color: #45424b;
    font-size: 15px;
    selection-background-color: rgba(236, 160, 188, 150);
    selection-color: #322f37;
}
QTextEdit#editor QScrollBar:vertical {
    background: transparent; width: 7px; margin: 3px 1px 3px 0;
}
QTextEdit#editor QScrollBar::handle:vertical {
    background: rgba(214, 196, 224, 200); border-radius: 3px; min-height: 28px;
}
QTextEdit#editor QScrollBar::handle:vertical:hover { background: rgba(150, 124, 226, 220); }
QTextEdit#editor QScrollBar::add-line:vertical, QTextEdit#editor QScrollBar::sub-line:vertical { height: 0; }
QTextEdit#editor QScrollBar::add-page:vertical, QTextEdit#editor QScrollBar::sub-page:vertical { background: transparent; }
QLabel#hint { color: #b9a9b8; font-size: 11px; }
QPushButton#tool {
    background: transparent;
    border: none;
    border-radius: 13px;
    padding: 0;
}
QPushButton#tool:hover { background: rgba(236, 213, 232, 160); }
QPushButton#send {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #8b7bff, stop:1 #6a59f5);
    border: none;
    border-radius: 15px;
    color: white;
    font-size: 15px;
    font-weight: 600;
}
QPushButton#send:hover { background: #5b49ef; }
QPushButton#send:disabled { background: rgba(190, 182, 210, 150); color: rgba(255,255,255,170); }
#chip {
    background: rgba(245, 238, 248, 235);
    border: 1px solid rgba(218, 196, 222, 200);
    border-radius: 10px;
}
#chip QLabel { color: #5d5566; font-size: 11px; background: transparent; }
QPushButton#chipdel {
    background: transparent; border: none; color: #a594aa;
    font-size: 13px; font-weight: 700; padding: 0;
}
QPushButton#chipdel:hover { color: #e8638c; }
"""

_SVG_IMAGE = (
    '<rect x="3" y="3" width="18" height="18" rx="3"/>'
    '<circle cx="8.5" cy="9" r="1.5"/>'
    '<path d="M21 16l-4.5-4.5L7 21"/>'
)
_SVG_CLIP = (
    '<path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19'
    'a3.5 3.5 0 0 1 4.95 4.95l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>'
)
_SVG_SEND = '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>'
_SVG_FILE = (
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'
)


def _svg_pixmap(body: str, px: int, color: str) -> QPixmap:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )
    ratio = 2
    pm = QPixmap(px * ratio, px * ratio)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def _svg_icon(body: str, px: int, color: str, active: str | None = None) -> QIcon:
    icon = QIcon(_svg_pixmap(body, px, color))
    if active is not None:
        icon.addPixmap(_svg_pixmap(body, px, active), QIcon.Mode.Active)
    return icon


def _clean(text: str) -> str:
    text = _clean_keep_punct(text)
    text = _DISPLAY_STRIP.sub("", text)
    return text.strip()


def _clean_keep_punct(text: str) -> str:
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_CODE.sub(r"\1", text)
    text = _MD_EMPH.sub("", text)
    text = _MD_LEAD.sub("", text)
    return text.strip()


class SpeechText(QWidget):

    talking = Signal(bool)
    finished = Signal()
    chunk_shown = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        _make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._font = QFont("Microsoft YaHei UI")
        self._font.setPixelSize(_FONT_PX)
        self._font.setWeight(QFont.Weight.DemiBold)

        self._anchor: QWidget | None = None
        self._full = ""
        self._shown = 0
        self._lines: list[str] = []
        self._queue: list[str] = []
        self._phase = ""
        self._paced = False
        self._awaiting_advance = False
        self._advance_pending = False
        self._awaiting_start = False
        self._synced = False

        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._reveal)
        self._phase_timer = QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._on_phase)

    def place_below(self, pet: QWidget) -> None:
        self._anchor = pet
        self._reposition()

    def speak(self, chunks: list[str], paced: bool = False) -> None:
        self._stop()
        self._paced = paced
        self._queue = [c for c in (_clean(s) for s in chunks) if c]
        if not self._queue:
            # 去标点后空了退回保留标点版
            self._queue = [c for c in (_clean_keep_punct(s) for s in chunks) if c]
        if not self._queue:
            self.hide()
            self.finished.emit()
            return
        self._next()

    @property
    def is_speaking(self) -> bool:
        return (bool(self._queue) or self._type_timer.isActive()
                or self._phase_timer.isActive() or self._awaiting_advance
                or self._awaiting_start or self._synced)

    def interrupt(self) -> None:
        self._stop()
        self._queue = []
        self.hide()

    def _stop(self) -> None:
        self._type_timer.stop()
        self._phase_timer.stop()
        self._phase = ""
        self._paced = False
        self._awaiting_advance = False
        self._advance_pending = False
        self._awaiting_start = False
        self._synced = False
        self.talking.emit(False)

    def advance(self) -> None:
        """翻到下一句"""
        if not self._paced:
            return
        if self._awaiting_advance:
            self._awaiting_advance = False
            self._do_advance()
        else:
            self._advance_pending = True

    def _do_advance(self) -> None:
        self._type_timer.stop()
        self._synced = False
        self._awaiting_start = False
        if self._queue:
            self._shown = 0
            self._phase = "blank"
            self._phase_timer.start(_BLANK_MS)
            self.update()
        else:
            self.talking.emit(False)
            self._phase = "linger"
            self._phase_timer.start(_LINGER_MS)

    def _next(self) -> None:
        self._set_text(self._queue.pop(0))
        self._shown = 0
        self.show()
        self.raise_()
        self.talking.emit(True)
        if self._paced:
            self._awaiting_start = True
            self._synced = False
            self.update()
            self.chunk_shown.emit(self._full)
        else:
            self._type_timer.start(_TYPE_MS)
            self.update()

    def begin_chunk(self) -> None:
        """音频开始出声时启动本地打字机兜底"""
        if not self._paced or not self._awaiting_start:
            return
        self._awaiting_start = False
        if not self._synced and not self._type_timer.isActive():
            self._type_timer.start(_TYPE_MS)

    def set_progress(self, shown: int) -> None:
        """按音频播放进度显示文字"""
        if not self._paced:
            return
        self._awaiting_start = False
        self._synced = True
        self._type_timer.stop()
        target = max(0, min(int(shown), len(self._full)))
        if target == self._shown and target < len(self._full):
            return
        self._shown = target
        self.update()
        if self._shown >= len(self._full):
            self._on_display_complete()

    def _on_display_complete(self) -> None:
        """一句显示完成后的推进"""
        self._type_timer.stop()
        if self._awaiting_advance:
            return
        if self._advance_pending:
            self._advance_pending = False
            self._do_advance()
        else:
            self._awaiting_advance = True

    def _reveal(self) -> None:
        step = 1 if len(self._full) < _LONG_CHUNK else 2
        self._shown = min(self._shown + step, len(self._full))
        if self._shown >= len(self._full):
            self._type_timer.stop()
            if self._paced:
                self._on_display_complete()
                self.update()
                return
            self.talking.emit(False)
            if self._queue:
                self._phase = "hold"
                self._phase_timer.start(_HOLD_MS)
            else:
                self._phase = "linger"
                self._phase_timer.start(_LINGER_MS)
        self.update()

    def _on_phase(self) -> None:
        if self._phase == "hold":
            self._shown = 0
            self._phase = "blank"
            self._phase_timer.start(_BLANK_MS)
            self.update()
        elif self._phase == "blank":
            self._next()
        elif self._phase == "linger":
            self._phase = ""
            self._paced = False
            self._awaiting_advance = False
            self._awaiting_start = False
            self._synced = False
            self.hide()
            self.finished.emit()

    def _set_text(self, text: str) -> None:
        self._full = text
        self._lines = self._wrap(text)
        self._relayout()

    def _wrap(self, text: str) -> list[str]:
        metrics = QFontMetrics(self._font)
        lines: list[str] = []
        current = ""
        for ch in text:
            if ch == "\n":
                lines.append(current)
                current = ""
                continue
            trial = current + ch
            if current and metrics.horizontalAdvance(trial) > _MAX_INNER:
                lines.append(current)
                current = ch
            else:
                current = trial
        if current or not lines:
            lines.append(current)
        return lines

    def _relayout(self) -> None:
        metrics = QFontMetrics(self._font)
        inner = min(max((metrics.horizontalAdvance(line) for line in self._lines), default=0), _MAX_INNER)
        count = len(self._lines)
        width = inner + 2 * _PAD
        height = count * metrics.height() + (count - 1) * _LINE_GAP + 2 * _PAD
        self.setFixedSize(max(int(width), 1), max(int(height), 1))
        self._reposition()

    def _reposition(self) -> None:
        if self._anchor is None:
            return
        anchor = self._anchor.below_blob()
        x = anchor.x() - self.width() // 2
        y = anchor.y() + _BELOW_GAP
        self.move(x, max(y, 0))

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._shown <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self._font)
        metrics = QFontMetrics(self._font)
        line_h = metrics.height()
        inner = self.width() - 2 * _PAD
        remaining = self._shown
        y = _PAD + metrics.ascent()
        for line in self._lines:
            if remaining <= 0:
                break
            visible = line[:remaining]
            remaining -= len(line)
            if visible:
                x = _PAD + (inner - metrics.horizontalAdvance(line)) / 2
                path = QPainterPath()
                path.addText(x, y, self._font, visible)
                self._stroke(painter, path, _GLOW, _GLOW_W, fill=False)
                self._stroke(painter, path, _OUTLINE, _OUTLINE_W, fill=True)
                painter.setPen(_TEXT)
                painter.drawText(QPointF(x, y), visible)
            y += line_h + _LINE_GAP

    @staticmethod
    def _stroke(painter: QPainter, path: QPainterPath, color: QColor, width: float, fill: bool) -> None:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color if fill else Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class ThoughtBubble(QWidget):

    def __init__(self) -> None:
        super().__init__()
        _make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._font = QFont("Microsoft YaHei UI")
        self._font.setPixelSize(_BUBBLE_FONT_PX)
        self._font.setWeight(QFont.Weight.DemiBold)
        self._text = ""
        self._bubble = (0.0, 0.0, 0.0, 0.0)
        self._t = 0.0
        self._steady = False
        self._steady_left = 0.0
        self._base = QPoint()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def pop(self, text: str, pet: QWidget) -> None:
        """一次性提示 向上飘并淡出"""
        self._steady = False
        self._begin(text, pet, fresh=True)

    def show_step(self, text: str, pet: QWidget) -> None:
        """进度标签 贴头部就地换文字 停更后淡出"""
        fresh = not (self.isVisible() and self._timer.isActive() and self._steady)
        self._steady = True
        self._steady_left = _BUBBLE_STEP_HOLD
        self._begin(text, pet, fresh=fresh)

    def follow(self, pet: QWidget) -> None:
        if self.isVisible():
            self._aim(pet)

    def _aim(self, pet: QWidget) -> None:
        anchor = pet.head_anchor()
        self._base = QPoint(anchor.x() - _BUBBLE_MARGIN, anchor.y() - self.height() + _BUBBLE_MARGIN)

    def _begin(self, text: str, pet: QWidget, fresh: bool) -> None:
        self._text = text[:48]
        self._relayout()
        self._aim(pet)
        if fresh:
            self._t = 0.0
            self.move(self._base)
            self.setWindowOpacity(0.0)
            self.show()
            self.raise_()
        if not self._timer.isActive():
            self._timer.start(_BUBBLE_FPS_MS)
        self.update()

    def _tick(self) -> None:
        dt = _BUBBLE_FPS_MS / 1000.0
        self._t += dt
        if self._steady:
            self._steady_left -= dt
            if self._t < 0.15:
                opacity = self._t / 0.15
            elif self._steady_left <= 0.0:
                opacity = 1.0 + self._steady_left / 0.3
            else:
                opacity = 1.0
            if opacity <= 0.0:
                self._timer.stop()
                self.hide()
                return
            self.move(self._base)
            self.setWindowOpacity(opacity)
        else:
            p = self._t / _BUBBLE_DUR
            if p >= 1.0:
                self._timer.stop()
                self.hide()
                return
            rise = _BUBBLE_RISE * (1 - (1 - p) ** 3)
            self.move(self._base.x(), int(self._base.y() - rise))
            self.setWindowOpacity(self._opacity(p))
        self.update()

    @staticmethod
    def _opacity(p: float) -> float:
        if p < 0.15:
            return p / 0.15
        if p > 0.7:
            return max(0.0, (1.0 - p) / 0.3)
        return 1.0

    def _relayout(self) -> None:
        metrics = QFontMetrics(self._font)
        bound = metrics.boundingRect(0, 0, _BUBBLE_MAXW, 10000, _BUBBLE_TEXT_FLAGS, self._text)
        inner_w = max(1, bound.width())
        inner_h = max(metrics.height(), bound.height())
        bw = inner_w + 2 * _BUBBLE_PAD
        bh = inner_h + 2 * _BUBBLE_PAD
        self._bubble = (float(_BUBBLE_MARGIN), float(_BUBBLE_MARGIN), bw, bh)
        self.setFixedSize(int(bw + 2 * _BUBBLE_MARGIN), int(bh + _BUBBLE_TRAIL_H + 2 * _BUBBLE_MARGIN))

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, bw, bh = self._bubble
        painter.setPen(QPen(_BUBBLE_EDGE, 1.2))
        painter.setBrush(_BUBBLE_BG)
        painter.drawRoundedRect(QRectF(x, y, bw, bh), bh * 0.45, bh * 0.45)
        for cx, cy, r in (
            (x + bw * 0.22, y + bh + 6, 5.0),
            (x + bw * 0.08, y + bh + 14, 3.0),
        ):
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setPen(_BUBBLE_INK)
        painter.setFont(self._font)
        painter.drawText(QRectF(x, y, bw, bh), _BUBBLE_TEXT_FLAGS, self._text)


def _sample_chars(source: str) -> str:
    chars = [c for c in source if not c.isspace()]
    if len(chars) < 2:
        return random.choice(_THINK_FALLBACK)
    n = random.randint(2, 3)
    start = random.randint(0, max(0, len(chars) - n))
    return "".join(chars[start : start + n])


def _think_opacity(frac: float) -> float:
    if frac < 0.18:
        return frac / 0.18
    if frac > 0.62:
        return max(0.0, (1.0 - frac) / 0.38)
    return 1.0


@dataclass
class _Particle:
    text: str
    cx: float
    drift_amp: float
    drift_freq: float
    life: float
    age: float = 0.0


class ThoughtBubbles(QWidget):

    def __init__(self) -> None:
        super().__init__()
        _make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(_THINK_W, _THINK_H)
        self._font = QFont("Microsoft YaHei UI")
        self._font.setPixelSize(_THINK_FONT_PX)
        self._font.setWeight(QFont.Weight.DemiBold)
        self._source = ""
        self._active = False
        self._particles: list[_Particle] = []
        self._spawn_in = 0.0
        self._last = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def feed(self, text: str) -> None:
        if text:
            self._source = (self._source + text)[-_THINK_SOURCE_MAX:]

    def start(self, pet: QWidget) -> None:
        self._source = ""
        self._active = True
        self._spawn_in = 0.0
        self.follow(pet)
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._last = time.perf_counter()
            self._timer.start(_BUBBLE_FPS_MS)

    def stop(self) -> None:
        self._active = False

    def follow(self, pet: QWidget) -> None:
        head = pet.head_top()
        self.move(head.x() - self.width() // 2, head.y() - self.height())

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        for particle in self._particles:
            particle.age += dt
        self._particles = [p for p in self._particles if p.age < p.life]
        if self._active and len(self._particles) < _THINK_MAX:
            self._spawn_in -= dt
            if self._spawn_in <= 0.0:
                self._spawn()
                self._spawn_in = random.uniform(*_THINK_SPAWN)
        if not self._active and not self._particles:
            self._timer.stop()
            self.hide()
            return
        self.update()

    def _spawn(self) -> None:
        self._particles.append(
            _Particle(
                text=_sample_chars(self._source),
                cx=self.width() / 2 + random.uniform(-33, 33),
                drift_amp=random.uniform(0.5, 1.0) * _THINK_DRIFT,
                drift_freq=random.uniform(1.6, 2.8),
                life=random.uniform(*_THINK_LIFE),
            )
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)
        metrics = QFontMetrics(self._font)
        base_y = float(self.height() - 8)
        for particle in self._particles:
            frac = particle.age / particle.life
            rise = _THINK_RISE * (1 - (1 - frac) ** 2)
            cx = particle.cx + math.sin(particle.age * particle.drift_freq) * particle.drift_amp
            cy = base_y - rise
            bw = metrics.horizontalAdvance(particle.text) + 2 * _THINK_PAD
            bh = metrics.height() + _THINK_PAD
            rect = QRectF(cx - bw / 2, cy - bh / 2, bw, bh)
            painter.setOpacity(_think_opacity(frac))
            painter.setPen(QPen(_THINK_EDGE, 1.0))
            painter.setBrush(_THINK_BG)
            painter.drawRoundedRect(rect, bh / 2, bh / 2)
            painter.setPen(_THINK_INK)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, particle.text)
        painter.setOpacity(1.0)


def _encode_b64(img: QImage, fmt: str, quality: int) -> str:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if quality >= 0:
        img.save(buf, fmt, quality)
    else:
        img.save(buf, fmt)
    data = base64.b64encode(bytes(buf.data())).decode("ascii")
    buf.close()
    return data


def _image_to_data_url(image: QImage) -> str:
    """图片转data url 超边长先缩 png过大退jpeg降质"""
    img = image
    if img.width() > _IMG_MAX_SIDE or img.height() > _IMG_MAX_SIDE:
        img = img.scaled(
            _IMG_MAX_SIDE, _IMG_MAX_SIDE,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
    png = _encode_b64(img, "PNG", -1)
    if len(png) <= _DATAURL_MAX:
        return f"data:image/png;base64,{png}"
    jpg = ""
    for quality in (85, 70, 55, 40):
        jpg = _encode_b64(img, "JPEG", quality)
        if len(jpg) <= _DATAURL_MAX:
            break
    return f"data:image/jpeg;base64,{jpg}"


def _elide(name: str) -> str:
    if len(name) <= _FILE_NAME_MAX:
        return name
    stem, _, ext = name.rpartition(".")
    keep = max(_FILE_NAME_MAX - len(ext) - 2, 1)
    return f"{(stem or name)[:keep]}…{('.' + ext) if ext else ''}"


class _Editor(QTextEdit):
    """多行文本域 自适应高度 支持粘贴拖入图片文件"""

    submit = Signal()
    escape = Signal()
    image_in = Signal(QImage)
    files_in = Signal(list)
    grew = Signal()
    focus_changed = Signal(bool)

    _MIN_H = 30
    _MAX_H = 132

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("editor")
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.setAcceptDrops(True)
        self.setFixedHeight(self._MIN_H)
        # 隔一拍再调高度 断开contentsChanged递归
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_height)
        self.document().contentsChanged.connect(self._schedule_resize)

    def _schedule_resize(self) -> None:
        self._resize_timer.start(0)

    def _apply_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        h = int(doc.size().height()) + 2 * int(self.frameWidth()) + 8
        h = max(self._MIN_H, min(h, self._MAX_H))
        if h != self.height():
            self.setFixedHeight(h)
            self.grew.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.escape.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                super().keyPressEvent(event)
            else:
                self.submit.emit()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def insertFromMimeData(self, source) -> None:
        if not self._consume_mime(source):
            super().insertFromMimeData(source)

    def _consume_mime(self, source) -> bool:
        if source is None:
            return False
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                self.image_in.emit(image)
                return True
        if source.hasUrls():
            paths = [u.toLocalFile() for u in source.urls() if u.isLocalFile()]
            paths = [p for p in paths if p]
            if paths:
                self.files_in.emit(paths)
                return True
        return False

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasImage() or md.hasUrls() or md.hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self._consume_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class _Chip(QFrame):
    """附件芯片"""

    removed = Signal(object)

    def __init__(self, item: dict) -> None:
        super().__init__()
        self.setObjectName("chip")
        self._item = item
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 4, 4)
        row.setSpacing(5)
        icon = QLabel()
        thumb = item.get("thumb")
        if item["kind"] == "image" and isinstance(thumb, QPixmap):
            icon.setPixmap(thumb)
            icon.setFixedSize(thumb.size())
        else:
            icon.setPixmap(_svg_pixmap(_SVG_FILE, 15, "#8a7d95"))
            icon.setFixedSize(15, 15)
        row.addWidget(icon)
        row.addWidget(QLabel(_elide(item.get("name", "?"))))
        delete = QPushButton("×")
        delete.setObjectName("chipdel")
        delete.setFixedSize(16, 16)
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(lambda: self.removed.emit(self._item))
        row.addWidget(delete)


class InputBox(QWidget):
    """点击桌宠弹出的输入框"""

    submitted = Signal(str, object)

    def __init__(self) -> None:
        super().__init__()
        _make_floating(self)
        self.setFixedWidth(_INPUT_W)
        self._attachments: list[dict] = []
        self._paste_seq = 0
        self._home = QPoint()
        self._hiding = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame()
        self._card.setObjectName("card")
        self._card.setStyleSheet(_PANEL_STYLE)
        outer.addWidget(self._card)

        col = QVBoxLayout(self._card)
        col.setContentsMargins(14, 10, 10, 10)
        col.setSpacing(8)

        self._strip = QWidget()
        self._strip_row = QHBoxLayout(self._strip)
        self._strip_row.setContentsMargins(0, 0, 0, 0)
        self._strip_row.setSpacing(6)
        self._strip_row.addStretch(1)
        self._strip.hide()
        col.addWidget(self._strip)

        self._editor = _Editor()
        self._editor.setPlaceholderText(i18n.t("input_placeholder"))
        pal = self._editor.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(176, 158, 172))
        self._editor.setPalette(pal)
        self._editor.submit.connect(self._emit)
        self._editor.escape.connect(self.fade_out)
        self._editor.image_in.connect(self._add_image)
        self._editor.files_in.connect(self._add_files)
        self._editor.grew.connect(self._sync_geometry)
        self._editor.textChanged.connect(self._update_send)
        self._editor.focus_changed.connect(self._on_focus)
        col.addWidget(self._editor)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(6)
        self._btn_img = self._tool_btn(_SVG_IMAGE, i18n.t("input_add_image"), self._pick_images)
        self._btn_file = self._tool_btn(_SVG_CLIP, i18n.t("input_add_file"), self._pick_files)
        bar.addWidget(self._btn_img)
        bar.addWidget(self._btn_file)
        bar.addStretch(1)
        self._hint = QLabel(i18n.t("input_hint"), objectName="hint")
        bar.addWidget(self._hint)
        self._send = QPushButton()
        self._send.setObjectName("send")
        self._send.setFixedSize(34, 30)
        self._send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send.setToolTip(i18n.t("input_send"))
        self._send.setIcon(_svg_icon(_SVG_SEND, 16, "#ffffff"))
        self._send.setIconSize(QSize(16, 16))
        self._send.setEnabled(False)
        self._send.clicked.connect(self._emit)
        bar.addWidget(self._send)
        col.addLayout(bar)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(_INPUT_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._on_fade_finished)
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(_INPUT_FADE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.adjustSize()

    def _tool_btn(self, svg_body: str, tip: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("tool")
        btn.setFixedSize(28, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tip)
        btn.setIcon(_svg_icon(svg_body, 17, "#9a8aa0", active="#6a59f5"))
        btn.setIconSize(QSize(17, 17))
        btn.clicked.connect(slot)
        return btn

    def setText(self, text: str) -> None:
        self._editor.setPlainText(text)
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._editor.setTextCursor(cursor)

    def text(self) -> str:
        return self._editor.toPlainText()

    def setPlaceholderText(self, text: str) -> None:
        self._editor.setPlaceholderText(text)

    def setFocus(self, reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason) -> None:
        self._editor.setFocus(reason)

    def clear(self) -> None:
        self._editor.clear()
        self._attachments.clear()
        self._refresh_strip()

    def _has_image(self, data_url: str) -> bool:
        return any(a.get("data_url") == data_url for a in self._attachments)

    def _add_image(self, image: QImage) -> None:
        if len(self._attachments) >= _ATTACH_MAX or image.isNull():
            return
        data_url = _image_to_data_url(image)
        if self._has_image(data_url):
            return
        self._paste_seq += 1
        self._attachments.append({
            "kind": "image", "data_url": data_url,
            "name": f"{i18n.t('att_pasted_image')} {self._paste_seq}", "thumb": self._thumb(image),
        })
        self._refresh_strip()

    def _add_files(self, paths: list) -> None:
        for path in paths:
            if len(self._attachments) >= _ATTACH_MAX:
                break
            p = Path(path)
            if not p.is_file():
                continue
            if p.suffix.lower() in _IMAGE_EXT:
                image = QImage(str(p))
                if not image.isNull():
                    data_url = _image_to_data_url(image)
                    if self._has_image(data_url):  # 按data_url去重
                        continue
                    self._attachments.append({
                        "kind": "image", "data_url": data_url,
                        "name": p.name, "thumb": self._thumb(image),
                    })
                    continue
            if any(a.get("kind") == "file" and a.get("path") == str(p) for a in self._attachments):
                continue
            self._attachments.append({"kind": "file", "path": str(p), "name": p.name})
        self._refresh_strip()

    @staticmethod
    def _thumb(image: QImage) -> QPixmap:
        return QPixmap.fromImage(image).scaled(
            34, 34, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _remove_attachment(self, item: dict) -> None:
        try:
            self._attachments.remove(item)
        except ValueError:
            pass
        self._refresh_strip()

    def _refresh_strip(self) -> None:
        while self._strip_row.count() > 1:
            taken = self._strip_row.takeAt(0)
            w = taken.widget()
            if w is not None:
                w.deleteLater()
        for item in self._attachments:
            chip = _Chip(item)
            chip.removed.connect(self._remove_attachment)
            self._strip_row.insertWidget(self._strip_row.count() - 1, chip)
        self._strip.setVisible(bool(self._attachments))
        self._update_send()
        self._sync_geometry()

    def _update_send(self) -> None:
        self._send.setEnabled(bool(self._attachments) or bool(self._editor.toPlainText().strip()))

    def _on_focus(self, on: bool) -> None:
        self._card.setProperty("focused", "true" if on else "false")
        self._card.style().unpolish(self._card)
        self._card.style().polish(self._card)

    def _pick_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, i18n.t("input_img_dialog"), "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.jfif)",
        )
        if paths:
            self._add_files(paths)
        self._editor.setFocus()

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, i18n.t("input_file_dialog"), "")
        if paths:
            self._add_files(paths)
        self._editor.setFocus()

    def _emit(self) -> None:
        text = self._editor.toPlainText().strip()
        if not text and not self._attachments:
            return
        # thumb只给芯片显示 往下游传之前剔掉
        payload = [
            {k: v for k, v in item.items() if k != "thumb"}
            for item in self._attachments
        ]
        self._editor.clear()
        self._attachments.clear()
        self._refresh_strip()
        self.submitted.emit(text, payload)

    def _sync_geometry(self) -> None:
        # 隔一拍等layout跑完再量尺寸
        QTimer.singleShot(0, self._apply_geometry)

    def _apply_geometry(self) -> None:
        self.layout().activate()
        self.adjustSize()
        if not self._home.isNull() and not self._hiding:
            self.move(self._home)

    def place_below(self, pet: QWidget) -> None:
        self.adjustSize()
        anchor = pet.below_blob()
        self._home = QPoint(anchor.x() - self.width() // 2, anchor.y() + _INPUT_GAP)
        if not self._hiding:
            self.move(self._home)

    def popup(self, pet: QWidget) -> None:
        self._editor.setPlaceholderText(i18n.t("input_placeholder"))
        self.place_below(pet)
        self._hiding = False
        self.setWindowOpacity(0.0)
        self.move(self._home.x(), self._home.y() + _INPUT_SLIDE)
        self.show()
        self.raise_()
        self.activateWindow()
        self._editor.setFocus()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._slide.stop()
        self._slide.setEndValue(self._home)
        self._slide.start()

    def fade_out(self) -> None:
        if not self.isVisible() or self._hiding:
            return
        self._hiding = True
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade_finished(self) -> None:
        if self._hiding:
            self.hide()
            self._hiding = False
