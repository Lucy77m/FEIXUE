# author: bdth
# email: 2074055628@qq.com
# 注册 Windows 全局热键（唤出 / 问选区 / 顺手改）并转成 Qt 信号。

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
    """解析 "ctrl+alt+s" 这种串；非法/纯修饰键返回 None，给上层当"这条没配好"。"""
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    mods = 0
    vk: int | None = None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        elif len(p) == 1 and ("a" <= p <= "z" or "0" <= p <= "9"):
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            vk = 0x70 + int(p[1:]) - 1  # F1..F24 连续映射，VK_F1=0x70
        else:
            return None
    if vk is None or mods == 0:
        return None  # 纯修饰键 / 没主键的组合不接受 —— RegisterHotKey 也注册不了
    return (mods, vk)


class GlobalHotkeys(QObject):
    """全局热键 → Qt 信号。注册/消息循环都跑在独立线程，信号跨线程回主线程。"""

    summon = Signal()
    ask_selection = Signal()
    quick_rewrite = Signal()
    status = Signal(object)

    _ACTIONS = ("summon", "ask", "quick")

    def __init__(self, keys: dict) -> None:
        super().__init__()
        self._keys = dict(keys)
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
                # 往那条线程塞 WM_QUIT 让 GetMessageW 返回 0 退出 —— 别在别处 join 死等
                ctypes.windll.user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            except (AttributeError, OSError):
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._tid = 0

    def restart(self, keys: dict) -> None:
        """键没变就别瞎重启那条线程，省一次注册/反注册的来回。"""
        new = dict(keys)
        if new == self._keys and self._thread is not None:
            return
        self.stop()
        self._keys = new
        self.start()

    def _run(self) -> None:
        """工作线程：注册热键 → 死循环抽消息 → 退出时全部 Unregister。"""
        user32 = kernel32 = None
        id_map: dict[int, str] = {}  # 注册成功的 id → action；停的时候照这个反注册
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._tid = kernel32.GetCurrentThreadId()  # 留着给 stop() 投 WM_QUIT
            status: dict[str, bool] = {}
            for index, action in enumerate(self._ACTIONS, start=1):  # id 从 1 起，0 被系统占
                parsed = parse_combo(self._keys.get(action, ""))
                if parsed is None:
                    status[action] = False
                    continue
                mods, vk = parsed
                # NOREPEAT：长按只触发一次，不刷一串信号。失败多半是热键被别家占了
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
                    break  # 0=收到 WM_QUIT 正常退；-1=出错，都不再循环
                if msg.message == _WM_HOTKEY:
                    action = id_map.get(msg.wParam)
                    if action:
                        sigs[action]()
        except Exception:
            pass
        finally:
            if user32 is not None:
                for index in id_map:
                    try:
                        user32.UnregisterHotKey(None, index)
                    except (AttributeError, OSError):
                        pass
