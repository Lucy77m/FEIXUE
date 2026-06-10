# author: bdth
# email: 2074055628@qq.com
# 幽灵鼠标：不动真实光标，把合成的鼠标消息（WM_MOUSEMOVE/WM_*BUTTON*）直接 PostMessage
# 给目标窗口——窗口被遮挡、不在前台也能点，和用户的真实鼠标互不干扰。
# 局限（调用方要心里有数）：标准 Win32 / CEF(Chromium) 窗口大多正常吃消息；
# 读真实光标位置(GetCursorPos)或走 Raw Input 的应用（游戏、部分自绘 UI）会无视；
# 投递成功 ≠ 应用真的响应了，效果要靠重新观察屏幕来确认。

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
    """目标窗口类有没有注册 CS_DBLCLKS——没有就别投 WM_LBUTTONDBLCLK，那种窗口收到也不认。"""
    try:
        # 取不到类样式时宁可当作支持(返回 True)：投了大不了被忽略，比漏掉双击好。
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
    """逐层钻到 (sx,sy) 落在的最底层子窗口。消息得投给最里层的孩子，投顶层往往没人接。"""
    cur = top_hwnd
    # CWP_SKIP 跳过隐藏/禁用/透明的子窗口；_MAX_DESCEND 封顶 32 层，防自引用或深嵌套时死转。
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
    """后台点击 top_hwnd 下落在 (sx,sy) 的子窗口。kind: click/right/double。"""
    hwnd = int(top_hwnd or 0)
    if not hwnd or not _user32.IsWindow(hwnd):
        return False
    # 最小化时客户区坐标全是负的，别投。
    if _user32.IsIconic(hwnd):
        return False
    target = _descend(hwnd, int(sx), int(sy))
    cx, cy = _screen_to_client(target, int(sx), int(sy))
    # 客户坐标为负说明点落在子窗口外(钻歪了/坐标过期)，宁可不点。
    if cx < 0 or cy < 0:
        return False
    lp = _pack_lparam(cx, cy)

    # 先补一发 MOUSEMOVE：有些控件靠 move 触发 hover 状态，不先动直接按会点不亮。
    ok = _post(target, _WM_MOUSEMOVE, 0, lp)
    if kind == "right":
        ok &= _post(target, _WM_RBUTTONDOWN, _MK_RBUTTON, lp)
        ok &= _post(target, _WM_RBUTTONUP, 0, lp)
        return bool(ok)
    ok &= _post(target, _WM_LBUTTONDOWN, _MK_LBUTTON, lp)
    ok &= _post(target, _WM_LBUTTONUP, 0, lp)
    if kind == "double":
        # 双击第二下：认 CS_DBLCLKS 的窗口用 DBLCLK 消息，不认的退回普通 DOWN 当快速两连击。
        second = _WM_LBUTTONDBLCLK if _wants_dblclk_msg(target) else _WM_LBUTTONDOWN
        ok &= _post(target, second, _MK_LBUTTON, lp)
        ok &= _post(target, _WM_LBUTTONUP, 0, lp)
    return bool(ok)


def foreground_hwnd() -> int:
    """当前前台窗口句柄，取不到给 0。"""
    try:
        return int(_user32.GetForegroundWindow() or 0)
    except Exception:
        return 0
