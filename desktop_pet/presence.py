# 用户在场感知 检测空闲时长和前台窗口标题

from __future__ import annotations

import ctypes


class _LastInputInfo(ctypes.Structure):
    # 对应 win32 LASTINPUTINFO 结构
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """距上次键鼠输入的空闲秒数 拿不到当 0"""
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        # 掩到 32 位相减 处理回绕
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        elapsed_ms = (now - info.dwTime) & 0xFFFFFFFF
    except (AttributeError, OSError):
        return 0.0
    return elapsed_ms / 1000.0


def foreground_window_title() -> str:
    """取前台窗口标题 取不到返回空串"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)  # 给结尾 NUL 留位
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except (AttributeError, OSError):
        return ""
