# 鼠标操作 win32 sendinput 支持整个虚拟桌面

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from desktop_pet.eyes.capture import image_to_screen

_user32 = ctypes.windll.user32
_SM = _user32.GetSystemMetrics

_SM_XVIRTUALSCREEN, _SM_YVIRTUALSCREEN = 76, 77
_SM_CXVIRTUALSCREEN, _SM_CYVIRTUALSCREEN = 78, 79

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_WHEEL = 0x0800
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040
_WHEEL_DELTA = 120
_INPUT_MOUSE = 0
_MOVE_SETTLE_S = 0.02  # 移动后等系统安顿
_DOUBLE_GAP_S = 0.04  # 双击两次点击的间隔


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    # 摊平union
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(flags: int, data: int = 0) -> None:
    """sendinput发鼠标事件"""
    inp = _INPUT(type=_INPUT_MOUSE)
    # 负数转无符号32位
    inp.mi = _MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, None)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _virtual_rect() -> tuple[int, int, int, int]:
    """虚拟桌面矩形"""
    return (
        _SM(_SM_XVIRTUALSCREEN), _SM(_SM_YVIRTUALSCREEN),
        # 拿到0兜成1
        _SM(_SM_CXVIRTUALSCREEN) or 1, _SM(_SM_CYVIRTUALSCREEN) or 1,
    )


def _onscreen(sx: int, sy: int) -> bool:
    """坐标是否在虚拟桌面内"""
    left, top, w, h = _virtual_rect()
    return left <= sx < left + w and top <= sy < top + h


def _move_cursor(sx: int, sy: int) -> None:
    _user32.SetCursorPos(int(sx), int(sy))


def _click_at(sx: int, sy: int, kind: str = "click") -> None:
    """挪光标过去再按"""
    _move_cursor(sx, sy)
    time.sleep(_MOVE_SETTLE_S)
    if kind == "right":
        _send(_MOUSEEVENTF_RIGHTDOWN)
        _send(_MOUSEEVENTF_RIGHTUP)
        return
    _send(_MOUSEEVENTF_LEFTDOWN)
    _send(_MOUSEEVENTF_LEFTUP)
    if kind == "double":
        time.sleep(_DOUBLE_GAP_S)
        _send(_MOUSEEVENTF_LEFTDOWN)
        _send(_MOUSEEVENTF_LEFTUP)


def _button_flags(button: str) -> tuple[int, int]:
    """Return (down_flag, up_flag) for a button name."""
    if button == "right":
        return _MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP
    if button == "middle":
        return _MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP
    return _MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP


def _oob(x: int, y: int, sx: int, sy: int) -> str:
    return (f"[坐标 ({x}, {y}) 换算到屏幕 ({sx}, {sy}) 已超出所有显示器范围，没有点击——"
            f"先用 screen_elements / screenshot 取准当前坐标再来]")


def click(x: int, y: int) -> str:
    """按截图坐标点击"""
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    _click_at(sx, sy)
    return f"clicked ({x}, {y})"


def double_click(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    _click_at(sx, sy, "double")
    return f"double-clicked ({x}, {y})"


def right_click(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    _click_at(sx, sy, "right")
    return f"right-clicked ({x}, {y})"


def move(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    _move_cursor(sx, sy)
    return f"moved to ({x}, {y})"


def scroll(amount: int) -> str:
    _send(_MOUSEEVENTF_WHEEL, data=int(amount) * _WHEEL_DELTA)
    return f"scrolled {amount}"


_DRAG_STEP_S = 0.015


def drag(x1: int, y1: int, x2: int, y2: int, *, steps: int = 20) -> str:
    """Drag from (x1,y1) to (x2,y2) in screenshot-space coordinates."""
    sx1, sy1 = image_to_screen(x1, y1)
    sx2, sy2 = image_to_screen(x2, y2)
    if not (_onscreen(sx1, sy1) and _onscreen(sx2, sy2)):
        return "drag failed: coordinates off-screen"
    _move_cursor(sx1, sy1)
    time.sleep(_MOVE_SETTLE_S)
    _send(_MOUSEEVENTF_LEFTDOWN)
    for i in range(1, steps + 1):
        cx = sx1 + (sx2 - sx1) * i // steps
        cy = sy1 + (sy2 - sy1) * i // steps
        _move_cursor(cx, cy)
        time.sleep(_DRAG_STEP_S)
    _send(_MOUSEEVENTF_LEFTUP)
    return f"dragged from ({x1},{y1}) to ({x2},{y2})"


def hold(x: int, y: int, button: str = "left") -> str:
    """Press and hold a mouse button at (x,y) in screenshot-space. Does not release."""
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return "hold failed: coordinates off-screen"
    _move_cursor(sx, sy)
    time.sleep(_MOVE_SETTLE_S)
    down_flag, _ = _button_flags(button)
    _send(down_flag)
    return f"{button} button held at ({x},{y})"


def release(x: int, y: int, button: str = "left") -> str:
    """Release a held mouse button at (x,y) in screenshot-space."""
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return "release failed: coordinates off-screen"
    _move_cursor(sx, sy)
    _, up_flag = _button_flags(button)
    _send(up_flag)
    return f"{button} button released at ({x},{y})"


def click_screen(ax: int, ay: int, kind: str = "click") -> bool:
    """按屏幕坐标点击不换算"""
    if not _onscreen(int(ax), int(ay)):
        return False
    _click_at(int(ax), int(ay), kind)
    return True
