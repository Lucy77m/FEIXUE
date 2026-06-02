# author: bdth
# email: 2074055628@qq.com
# 程序入口:在创建任何窗口前设置高 DPI 感知,然后启动桌宠应用

from __future__ import annotations

import ctypes as _ctypes


def _set_dpi_aware() -> None:
    try:
        _ctypes.windll.user32.SetProcessDpiAwarenessContext(_ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError, ValueError):
        pass
    try:
        _ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        _ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


_set_dpi_aware()

from desktop_pet.app import PetApp


def main() -> int:
    try:
        return PetApp().run()
    except KeyboardInterrupt:  # Ctrl+C 静默退出,不打印 traceback
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
