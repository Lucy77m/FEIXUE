# author: bdth
# email: 2074055628@qq.com
# 鼠标操作：点击/双击/右键/移动/滚动。

from __future__ import annotations

import pyautogui

from desktop_pet.eyes.capture import image_to_screen

pyautogui.FAILSAFE = False


def _onscreen(sx: int, sy: int) -> bool:
    try:
        w, h = pyautogui.size()
    except Exception:
        return True
    return 0 <= sx < w and 0 <= sy < h


def _oob(x: int, y: int, sx: int, sy: int) -> str:
    return (f"[坐标 ({x}, {y}) 换算到屏幕 ({sx}, {sy}) 已超出屏幕范围，没有点击——"
            f"先用 screen_elements / screenshot 取准当前坐标再来]")


def click(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    pyautogui.click(sx, sy)
    return f"clicked ({x}, {y})"


def double_click(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    pyautogui.doubleClick(sx, sy)
    return f"double-clicked ({x}, {y})"


def right_click(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    pyautogui.rightClick(sx, sy)
    return f"right-clicked ({x}, {y})"


def move(x: int, y: int) -> str:
    sx, sy = image_to_screen(x, y)
    if not _onscreen(sx, sy):
        return _oob(x, y, sx, sy)
    pyautogui.moveTo(sx, sy)
    return f"moved to ({x}, {y})"


def scroll(amount: int) -> str:
    pyautogui.scroll(amount)
    return f"scrolled {amount}"


def click_screen(ax: int, ay: int, kind: str = "click") -> bool:
    if not _onscreen(int(ax), int(ay)):
        return False
    if kind == "double":
        pyautogui.doubleClick(ax, ay)
    elif kind == "right":
        pyautogui.rightClick(ax, ay)
    else:
        pyautogui.click(ax, ay)
    return True
