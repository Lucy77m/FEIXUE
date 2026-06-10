# author: bdth
# email: 2074055628@qq.com
# 桌宠媒体展示窗 图片渲成拍立得 动图渲成复古电视机 带弹出收起动画和点击保存

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
    """等比缩到框内 只缩不放"""
    scale = min(max_w / w, max_h / h, 1.0)
    return max(1, round(w * scale)), max(1, round(h * scale))


class MediaFrame(QWidget):
    """图片渲成拍立得 动图渲成电视机的悬浮展示窗"""

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._font = QFont("Microsoft YaHei UI")
        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None
        self._chrome: QPixmap | None = None
        self._src_path = ""
        self._screen_rect = QRectF()
        self._scale = 0.0
        self._target = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def show_image(self, path: str, caption: str, pet: QWidget, screen) -> None:
        """渲成拍立得弹出来"""
        src = QPixmap(path)
        if src.isNull():
            return
        self._teardown_movie()  # 先停掉还在放的电视
        self._src_path = path
        self._pixmap = self._render_polaroid(src, caption)
        self._begin(self._pixmap.size(), pet, screen)

    def play_gif(self, path: str, caption: str, pet: QWidget, screen) -> None:
        """动图塞进电视机屏幕循环放"""
        movie = QMovie(path)
        if not movie.isValid():
            return
        self._teardown_movie()
        self._src_path = path
        movie.jumpToFrame(0)  # 跳到首帧量尺寸
        first = movie.currentPixmap()
        fw = first.width() or _TV_MAX_W  # 首帧报 0 就退回上限
        fh = first.height() or _TV_MAX_H
        sw, sh = _fit(fw, fh, _TV_MAX_W, _TV_MAX_H)
        movie.setScaledSize(QSize(sw, sh))
        self._pixmap = None  # 切到电视模式 清掉拍立得
        self._movie = movie
        self._chrome = self._render_tv(sw, sh, caption)
        movie.frameChanged.connect(self._on_frame)
        movie.start()
        self._begin(self._chrome.size(), pet, screen)

    def dismiss(self) -> None:
        """起收起动画"""
        if not self.isVisible() and self._scale <= 0.001:
            return
        self._target = 0.0
        if not self._timer.isActive():
            self._timer.start(_FPS_MS)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 动画途中不收点击
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._target <= 0.0 or self._scale < 0.95:
            return
        pos = event.position()
        cx, cy = self.width() - 21.0, 21.0
        # 右上角叉的判定圈 圈外算保存
        if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= 15.0 ** 2:
            self.dismiss()
        else:
            self._save()

    def _save(self) -> None:
        """直接 copy 源文件另存"""
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
            except OSError as exc:
                audit.system("媒体保存失败", target=target, error=f"{type(exc).__name__}: {exc}")

    def _on_frame(self, _index: int) -> None:
        self.update()

    def _teardown_movie(self) -> None:
        """停掉 movie 并断信号"""
        if self._movie is not None:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_frame)
            except (RuntimeError, TypeError):
                pass
            self._movie = None
        self._chrome = None

    def _begin(self, size: QSize, pet: QWidget, screen) -> None:
        """定尺寸 贴位 起弹出动画"""
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
        # 每帧推 scale 朝 target 走 到头停表
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
        """桌宠拖动时跟着挪"""
        if self.isVisible():
            self._place(pet, screen)

    def _place(self, pet: QWidget, screen) -> None:
        place_beside_pet(self, pet, screen, prefer="right")

    def _render_polaroid(self, src: QPixmap, caption: str) -> QPixmap:
        """离屏画拍立得卡片和红图钉"""
        iw, ih = _fit(src.width(), src.height(), _IMG_MAX_W, _IMG_MAX_H)
        photo_w = iw + 2 * _BORDER
        photo_h = ih + _BORDER + _CAPTION_H  # 下边留白写字
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
        # 三层黑块叠投影
        for dy, alpha in ((4, 40), (9, 24), (15, 12)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(card.translated(0, dy), 4, 4)
        painter.setBrush(QColor(250, 249, 245))  # 相纸底色
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
        painter.resetTransform()  # 撤掉旋转 图钉要画正

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
        """画电视机壳 屏幕区留空"""
        body_w = screen_w + 2 * _TV_EDGE
        body_h = screen_h + 2 * _TV_EDGE + _TV_FOOT  # 底下一条放指示灯台标旋钮
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
        painter.drawRoundedRect(screen.adjusted(-3, -3, 3, 3), 8, 8)  # 显像管黑框
        self._screen_rect = screen  # 存屏幕区给 paintEvent 贴帧用

        foot = QRectF(screen.left(), screen.bottom() + 8, screen_w, _TV_FOOT - 10)
        painter.setBrush(QColor(120, 232, 120))
        painter.drawEllipse(QRectF(foot.left() + 2, foot.center().y() - 3, 6, 6))  # 开机绿灯
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
        # 弹出带回弹 收起用平方曲线
        display = self._scale * self._scale if self._target == 0.0 else ease_out_back(self._scale)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.translate(w / 2, h / 2)  # 绕中心缩放
        painter.scale(display, display)
        painter.translate(-w / 2, -h / 2)

        # 拍立得整张贴 电视先机壳再贴当前帧
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        elif self._movie is not None and self._chrome is not None:
            painter.drawPixmap(0, 0, self._chrome)
            frame = self._movie.currentPixmap()
            if not frame.isNull():
                painter.save()
                clip = QPainterPath()
                clip.addRoundedRect(self._screen_rect, 6, 6)  # 裁成圆角
                painter.setClipPath(clip)
                painter.drawPixmap(self._screen_rect.topLeft(), frame)
                painter.restore()

        # 关闭按钮动画过半才淡入 不跟缩放走
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
