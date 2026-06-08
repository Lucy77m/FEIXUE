# author: bdth
# email: 2074055628@qq.com
# 桌面窗口操作工具:列举/聚焦窗口,以及最小化、最大化、还原、关闭、移动、调整大小

from __future__ import annotations

import time

import pygetwindow as gw


def list_windows() -> str:
    titles = sorted({t for t in gw.getAllTitles() if t.strip()})
    return "\n".join(titles) if titles else "(no visible windows)"


def focus_window(title: str) -> str:
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return f"Window not found: {title}"
    window = matches[0]
    if window.isMinimized:
        window.restore()
    try:
        window.activate()
    except Exception as exc:
        return (f"激活「{window.title}」失败({type(exc).__name__})——Windows 常拦后台程序抢前台；"
                f"要操作它直接 screen_elements / act_element 即可，不一定非得它在最前")
    time.sleep(0.12)
    active = gw.getActiveWindow()
    if active is not None and (active.title or "") == window.title:
        return f"Activated window: {window.title}"
    return (f"已尝试激活「{window.title}」，但它可能没真正到最前(Windows 前台锁常见)；"
            f"直接 screen_elements / act_element 操作它通常照样行")


_WINDOW_ACTIONS = ("minimize", "maximize", "restore", "close", "move", "resize")


def manage_window(
    title: str, action: str,
    x: int | None = None, y: int | None = None,
    width: int | None = None, height: int | None = None,
) -> str:
    action = (action or "").strip().lower()
    if action not in _WINDOW_ACTIONS:
        return f"Unknown action \"{action}\"; available: {' / '.join(_WINDOW_ACTIONS)}"
    matches = gw.getWindowsWithTitle(title)
    if not matches:
        return f"Window not found: {title}"
    window = matches[0]
    try:
        if action == "minimize":
            window.minimize()
        elif action == "maximize":
            window.maximize()
        elif action == "restore":
            window.restore()
        elif action == "close":
            window.close()
            time.sleep(0.15)
            if gw.getWindowsWithTitle(title):
                return f"对「{title}」发了关闭，但它好像还在(可能弹了保存提示，或被程序拦下了)——截图确认一下"
            return f"Closed window: {title}"
        elif action == "move":
            if x is None or y is None:
                return "move needs both x and y."
            window.moveTo(int(x), int(y))
        elif action == "resize":
            if width is None or height is None:
                return "resize needs width and height."
            window.resizeTo(int(width), int(height))
    except Exception as exc:
        return f"Couldn't {action} window \"{window.title}\": {type(exc).__name__}: {exc}"
    return f"Did {action} on window \"{window.title}\"."
