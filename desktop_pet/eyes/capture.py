# author: bdth
# email: 2074055628@qq.com
# 屏幕截图模块：抓取活动显示器画面、按需裁剪到当前窗口、缩放编码为 JPEG/DataURL，并把自身窗口排除在截图之外

from __future__ import annotations

import base64
import ctypes
import io
import time
from ctypes import wintypes
from dataclasses import dataclass

import pygetwindow as gw
from PIL import Image

from desktop_pet.settings import CAPTURE_WINDOW

_MASK_COLOR = (0, 0, 0)
_MAX_LONG_EDGE = 3840
_JPEG_QUALITY = 82

_WDA_NONE = 0x00
_WDA_EXCLUDEFROMCAPTURE = 0x11
_RECOMPOSE_S = 0.06

_own_hwnds: set[int] = set()

_user32 = ctypes.windll.user32
_SM = _user32.GetSystemMetrics
_MONITOR_DEFAULTTONEAREST = 2


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_geom: tuple[int, int, int, int] = (0, 0, _SM(0) or 1, _SM(1) or 1)

try:
    _set_affinity_fn = _user32.SetWindowDisplayAffinity
    _set_affinity_fn.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    _set_affinity_fn.restype = ctypes.c_bool
except (AttributeError, OSError):
    _set_affinity_fn = None


def _set_affinity(hwnd: int, value: int) -> bool:
    if _set_affinity_fn is None or not hwnd:
        return False
    try:
        return bool(_set_affinity_fn(ctypes.c_void_p(int(hwnd)), value))
    except OSError:
        return False


def register_own_window(hwnd: int) -> None:
    if not hwnd:
        return
    _own_hwnds.add(int(hwnd))
    _set_affinity(int(hwnd), _WDA_EXCLUDEFROMCAPTURE)


def _monitor_rect_at(x: int, y: int) -> tuple[int, int, int, int] | None:
    try:
        hmon = _user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), _MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not _user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return None
        r = info.rcMonitor
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    except OSError:
        return None


def _active_monitor_rect() -> tuple[int, int, int, int]:
    try:
        win = gw.getActiveWindow()
        if win is not None and win.width > 0 and win.height > 0:
            rect = _monitor_rect_at(win.left + win.width // 2, win.top + win.height // 2)
            if rect is not None:
                return rect
    except Exception:  # noqa: BLE001
        pass
    try:
        pt = wintypes.POINT()
        if _user32.GetCursorPos(ctypes.byref(pt)):
            rect = _monitor_rect_at(pt.x, pt.y)
            if rect is not None:
                return rect
    except OSError:
        pass
    return 0, 0, _SM(0) or 1, _SM(1) or 1


def set_geom_for_point(x: int, y: int) -> None:
    global _geom
    rect = _monitor_rect_at(x, y)
    if rect is not None:
        _geom = rect


def current_geom() -> tuple[int, int, int, int]:
    return _geom


def set_geom(geom: tuple[int, int, int, int]) -> None:
    global _geom
    _geom = geom


def _scale(w: int, h: int) -> float:
    long_edge = max(w, h)
    return min(1.0, _MAX_LONG_EDGE / long_edge) if long_edge else 1.0


def image_to_screen(ix: float, iy: float) -> tuple[int, int]:
    ox, oy, ow, oh = _geom
    s = _scale(ow, oh) or 1.0
    return int(round(ox + ix / s)), int(round(oy + iy / s))


def screen_to_image(ax: float, ay: float) -> tuple[int, int]:
    ox, oy, ow, oh = _geom
    s = _scale(ow, oh)
    return int(round((ax - ox) * s)), int(round((ay - oy) * s))


@dataclass
class Capture:

    png_bytes: bytes
    width: int
    height: int
    focus_title: str | None = None


def capture_screen(mode: str, include_self: bool = False) -> Capture:
    image = _grab(include_self)
    focus_title: str | None = None
    if mode == CAPTURE_WINDOW:
        image, focus_title = _mask_to_active_window(image)
    jpeg, enc_w, enc_h = _encode(image)
    return Capture(jpeg, enc_w, enc_h, focus_title)


def grab_active() -> Image.Image:
    import mss

    global _geom
    _geom = _active_monitor_rect()
    ox, oy, ow, oh = _geom
    with mss.mss() as sct:
        raw = sct.grab({"left": ox, "top": oy, "width": ow, "height": oh})
    return Image.frombytes("RGB", raw.size, raw.rgb)


def _grab(include_self: bool) -> Image.Image:
    if not (include_self and _own_hwnds):
        return grab_active()
    for hwnd in _own_hwnds:
        _set_affinity(hwnd, _WDA_NONE)
    time.sleep(_RECOMPOSE_S)
    try:
        return grab_active()
    finally:
        for hwnd in _own_hwnds:
            _set_affinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)


def _mask_to_active_window(image: Image.Image) -> tuple[Image.Image, str | None]:
    ox, oy, _ow, _oh = _geom
    box = _active_window_box(ox, oy, image.width, image.height)
    if box is None:
        return image, None
    left, top, right, bottom, title = box
    masked = Image.new("RGB", image.size, _MASK_COLOR)
    masked.paste(image.crop((left, top, right, bottom)), (left, top))
    return masked, title


def _active_window_box(
    ox: int, oy: int, img_w: int, img_h: int
) -> tuple[int, int, int, int, str] | None:
    try:
        window = gw.getActiveWindow()
    except Exception:  # noqa: BLE001
        return None
    if window is None:
        return None
    left = max(0, window.left - ox)
    top = max(0, window.top - oy)
    right = min(img_w, window.left - ox + window.width)
    bottom = min(img_h, window.top - oy + window.height)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom, window.title


def _encode(image: Image.Image) -> tuple[bytes, int, int]:
    long_edge = max(image.width, image.height)
    if long_edge > _MAX_LONG_EDGE:
        scale = _MAX_LONG_EDGE / long_edge
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
    return buffer.getvalue(), image.width, image.height


def to_data_url(jpeg_bytes: bytes) -> str:
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
