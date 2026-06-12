# author: bdth
# email: 2074055628@qq.com
# 程序入口 先设置dpi感知再启动桌宠

from __future__ import annotations

import ctypes as _ctypes


def _enable_faulthandler() -> None:
    try:
        import faulthandler
        import os
        base = os.environ.get("STAR_DATA_DIR") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data")
        log_dir = os.path.join(base, "logs")
        os.makedirs(log_dir, exist_ok=True)
        fh = open(os.path.join(log_dir, "crash.log"), "a", encoding="utf-8")
        faulthandler.enable(file=fh, all_threads=True)
    except Exception:
        pass


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


_enable_faulthandler()
_set_dpi_aware()

from desktop_pet.app.core import PetApp


def main() -> int:
    try:
        return PetApp().run()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
