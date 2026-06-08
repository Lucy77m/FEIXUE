# author: bdth
# email: 2074055628@qq.com
# Windows 剪贴板读写工具,封装文本的读取与写入

from __future__ import annotations


def read_clipboard_text() -> str | None:
    """返回剪贴板里的文本；非文本 / 空 / 读取失败一律返回 None。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            else:
                data = None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None
    return data if data else None


def read_clipboard() -> str:
    text = read_clipboard_text()
    return text if text else "(剪贴板里不是文本、是空的，或读取失败——可能是图片或其它格式)"


def write_clipboard(text: str) -> str:
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, str(text))
        finally:
            win32clipboard.CloseClipboard()
        return f"Wrote to the clipboard ({len(str(text))} chars)."
    except Exception as exc:
        return f"Couldn't write the clipboard: {type(exc).__name__}: {exc}"
