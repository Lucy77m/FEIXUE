# author: bdth
# email: 2074055628@qq.com
# 桌宠窗口特效工具:无边框置顶、缓动动画与贴边定位

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

_BACK = 1.70158
_GAP = 24
_EDGE = 8


def make_floating(widget: QWidget) -> None:
    widget.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_FLAGS = _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE


def raise_topmost(widget: QWidget) -> None:
    if not widget.isVisible():
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        ctypes.windll.user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_FLAGS)
    except Exception:  # noqa: BLE001
        pass


def ease_out_back(t: float) -> float:
    u = t - 1.0
    return 1.0 + (_BACK + 1.0) * u * u * u + _BACK * u * u


def place_beside_pet(
    widget: QWidget, pet: QWidget, screen, prefer: str = "left", gap: int = _GAP, edge: int = _EDGE
) -> None:
    geo = pet.frameGeometry()
    if prefer == "left":
        x = geo.left() - widget.width() - gap
        if x < screen.left() + edge:
            x = geo.right() + gap
    else:
        x = geo.right() + gap
        if x + widget.width() > screen.right() - edge:
            x = geo.left() - widget.width() - gap
    y = geo.center().y() - widget.height() // 2
    x = max(screen.left() + edge, min(x, screen.right() - widget.width() - edge))
    y = max(screen.top() + edge, min(y, screen.bottom() - widget.height() - edge))
    widget.move(int(x), int(y))
