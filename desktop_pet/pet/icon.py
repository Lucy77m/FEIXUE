# author: bdth
# email: 2074055628@qq.com
# 用 QPainter 矢量绘制 Mochi 桌宠的脸,生成多尺寸应用图标

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
_MOCHI_TOP = QColor(252, 252, 254)
_MOCHI_BOT = QColor(226, 230, 240)
_BLUSH = QColor(245, 170, 188, 120)


def _shine_path(cx: float, cy: float, r: float, waist: float) -> QPainterPath:
    """四段二次贝塞尔拼出的菱形高光——waist 越小越尖，0.2 左右出"星点/反光"那味。"""
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
    """中心向外径向渐隐的光晕——外圈 alpha 必须收到 0，否则会硬切出一道圆边。"""
    g = QRadialGradient(QPointF(cx, cy), r)
    g.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
    g.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(g)
    painter.drawEllipse(QPointF(cx, cy), r, r)


def render_face(painter: QPainter, size: float) -> None:
    """把整张脸画进 painter——所有尺寸都用 s 的比例算，这样 16px 到 256px 一套代码通吃。"""
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
    painter.setClipPath(clip)  # 后面光晕/高光都会溢出圆角，先夹进圆角矩形别糊到角外

    cx, cy = s * 0.5, s * 0.5
    _glow(painter, cx, cy, s * 0.52, _CYAN, 60)
    _glow(painter, cx, cy, s * 0.42, _VIOLET, 85)

    bw, bh = s * 0.60, s * 0.52
    body = QRectF(cx - bw / 2, cy - bh / 2 + s * 0.02, bw, bh)  # +0.02 往下挪一点，视觉重心比几何正中更稳
    grad = QLinearGradient(0, body.top(), 0, body.bottom())
    grad.setColorAt(0.0, _MOCHI_TOP)
    grad.setColorAt(1.0, _MOCHI_BOT)
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
    for sx in (-1, 1):  # sx=±1 镜像左右眼，省得两套坐标
        ex = cx + sx * dx
        painter.drawRoundedRect(QRectF(ex - ew / 2, ey - eh / 2, ew, eh), ew / 2, ew / 2)
    painter.setBrush(QColor(255, 255, 255, 230))
    for sx in (-1, 1):  # 眼里那点白：左上偏一点，看着才有神
        ex = cx + sx * dx
        painter.drawEllipse(QPointF(ex - ew * 0.10, ey - eh * 0.24), ew * 0.17, ew * 0.17)

    pen = QPen(_INK)
    pen.setWidthF(max(1.0, s * 0.016))  # 嘴线宽随尺寸缩，但 16px 小图上至少留 1px 不然这笑就没了
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    mw = bw * 0.17
    my = body.center().y() + bh * 0.18
    painter.drawArc(QRectF(cx - mw / 2, my - mw * 0.5, mw, mw), 200 * 16, 140 * 16)  # Qt 的角度单位是 1/16 度，别忘了乘 16

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 205))
    painter.drawPath(_shine_path(s * 0.80, s * 0.21, s * 0.05, 0.18))
    painter.setBrush(QColor(180, 230, 255, 170))
    painter.drawPath(_shine_path(s * 0.19, s * 0.81, s * 0.04, 0.18))

    painter.restore()


def _face_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)  # 先填透明，圆角外的四角才不会留黑底
    painter = QPainter(pixmap)
    render_face(painter, float(size))
    painter.end()
    return pixmap


_ICON_CACHE: QIcon | None = None


def mochi_icon() -> QIcon:
    """全程序共用的应用图标，懒加载 + 进程级缓存——七张多尺寸位图一次画好，省得每次重绘。"""
    global _ICON_CACHE
    if _ICON_CACHE is None:
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):  # 塞满各档，让 Qt 按托盘/任务栏 DPI 自己挑最合适的，4K 屏才不糊
            icon.addPixmap(_face_pixmap(size))
        _ICON_CACHE = icon
    return _ICON_CACHE


def save_ico(path: str = "mochi.ico", sizes: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)) -> str:
    """导出打包用的 .ico（exe 图标/快捷方式都吃这个）——PIL 只在这里才需要，故延迟导入。"""
    import io

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray

    pm = _face_pixmap(max(sizes))  # 只画最大那张，小尺寸交给 PIL 下采样，比逐档重绘锐
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")  # QPixmap 不能直接喂 PIL，走内存里 PNG 中转
    buf.close()
    img = Image.open(io.BytesIO(bytes(ba))).convert("RGBA")
    img.save(path, format="ICO", sizes=[(s, s) for s in sizes])
    return path
