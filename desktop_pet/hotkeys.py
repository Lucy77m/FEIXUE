# author: bdth
# email: 2074055628@qq.com
# 注册 Windows 全局热键（唤出 / 问选区 / 顺手改），组合键可由控制面板自定义；
# 在后台线程跑 Win32 消息循环并转成 Qt 信号，并把每个键的注册结果(成功/被占用)回报给面板。

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_NOREPEAT = 0x4000
_MODS = {
    "ctrl": 0x0002, "control": 0x0002,
    "alt": 0x0001,
    "shift": 0x0004,
    "win": 0x0008, "meta": 0x0008, "super": 0x0008,
}


def parse_combo(combo: str) -> tuple[int, int] | None:
    """'ctrl+shift+q' / 'Ctrl+Alt+S' → (mods, vk)；缺修饰键或解析不出主键返回 None。"""
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    mods = 0
    vk: int | None = None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        elif len(p) == 1 and ("a" <= p <= "z" or "0" <= p <= "9"):
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            vk = 0x70 + int(p[1:]) - 1  # F1..F24
        else:
            return None
    if vk is None or mods == 0:  # 必须「修饰键 + 主键」，纯单键不收(太容易误触/抢不到)
        return None
    return (mods, vk)


class GlobalHotkeys(QObject):
    summon = Signal()
    ask_selection = Signal()
    quick_rewrite = Signal()
    status = Signal(object)  # {"summon": bool, "ask": bool, "quick": bool}：是否注册成功(False=被占/非法)

    _ACTIONS = ("summon", "ask", "quick")

    def __init__(self, keys: dict) -> None:
        super().__init__()
        self._keys = dict(keys)  # {"summon": "ctrl+alt+s", "ask": ..., "quick": ...}
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._status: dict[str, bool] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="star-hotkeys")
        self._thread.start()

    def stop(self) -> None:
        if self._tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            except (AttributeError, OSError):
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._tid = 0

    def restart(self, keys: dict) -> None:
        """用户在面板改了键：停旧线程、用新键重注册（会重新 emit status）。键没变就不折腾。"""
        new = dict(keys)
        if new == self._keys and self._thread is not None:
            return
        self.stop()
        self._keys = new
        self.start()

    def current_status(self) -> dict:
        return dict(self._status)

    def _run(self) -> None:
        user32 = kernel32 = None
        id_map: dict[int, str] = {}
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._tid = kernel32.GetCurrentThreadId()
            status: dict[str, bool] = {}
            for index, action in enumerate(self._ACTIONS, start=1):
                parsed = parse_combo(self._keys.get(action, ""))
                if parsed is None:
                    status[action] = False
                    continue
                mods, vk = parsed
                ok = bool(user32.RegisterHotKey(None, index, mods | _MOD_NOREPEAT, vk))
                status[action] = ok
                if ok:
                    id_map[index] = action
            self._status = status
            self.status.emit(dict(status))
            sigs: dict[str, Callable] = {
                "summon": self.summon.emit, "ask": self.ask_selection.emit, "quick": self.quick_rewrite.emit,
            }
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):
                    break
                if msg.message == _WM_HOTKEY:
                    action = id_map.get(msg.wParam)
                    if action:
                        sigs[action]()
        except Exception:  # noqa: BLE001
            pass
        finally:
            if user32 is not None:
                for index in id_map:
                    try:
                        user32.UnregisterHotKey(None, index)
                    except (AttributeError, OSError):
                        pass
