# author: bdth
# email: 2074055628@qq.com
# Windows 剪贴板读写工具,封装文本的读取与写入

from __future__ import annotations


def read_clipboard_text() -> str | None:
    """返回剪贴板里的文本；非文本/空串/读失败一律 None。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            # 只认 CF_UNICODETEXT —— 图片/文件列表/HTML 这些非文本格式直接当没有。
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            else:
                data = None
        finally:
            win32clipboard.CloseClipboard()  # 一定要关，Open 不配 Close 会把剪贴板锁死，别的程序读不了
    except Exception:
        return None
    return data if data else None  # 空串也归 None，上层不用再判一次


def read_clipboard() -> str:
    """给模型看的版本 —— 读不到文本时返回一句人话解释，而不是 None。"""
    text = read_clipboard_text()
    return text if text else "(剪贴板里不是文本、是空的，或读取失败——可能是图片或其它格式)"


def write_clipboard(text: str) -> str:
    """把文本写进剪贴板，成败都返回一句话给上层。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()  # 不清空旧内容的话某些格式会残留，写完读出来串味
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, str(text))
        finally:
            win32clipboard.CloseClipboard()
        return f"Wrote to the clipboard ({len(str(text))} chars)."
    except Exception as exc:
        return f"Couldn't write the clipboard: {type(exc).__name__}: {exc}"
