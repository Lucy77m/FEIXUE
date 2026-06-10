# author: bdth
# email: 2074055628@qq.com
# 用户在场感知:检测系统空闲时长与当前前台窗口标题

from __future__ import annotations

import ctypes


class _LastInputInfo(ctypes.Structure):
    # 对应 Win32 LASTINPUTINFO，字段名/类型必须和系统结构一一对上，dwTime 是 GetTickCount 时基的毫秒戳。
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """距上次键鼠输入的空闲秒数；拿不到(非 Windows/调用失败)就当 0.0 —— 宁可误判"有人在"也别瞎触发空闲行为。"""
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        # GetTickCount 是 32 位、约 49.7 天回绕一次；now 和相减都掩到 32 位，跨回绕点也能算出正确差值。
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        elapsed_ms = (now - info.dwTime) & 0xFFFFFFFF
    except (AttributeError, OSError):
        return 0.0
    return elapsed_ms / 1000.0


def foreground_window_title() -> str:
    """当前前台窗口标题，没有/取不到一律返回空串。用 W 系列拿宽字符，避免中文标题乱码。"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)  # +1 给结尾的 NUL 留位，否则末字符被截
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except (AttributeError, OSError):
        return ""
