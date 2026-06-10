# author: bdth
# email: 2074055628@qq.com
# 幽灵鼠标 postmessage后台点击不动真实光标

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32

_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_LBUTTONDBLCLK = 0x0203
_WM_RBUTTONDOWN = 0x0204
_WM_RBUTTONUP = 0x0205
_MK_LBUTTON = 0x0001
_MK_RBUTTON = 0x0002

_CWP_SKIP = 0x0001 | 0x0002 | 0x0004
_MAX_DESCEND = 32

_GCL_STYLE = -26
_CS_DBLCLKS = 0x0008

_ChildWindowFromPointEx = _user32.ChildWindowFromPointEx
_ChildWindowFromPointEx.argtypes = [wintypes.HWND, wintypes.POINT, wintypes.UINT]
_ChildWindowFromPointEx.restype = wintypes.HWND

_GetClassLongPtr = getattr(_user32, "GetClassLongPtrW", _user32.GetClassLongW)


def _wants_dblclk_msg(hwnd: int) -> bool:
    """窗口类有没有注册cs_dblclks"""
    try:
        return bool(_GetClassLongPtr(hwnd, _GCL_STYLE) & _CS_DBLCLKS)
    except Exception:
        return True


def _pack_lparam(cx: int, cy: int) -> int:
    return ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)


def _screen_to_client(hwnd: int, sx: int, sy: int) -> tuple[int, int]:
    pt = wintypes.POINT(int(sx), int(sy))
    _user32.ScreenToClient(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def _descend(top_hwnd: int, sx: int, sy: int) -> int:
    """钻到点所在的最底层子窗口"""
    cur = top_hwnd
    # 跳过隐藏禁用透明的子窗口 层数封顶
    for _ in range(_MAX_DESCEND):
        cx, cy = _screen_to_client(cur, sx, sy)
        child = _ChildWindowFromPointEx(cur, wintypes.POINT(cx, cy), _CWP_SKIP)
        if not child or child == cur:
            return cur
        cur = child
    return cur


def _post(hwnd: int, msg: int, wparam: int, lparam: int) -> bool:
    return bool(_user32.PostMessageW(hwnd, msg, wparam, lparam))


def bg_click(top_hwnd: int, sx: int, sy: int, kind: str = "click") -> bool:
    """后台点击"""
    hwnd = int(top_hwnd or 0)
    if not hwnd or not _user32.IsWindow(hwnd):
        return False
    # 最小化不投
    if _user32.IsIconic(hwnd):
        return False
    target = _descend(hwnd, int(sx), int(sy))
    cx, cy = _screen_to_client(target, int(sx), int(sy))
    # 客户坐标为负不点
    if cx < 0 or cy < 0:
        return False
    lp = _pack_lparam(cx, cy)

    # 先补一发mousemove触发hover
    ok = _post(target, _WM_MOUSEMOVE, 0, lp)
    if kind == "right":
        ok &= _post(target, _WM_RBUTTONDOWN, _MK_RBUTTON, lp)
        ok &= _post(target, _WM_RBUTTONUP, 0, lp)
        return bool(ok)
    ok &= _post(target, _WM_LBUTTONDOWN, _MK_LBUTTON, lp)
    ok &= _post(target, _WM_LBUTTONUP, 0, lp)
    if kind == "double":
        # 双击第二下按窗口类选消息
        second = _WM_LBUTTONDBLCLK if _wants_dblclk_msg(target) else _WM_LBUTTONDOWN
        ok &= _post(target, second, _MK_LBUTTON, lp)
        ok &= _post(target, _WM_LBUTTONUP, 0, lp)
    return bool(ok)


def foreground_hwnd() -> int:
    """前台窗口句柄"""
    try:
        return int(_user32.GetForegroundWindow() or 0)
    except Exception:
        return 0
