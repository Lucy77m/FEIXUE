# 听写浮条 说话时屏幕下方实时显示识别文字 麦克风圆点呼吸

from __future__ import annotations

import math
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from desktop_pet import i18n
from desktop_pet.pet.fx import make_floating as _make_floating

_FONT_PX = 15
_PAD_H = 18
_PAD_V = 12
_MIN_W = 220
_MAX_W = 520
_DOT_R = 5.0
_DOT_GAP = 12
_BOTTOM_GAP = 96
_BG = QColor(255, 255, 255, 242)
_INK = QColor(44, 46, 54)
_HINT_INK = QColor(150, 153, 165)
_EDGE = QColor(0, 0, 0, 38)
_DOT = QColor(225, 85, 90)
_FLASH_MS = 450


class HearBar(QWidget):
    """听写浮条 屏幕底部居中 跟随识别文字自动变宽"""

    def __init__(self) -> None:
        super().__init__()
        _make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._font = QFont("Microsoft YaHei UI")
        self._font.setPixelSize(_FONT_PX)
        self._font.setWeight(QFont.Weight.DemiBold)
        self._font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self._font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self._text = ""
        self._remaining = -1.0
        self._t0 = 0.0
        self._pulse = QTimer(self)
        self._pulse.timeout.connect(self.update)
        self._flash = QTimer(self)
        self._flash.setSingleShot(True)
        self._flash.timeout.connect(self.hide)

    def begin(self) -> None:
        """进入聆听 文字清空 圆点开始呼吸"""
        self._flash.stop()
        self._text = ""
        self._remaining = -1.0
        self._t0 = time.monotonic()
        self._relayout()
        self.show()
        self.raise_()
        self._pulse.start(33)

    def set_text(self, text: str) -> None:
        if not self.isVisible():
            return
        self._text = text or ""
        self._relayout()

    def set_remaining(self, sec: float) -> None:
        if self.isVisible():
            self._remaining = sec

    def finish(self, text: str) -> None:
        """定稿 亮一下随即收起"""
        self._text = text or ""
        self._remaining = -1.0
        self._relayout()
        self._pulse.stop()
        self.update()
        self._flash.start(_FLASH_MS)

    def dismiss(self) -> None:
        self._pulse.stop()
        self._flash.stop()
        self.hide()

    def _relayout(self) -> None:
        from PySide6.QtGui import QCursor
        fm = QFontMetrics(self._font)
        shown = self._text or i18n.t("hear_listening")
        text_w = min(fm.horizontalAdvance(shown) + 8, _MAX_W)
        w = max(_MIN_W, text_w + _PAD_H * 2 + int(_DOT_R * 2) + _DOT_GAP)
        h = fm.height() + _PAD_V * 2
        # 说话的人在哪块屏 浮条就贴哪块屏 找不到退回主屏
        scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        screen = scr.availableGeometry()
        self.resize(w, h)
        self.move(screen.center().x() - w // 2, screen.bottom() - h - _BOTTOM_GAP)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(_EDGE)
        p.setBrush(_BG)
        p.drawPath(path)
        # 呼吸圆点
        k = 0.55 + 0.45 * math.sin((time.monotonic() - self._t0) * 4.2)
        dot = QColor(_DOT)
        dot.setAlphaF(0.35 + 0.65 * k)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dot)
        cx = _PAD_H + _DOT_R
        p.drawEllipse(QRectF(cx - _DOT_R, r.center().y() - _DOT_R, _DOT_R * 2, _DOT_R * 2))
        # 倒计时 最后10秒在右端显示
        right_w = 0
        if self._remaining >= 0.0:
            cd = f"{int(self._remaining + 0.999)}s"
            p.setFont(self._font)
            fm = QFontMetrics(self._font)
            right_w = fm.horizontalAdvance(cd) + 10
            p.setPen(_DOT if self._remaining <= 3.0 else _HINT_INK)
            p.drawText(QRectF(0, 0, self.width() - _PAD_H, self.height()),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), cd)
        # 文字 没识别出来时放提示灰
        p.setFont(self._font)
        p.setPen(_INK if self._text else _HINT_INK)
        shown = self._text or i18n.t("hear_listening")
        fm = QFontMetrics(self._font)
        shown = fm.elidedText(shown, Qt.TextElideMode.ElideLeft,
                              self.width() - _PAD_H * 2 - int(_DOT_R * 2) - _DOT_GAP - right_w)
        p.drawText(QRectF(cx + _DOT_R + _DOT_GAP, 0, self.width(), self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter), shown)
