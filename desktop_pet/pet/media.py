# author: bdth
# email: 2074055628@qq.com
# 桌宠媒体展示窗:把图片渲染成拍立得、把动图渲染成复古电视机,带弹出/收起动画与点击保存

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QMovie,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFileDialog, QWidget

from desktop_pet import i18n
from desktop_pet.audit import audit
from desktop_pet.pet.fx import ease_out_back, make_floating, place_beside_pet

_IMG_MAX_W, _IMG_MAX_H = 300, 220
_BORDER = 14
_CAPTION_H = 38
_TILT = -3.2
_MARGIN = 38

_TV_MAX_W, _TV_MAX_H = 300, 220
_TV_EDGE = 18
_TV_FOOT = 28

_FPS_MS = 1000 // 60
_PRESENT_DUR = 0.42
_DISMISS_DUR = 0.28


def _fit(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int]:
    scale = min(max_w / w, max_h / h, 1.0)
    return max(1, round(w * scale)), max(1, round(h * scale))


class MediaFrame(QWidget):

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._font = QFont("Microsoft YaHei UI")
        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None
        self._chrome: QPixmap | None = None
        self._src_path = ""  # 原始图片/动图路径，供点击保存
        self._screen_rect = QRectF()
        self._scale = 0.0
        self._target = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def show_image(self, path: str, caption: str, pet: QWidget, screen) -> None:
        src = QPixmap(path)
        if src.isNull():
            return
        self._teardown_movie()
        self._src_path = path
        self._pixmap = self._render_polaroid(src, caption)
        self._begin(self._pixmap.size(), pet, screen)

    def play_gif(self, path: str, caption: str, pet: QWidget, screen) -> None:
        movie = QMovie(path)
        if not movie.isValid():
            return
        self._teardown_movie()
        self._src_path = path
        movie.jumpToFrame(0)
        first = movie.currentPixmap()
        fw = first.width() or _TV_MAX_W
        fh = first.height() or _TV_MAX_H
        sw, sh = _fit(fw, fh, _TV_MAX_W, _TV_MAX_H)
        movie.setScaledSize(QSize(sw, sh))
        self._pixmap = None
        self._movie = movie
        self._chrome = self._render_tv(sw, sh, caption)
        movie.frameChanged.connect(self._on_frame)
        movie.start()
        self._begin(self._chrome.size(), pet, screen)

    def dismiss(self) -> None:
        if not self.isVisible() and self._scale <= 0.001:
            return
        self._target = 0.0
        if not self._timer.isActive():
            self._timer.start(_FPS_MS)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._target <= 0.0 or self._scale < 0.95:
            return  # present 动画未完成 / 正在收起：× 按钮(scale>0.55 才画)还没稳定显示，先别响应点击
        pos = event.position()
        # 命中右上角 × 才关闭(坐标与 paintEvent 画的一致，半径留容差);否则点的是图框主体 → 保存
        cx, cy = self.width() - 21.0, 21.0
        if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= 15.0 ** 2:
            self.dismiss()
        else:
            self._save()

    def _save(self) -> None:
        if not self._src_path or not os.path.exists(self._src_path):
            return
        suffix = Path(self._src_path).suffix or ".png"
        downloads = Path.home() / "Downloads"
        default_dir = downloads if downloads.is_dir() else Path.home()
        default = default_dir / ("mochi_media" + suffix)
        target, _ = QFileDialog.getSaveFileName(
            self, i18n.t("media_save_title"), str(default), i18n.t("media_save_filter").format(suffix=suffix)
        )
        if target:
            try:
                shutil.copy(self._src_path, target)
            except OSError as exc:  # 失败别静默：至少写审计，用户也好排查
                audit.system("媒体保存失败", target=target, error=f"{type(exc).__name__}: {exc}")

    def _on_frame(self, _index: int) -> None:
        self.update()

    def _teardown_movie(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_frame)
            except (RuntimeError, TypeError):
                pass
            self._movie = None
        self._chrome = None

    def _begin(self, size: QSize, pet: QWidget, screen) -> None:
        was_visible = self.isVisible()
        self.setFixedSize(size)
        self._place(pet, screen)
        self._target = 1.0
        self._scale = self._scale if was_visible else 0.0
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start(_FPS_MS)
        self.update()

    def _tick(self) -> None:
        dt = _FPS_MS / 1000.0
        if self._target > 0.0:
            self._scale = min(1.0, self._scale + dt / _PRESENT_DUR)
        else:
            self._scale = max(0.0, self._scale - dt / _DISMISS_DUR)
        if self._target == 0.0 and self._scale <= 0.001:
            self._timer.stop()
            self._teardown_movie()
            self.hide()
        elif self._target > 0.0 and self._scale >= 1.0:
            self._timer.stop()
        self.update()

    def follow(self, pet: QWidget, screen) -> None:
        if self.isVisible():
            self._place(pet, screen)

    def _place(self, pet: QWidget, screen) -> None:
        place_beside_pet(self, pet, screen, prefer="right")

    def _render_polaroid(self, src: QPixmap, caption: str) -> QPixmap:
        iw, ih = _fit(src.width(), src.height(), _IMG_MAX_W, _IMG_MAX_H)
        photo_w = iw + 2 * _BORDER
        photo_h = ih + _BORDER + _CAPTION_H
        cw = photo_w + 2 * _MARGIN
        ch = photo_h + 2 * _MARGIN
        canvas = QPixmap(cw, ch)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.translate(cw / 2, ch / 2)
        painter.rotate(_TILT)
        card = QRectF(-photo_w / 2, -photo_h / 2, photo_w, photo_h)
        painter.setPen(Qt.PenStyle.NoPen)
        for dy, alpha in ((4, 40), (9, 24), (15, 12)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(card.translated(0, dy), 4, 4)
        painter.setBrush(QColor(250, 249, 245))
        painter.drawRoundedRect(card, 4, 4)
        image = src.scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(QPointF(-photo_w / 2 + _BORDER, -photo_h / 2 + _BORDER), image)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 28), 1))
        painter.drawRect(QRectF(-photo_w / 2 + _BORDER, -photo_h / 2 + _BORDER, iw, ih))
        if caption:
            painter.setPen(QColor(70, 70, 76))
            font = QFont(self._font)
            font.setPixelSize(13)
            painter.setFont(font)
            cap = QRectF(-photo_w / 2 + 6, photo_h / 2 - _CAPTION_H, photo_w - 12, _CAPTION_H)
            painter.drawText(cap, int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap), caption[:42])
        painter.resetTransform()

        cx = cw / 2
        pin = QRectF(cx - 7, _MARGIN - 4, 14, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 55))
        painter.drawEllipse(pin.translated(1, 2))
        dome = QRadialGradient(pin.center() + QPointF(-2, -2), 9)
        dome.setColorAt(0.0, QColor(236, 96, 96))
        dome.setColorAt(1.0, QColor(162, 28, 28))
        painter.setBrush(dome)
        painter.drawEllipse(pin)
        painter.setBrush(QColor(255, 255, 255, 170))
        painter.drawEllipse(QRectF(cx - 4, _MARGIN - 2, 4, 4))
        painter.end()
        return canvas

    def _render_tv(self, screen_w: int, screen_h: int, caption: str) -> QPixmap:
        body_w = screen_w + 2 * _TV_EDGE
        body_h = screen_h + 2 * _TV_EDGE + _TV_FOOT
        cw = body_w + 2 * _MARGIN
        ch = body_h + 2 * _MARGIN
        chrome = QPixmap(cw, ch)
        chrome.fill(Qt.GlobalColor.transparent)
        painter = QPainter(chrome)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = float(_MARGIN), float(_MARGIN)
        body = QRectF(ox, oy, body_w, body_h)

        painter.setPen(Qt.PenStyle.NoPen)
        for dy, alpha in ((4, 46), (10, 26), (16, 12)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(body.translated(0, dy), 16, 16)
        shell = QLinearGradient(0, body.top(), 0, body.bottom())
        shell.setColorAt(0.0, QColor(78, 73, 68))
        shell.setColorAt(1.0, QColor(44, 41, 38))
        painter.setPen(QPen(QColor(26, 24, 22), 1.5))
        painter.setBrush(shell)
        painter.drawRoundedRect(body, 16, 16)
        painter.setPen(QPen(QColor(255, 248, 236, 42), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body.adjusted(1.5, 1.5, -1.5, -1.5), 15, 15)

        screen = QRectF(ox + _TV_EDGE, oy + _TV_EDGE, screen_w, screen_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 12, 14))
        painter.drawRoundedRect(screen.adjusted(-3, -3, 3, 3), 8, 8)
        self._screen_rect = screen

        foot = QRectF(screen.left(), screen.bottom() + 8, screen_w, _TV_FOOT - 10)
        painter.setBrush(QColor(120, 232, 120))
        painter.drawEllipse(QRectF(foot.left() + 2, foot.center().y() - 3, 6, 6))
        if caption:
            painter.setPen(QColor(214, 209, 202))
            font = QFont(self._font)
            font.setPixelSize(12)
            painter.setFont(font)
            text_area = QRectF(foot.left() + 14, foot.top(), foot.width() - 76, foot.height())
            painter.drawText(text_area, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), caption[:24])
        for kx in (foot.right() - 16, foot.right() - 38):
            knob = QRectF(kx, foot.center().y() - 7, 14, 14)
            grad = QRadialGradient(knob.center() + QPointF(-2, -2), 8)
            grad.setColorAt(0.0, QColor(152, 147, 140))
            grad.setColorAt(1.0, QColor(80, 76, 72))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(knob)
        painter.end()
        return chrome

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._scale <= 0.001:
            return
        display = self._scale * self._scale if self._target == 0.0 else ease_out_back(self._scale)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.translate(w / 2, h / 2)
        painter.scale(display, display)
        painter.translate(-w / 2, -h / 2)

        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        elif self._movie is not None and self._chrome is not None:
            painter.drawPixmap(0, 0, self._chrome)
            frame = self._movie.currentPixmap()
            if not frame.isNull():
                painter.save()
                clip = QPainterPath()
                clip.addRoundedRect(self._screen_rect, 6, 6)
                painter.setClipPath(clip)
                painter.drawPixmap(self._screen_rect.topLeft(), frame)
                painter.restore()

        if self._scale > 0.55:
            painter.resetTransform()
            alpha = int(235 * min(1.0, (self._scale - 0.55) / 0.45))
            cx, cy, radius = self.width() - 21.0, 21.0, 11.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(38, 38, 42, int(alpha * 0.82)))
            painter.drawEllipse(QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius))
            painter.setPen(QPen(QColor(242, 242, 246, alpha), 2))
            arm = 4.0
            painter.drawLine(QPointF(cx - arm, cy - arm), QPointF(cx + arm, cy + arm))
            painter.drawLine(QPointF(cx - arm, cy + arm), QPointF(cx + arm, cy - arm))
