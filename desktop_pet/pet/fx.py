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
    """无边框 + 置顶 + 不进任务栏的悬浮窗。Tool 而非 Window —— 不抢焦点、Alt-Tab 里也不露脸。"""
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
    """重新抢回最顶层 —— Qt 的 StaysOnTop 会被别的置顶窗(全屏游戏/弹窗)盖掉，直接走 user32 顶一下。"""
    if not widget.isVisible():
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        # 只顶 Z 序，别动位置/大小、别抢焦点，不然桌宠会跳一下
        ctypes.windll.user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_FLAGS)
    except Exception:
        pass  # 非 Windows 或 winId 还没就绪 —— 置顶只是锦上添花，失败就算了


def ease_out_back(t: float) -> float:
    """回弹缓动：末尾略微冲过头再收回 —— 面板弹出时那点"Q弹"感。_BACK 越大回弹越夸张。"""
    u = t - 1.0
    return 1.0 + (_BACK + 1.0) * u * u * u + _BACK * u * u


def place_beside_pet(
    widget: QWidget, pet: QWidget, screen, prefer: str = "left", gap: int = _GAP, edge: int = _EDGE
) -> None:
    """把面板贴在桌宠旁边、与之垂直居中。prefer 那侧放不下就翻到另一侧，最后整体夹回屏内。"""
    geo = pet.frameGeometry()
    if prefer == "left":
        x = geo.left() - widget.width() - gap
        if x < screen.left() + edge:  # 左边塞不进 —— 翻到右边
            x = geo.right() + gap
    else:
        x = geo.right() + gap
        if x + widget.width() > screen.right() - edge:  # 右边出屏 —— 翻到左边
            x = geo.left() - widget.width() - gap
    y = geo.center().y() - widget.height() // 2
    # 两侧都挤不下时翻完还会越界，统一 clamp 兜底，至少留 edge 边距贴着屏幕
    x = max(screen.left() + edge, min(x, screen.right() - widget.width() - edge))
    y = max(screen.top() + edge, min(y, screen.bottom() - widget.height() - edge))
    widget.move(int(x), int(y))
