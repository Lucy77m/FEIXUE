# qpainter矢量画绯雪的脸 生成多尺寸应用图标

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

_BADGE_TOP = QColor(38, 36, 64)
_BADGE_BOT = QColor(12, 12, 22)
_VIOLET = QColor(167, 139, 250)
_CYAN = QColor(34, 211, 238)
_INK = QColor(34, 32, 46)
_FEIXUE_TOP = QColor(252, 252, 254)
_FEIXUE_BOT = QColor(226, 230, 240)
_BLUSH = QColor(245, 170, 188, 120)


def _shine_path(cx: float, cy: float, r: float, waist: float) -> QPainterPath:
    """四段贝塞尔拼菱形高光 waist越小越尖"""
    w = r * waist
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.quadTo(cx + w, cy - w, cx + r, cy)
    path.quadTo(cx + w, cy + w, cx, cy + r)
    path.quadTo(cx - w, cy + w, cx - r, cy)
    path.quadTo(cx - w, cy - w, cx, cy - r)
    path.closeSubpath()
    return path


def _glow(painter: QPainter, cx: float, cy: float, r: float, color: QColor, alpha: int) -> None:
    """径向渐隐的光晕"""
    g = QRadialGradient(QPointF(cx, cy), r)
    g.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
    g.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(g)
    painter.drawEllipse(QPointF(cx, cy), r, r)


def render_face(painter: QPainter, size: float) -> None:
    """把整张脸画进painter 全按比例算"""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size
    radius = s * 0.28
    rect = QRectF(0, 0, s, s)

    bg = QLinearGradient(0, 0, s, s)
    bg.setColorAt(0.0, _BADGE_TOP)
    bg.setColorAt(1.0, _BADGE_BOT)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(bg)
    painter.drawRoundedRect(rect, radius, radius)

    painter.save()
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    painter.setClipPath(clip)  # 先clip进圆角矩形

    cx, cy = s * 0.5, s * 0.5
    _glow(painter, cx, cy, s * 0.52, _CYAN, 60)
    _glow(painter, cx, cy, s * 0.42, _VIOLET, 85)

    bw, bh = s * 0.60, s * 0.52
    body = QRectF(cx - bw / 2, cy - bh / 2 + s * 0.02, bw, bh)  # 往下挪一点
    grad = QLinearGradient(0, body.top(), 0, body.bottom())
    grad.setColorAt(0.0, _FEIXUE_TOP)
    grad.setColorAt(1.0, _FEIXUE_BOT)
    painter.setBrush(grad)
    painter.drawRoundedRect(body, bh * 0.46, bh * 0.46)

    painter.setBrush(QColor(255, 255, 255, 150))
    painter.drawPath(_shine_path(cx - bw * 0.17, body.top() + bh * 0.22, s * 0.05, 0.2))

    cheek_y = body.center().y() + bh * 0.13
    painter.setBrush(_BLUSH)
    painter.drawEllipse(QPointF(cx - bw * 0.28, cheek_y), bw * 0.09, bw * 0.06)
    painter.drawEllipse(QPointF(cx + bw * 0.28, cheek_y), bw * 0.09, bw * 0.06)

    ew, eh = bw * 0.13, bh * 0.27
    ey = body.center().y() - bh * 0.04
    dx = bw * 0.22
    painter.setBrush(_INK)
    for sx in (-1, 1):  # 镜像左右眼
        ex = cx + sx * dx
        painter.drawRoundedRect(QRectF(ex - ew / 2, ey - eh / 2, ew, eh), ew / 2, ew / 2)
    painter.setBrush(QColor(255, 255, 255, 230))
    for sx in (-1, 1):  # 眼里高光左上偏一点
        ex = cx + sx * dx
        painter.drawEllipse(QPointF(ex - ew * 0.10, ey - eh * 0.24), ew * 0.17, ew * 0.17)

    pen = QPen(_INK)
    pen.setWidthF(max(1.0, s * 0.016))  # 嘴线宽随尺寸缩 至少留1px
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    mw = bw * 0.17
    my = body.center().y() + bh * 0.18
    painter.drawArc(QRectF(cx - mw / 2, my - mw * 0.5, mw, mw), 200 * 16, 140 * 16)  # qt角度要乘16

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 205))
    painter.drawPath(_shine_path(s * 0.80, s * 0.21, s * 0.05, 0.18))
    painter.setBrush(QColor(180, 230, 255, 170))
    painter.drawPath(_shine_path(s * 0.19, s * 0.81, s * 0.04, 0.18))

    painter.restore()


def _face_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)  # 先填透明
    painter = QPainter(pixmap)
    render_face(painter, float(size))
    painter.end()
    return pixmap


_ICON_CACHE: QIcon | None = None


def feixue_icon() -> QIcon:
    """共用应用图标 懒加载进程级缓存"""
    global _ICON_CACHE
    if _ICON_CACHE is None:
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):  # 塞满各档让qt按dpi自己挑
            icon.addPixmap(_face_pixmap(size))
        _ICON_CACHE = icon
    return _ICON_CACHE


def save_ico(path: str = "feixue.ico", sizes: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)) -> str:
    """导出打包用的ico文件"""
    import io

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray

    pm = _face_pixmap(max(sizes))  # 只画最大那张 小尺寸交给pil下采样
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")  # 走内存png中转给pil
    buf.close()
    img = Image.open(io.BytesIO(bytes(ba))).convert("RGBA")
    img.save(path, format="ICO", sizes=[(s, s) for s in sizes])
    return path
