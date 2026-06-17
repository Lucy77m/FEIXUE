# author: bdth
# email: 2074055628@qq.com
# 键盘输入 模拟打字和组合键

from __future__ import annotations

import time

import pyautogui

from desktop_pet.executor import clipboard

# 关掉pyautogui角落急停
pyautogui.FAILSAFE = False


def type_text(text: str) -> str:
    """模拟打字 非ascii走剪贴板"""
    if not text:
        return "typed 0 chars"
    if all(ord(c) < 128 for c in text):
        pyautogui.write(text, interval=0.01)
        return f"typed {len(text)} chars"
    snap = clipboard.snapshot_clipboard()  # 连图片一起存 粘完原样还回去 别把用户复制的图弄丢
    clipboard.write_clipboard(text)
    time.sleep(0.06)  # 等剪贴板刷新
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)  # 等粘贴落地再还原
    clipboard.restore_clipboard(snap)
    return f"typed {len(text)} chars (pasted via clipboard — non-ASCII)"


def press_keys(keys: str) -> str:
    """按组合键"""
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
