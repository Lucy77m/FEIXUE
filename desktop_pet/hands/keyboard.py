# author: bdth
# email: 2074055628@qq.com
# 键盘输入：模拟打字与组合键

from __future__ import annotations

import time

import pyautogui

from desktop_pet.executor import clipboard

# 关掉 pyautogui 的角落急停——鼠标甩到屏幕左上角就抛异常那套，我们自己控流程，别让它半路掀桌。
pyautogui.FAILSAFE = False


def type_text(text: str) -> str:
    """模拟打字：纯 ASCII 直接逐字符敲，含中文/emoji 时走剪贴板粘贴（write 打不出非 ASCII）。"""
    if not text:
        return "typed 0 chars"
    if all(ord(c) < 128 for c in text):
        pyautogui.write(text, interval=0.01)
        return f"typed {len(text)} chars"
    saved = clipboard.read_clipboard_text()  # 先存一份用户原有剪贴板，粘完还回去，别把人家复制的东西吞了
    clipboard.write_clipboard(text)
    time.sleep(0.06)  # 留一拍给系统刷新剪贴板，写完立刻 Ctrl+V 有时贴到的是旧内容
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)  # 等粘贴落地再恢复剪贴板，太快还原会抢在 V 之前、贴出来是 saved
    if saved is not None:  # 读不到（None）就别瞎写空串覆盖，保持原样
        clipboard.write_clipboard(saved)
    return f"typed {len(text)} chars (pasted via clipboard — non-ASCII)"


def press_keys(keys: str) -> str:
    """按组合键：空格分隔多组、每组内 + 连接（例 "ctrl+c ctrl+v" → 先复制再粘贴）。"""
    chords = [c for c in (keys or "").split() if c.strip()]
    pressed: list[str] = []
    for chord in chords:
        combo = [k.strip().lower() for k in chord.split("+") if k.strip()]
        if not combo:
            continue
        if len(combo) == 1:
            pyautogui.press(combo[0])
        else:
            pyautogui.hotkey(*combo)
        pressed.append("+".join(combo))
    if not pressed:
        return f"[没解析出有效按键: {keys!r}——什么都没按]"
    return f"pressed {' '.join(pressed)}"
