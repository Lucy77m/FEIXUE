# author: bdth
# email: 2074055628@qq.com
# 鼠标操作：点击/双击/右键/移动/滚动。
# 用 Win32 SetCursorPos + SendInput 而不是 pyautogui：pyautogui 会把坐标钳到主屏范围，
# 副屏（负坐标 / 主屏右侧）永远点不到；Win32 原生支持整个虚拟桌面。

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
_WHEEL_DELTA = 120
_INPUT_MOUSE = 0
_MOVE_SETTLE_S = 0.02  # SetCursorPos 后给系统一点时间安顿——立刻按下偶尔会落在旧位置
_DOUBLE_GAP_S = 0.04  # 两次单击间隔，太短系统会当成单次点；太长又超过双击判定窗口


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    # _anonymous_ 摊平 union，直接写 inp.mi 不用 inp.u.mi
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(flags: int, data: int = 0) -> None:
    """data 只滚轮用得上（走 mouseData），按下/抬起传 0。"""
    inp = _INPUT(type=_INPUT_MOUSE)
    # data 可能是负的（向下滚），mouseData 是 DWORD，得手动转成无符号 32 位
    inp.mi = _MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, None)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _virtual_rect() -> tuple[int, int, int, int]:
    """整个虚拟桌面的 (left, top, w, h)。left/top 可能为负——副屏挂在主屏左边时就是负的。"""
    return (
        _SM(_SM_XVIRTUALSCREEN), _SM(_SM_YVIRTUALSCREEN),
        # 宽高拿到 0 兜底成 1：极少数情况（无显示器/RDP 刚连上）metrics 还没就绪，别让范围塌成空
        _SM(_SM_CXVIRTUALSCREEN) or 1, _SM(_SM_CYVIRTUALSCREEN) or 1,
    )


def _onscreen(sx: int, sy: int) -> bool:
    """坐标是否落在虚拟桌面内——含负坐标的副屏，不是只判主屏。"""
    left, top, w, h = _virtual_rect()
    return left <= sx < left + w and top <= sy < top + h


def _move_cursor(sx: int, sy: int) -> None:
    _user32.SetCursorPos(int(sx), int(sy))


def _click_at(sx: int, sy: int, kind: str = "click") -> None:
    """先把光标挪过去再原地按——SendInput 不带坐标，靠 SetCursorPos 定位。kind: click/double/right。"""
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


def _oob(x: int, y: int, sx: int, sy: int) -> str:
    return (f"[坐标 ({x}, {y}) 换算到屏幕 ({sx}, {sy}) 已超出所有显示器范围，没有点击——"
            f"先用 screen_elements / screenshot 取准当前坐标再来]")


def click(x: int, y: int) -> str:
    """(x, y) 是截图坐标，得先 image_to_screen 换到真实屏幕。下面双击/右键/移动同理。"""
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


def click_screen(ax: int, ay: int, kind: str = "click") -> bool:
    """传进来的已经是屏幕坐标——不走 image_to_screen 换算，给内部已知真实坐标的调用方用。"""
    if not _onscreen(int(ax), int(ay)):
        return False
    _click_at(int(ax), int(ay), kind)
    return True
