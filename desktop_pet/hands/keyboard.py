# author: bdth
# email: 2074055628@qq.com
# 键盘输入：模拟打字与组合键，非 ASCII 文本走剪贴板粘贴

from __future__ import annotations

import time

import pyautogui

from desktop_pet.executor import clipboard


def type_text(text: str) -> str:
    if not text:
        return "typed 0 chars"
    if all(ord(c) < 128 for c in text):
        pyautogui.write(text, interval=0.01)
        return f"typed {len(text)} chars"
    saved = clipboard.read_clipboard_text()  # str|None：只在原来确有文本时才恢复，正文以 '(' 开头也不会被丢
    clipboard.write_clipboard(text)
    time.sleep(0.06)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    if saved is not None:
        clipboard.write_clipboard(saved)
    return f"typed {len(text)} chars (pasted via clipboard — non-ASCII)"


def press_keys(keys: str) -> str:
    # 空格分隔「依次按下的多个组合键」，每个组合键内用 + 连接「同时按下的键」。
    # 例：'ctrl+a' = 同时按 Ctrl+A；'ctrl+a delete enter' = 先 Ctrl+A，再 Delete，再 Enter。
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
