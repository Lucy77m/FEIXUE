# author: bdth
# email: 2074055628@qq.com
# 鼠标操作：将图像坐标换算成屏幕坐标后执行点击/双击/右键/移动/滚动，越界则拒绝

from __future__ import annotations

import pyautogui

from desktop_pet.eyes.capture import image_to_screen

# 关掉 pyautogui 的"鼠标移到屏幕四角即抛 FailSafeException"机制：我们已有自己的 _onscreen 越界保护，
# 而合法操作经常要点到 (0,0) / 右下角等角点；留着 failsafe 会让点角点稳定抛异常、模型反复重试同坐标。
pyautogui.FAILSAFE = False


def _onscreen(sx: int, sy: int) -> bool:
    try:
        w, h = pyautogui.size()
    except Exception:  # noqa: BLE001
        return True  # 拿不到屏幕尺寸就别拦，照常点
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
    # 直接用绝对屏幕坐标点击（act_element 走这里）。加越界检查：陈旧/错误坐标不再盲点屏幕。
    if not _onscreen(int(ax), int(ay)):
        return False
    if kind == "double":
        pyautogui.doubleClick(ax, ay)
    elif kind == "right":
        pyautogui.rightClick(ax, ay)
    else:
        pyautogui.click(ax, ay)
    return True
