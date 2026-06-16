# author: bdth
# email: 2074055628@qq.com
# 注册windows全局热键并转成qt信号

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
    """解析热键串 非法返回None"""
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    mods = 0
    vk: int | None = None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        elif len(p) == 1 and ("a" <= p <= "z" or "0" <= p <= "9"):
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            vk = 0x70 + int(p[1:]) - 1  # f键从0x70起连续映射
        else:
            return None
    if vk is None or mods == 0:
        return None  # 纯修饰键或没主键的不接受
    return (mods, vk)


class GlobalHotkeys(QObject):
    """全局热键转qt信号 独立线程跑消息循环"""

    summon = Signal()
    ask_selection = Signal()
    quick_rewrite = Signal()
    talk_pressed = Signal()
    status = Signal(object)

    _ACTIONS = ("summon", "ask", "quick", "talk")

    def __init__(self, keys: dict) -> None:
        super().__init__()
        self._keys = dict(keys)
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._ready = threading.Event()  # _run 写好 _tid 后置位 stop 据此别在 _tid 还是0时投空 WM_QUIT
        self._status: dict[str, bool] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="star-hotkeys")
        self._thread.start()

    def stop(self) -> None:
        thread = self._thread
        if thread is not None:
            # 等 _run 把 _tid 赋好再投 WM_QUIT——否则快速 restart 时 _tid 还是0 投了个空 线程会卡死在
            # GetMessageW 里且热键不反注册 变成占着热键 id 的孤儿线程(下次注册同键会失败 热键静默失灵)
            self._ready.wait(timeout=2.0)
        if self._tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            except (AttributeError, OSError):
                pass
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._tid = 0

    def restart(self, keys: dict) -> None:
        """键变了才重启线程"""
        new = dict(keys)
        if new == self._keys and self._thread is not None:
            return
        self.stop()
        self._keys = new
        self.start()

    def _run(self) -> None:
        """工作线程 注册热键 抽消息 退出时全部反注册"""
        user32 = kernel32 = None
        id_map: dict[int, str] = {}  # 注册成功的id到action
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._tid = kernel32.GetCurrentThreadId()  # 留给stop投WM_QUIT
            self._ready.set()  # _tid 已就绪 放行 stop() 的等待
            status: dict[str, bool] = {}
            for index, action in enumerate(self._ACTIONS, start=1):  # id从1起
                parsed = parse_combo(self._keys.get(action, ""))
                if parsed is None:
                    status[action] = False
                    continue
                mods, vk = parsed
                # norepeat 长按只触发一次
                ok = bool(user32.RegisterHotKey(None, index, mods | _MOD_NOREPEAT, vk))
                status[action] = ok
                if ok:
                    id_map[index] = action
            self._status = status
            self.status.emit(dict(status))
            sigs: dict[str, Callable] = {
                "summon": self.summon.emit, "ask": self.ask_selection.emit,
                "quick": self.quick_rewrite.emit, "talk": self.talk_pressed.emit,
            }
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):
                    break  # 收到WM_QUIT或出错都退
                if msg.message == _WM_HOTKEY:
                    action = id_map.get(msg.wParam)
                    if action:
                        sigs[action]()
        except Exception:
            pass
        finally:
            self._ready.set()  # 即便注册前就崩了也放行 stop() 别让它干等满 2s
            if user32 is not None:
                for index in id_map:
                    try:
                        user32.UnregisterHotKey(None, index)
                    except (AttributeError, OSError):
                        pass
