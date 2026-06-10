# author: bdth
# email: 2074055628@qq.com
# windows 剪贴板文本读写

from __future__ import annotations


def read_clipboard_text() -> str | None:
    """读剪贴板文本"""
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
    """读剪贴板 给模型的版本"""
    text = read_clipboard_text()
    return text if text else "(剪贴板里不是文本、是空的，或读取失败——可能是图片或其它格式)"


def write_clipboard(text: str) -> str:
    """写文本进剪贴板"""
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
