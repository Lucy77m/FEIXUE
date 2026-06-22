# 屏幕截图 抓活动显示器 按需裁剪 编码jpeg 排除自身窗口

from __future__ import annotations

import base64
import ctypes
import io
import threading
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
_RECOMPOSE_S = 0.06  # 撤标志后等dwm重新合成的间隔

_own_hwnds: set[int] = set()
# 主线程登记注销自家窗口 worker 线程截图时遍历 加锁加遍历副本防 set changed size during iteration
_own_lock = threading.Lock()

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


# 截图用的监视器矩形做线程本地 每个 agent 各跑在自己的线程上
# 截图到点击的坐标变换得用各自这次截的 geom 共享全局会被别的 agent 改掉点错位置
_geom_default: tuple[int, int, int, int] = (0, 0, _SM(0) or 1, _SM(1) or 1)
_geom_tls = threading.local()


def _get_geom() -> tuple[int, int, int, int]:
    return getattr(_geom_tls, "value", _geom_default)


def _put_geom(geom: tuple[int, int, int, int]) -> None:
    _geom_tls.value = geom

try:
    _set_affinity_fn = _user32.SetWindowDisplayAffinity
    _set_affinity_fn.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    _set_affinity_fn.restype = ctypes.c_bool
except (AttributeError, OSError):
    _set_affinity_fn = None


def _set_affinity(hwnd: int, value: int) -> bool:
    """设窗口显示亲和性"""
    if _set_affinity_fn is None or not hwnd:
        return False
    try:
        return bool(_set_affinity_fn(ctypes.c_void_p(int(hwnd)), value))
    except OSError:
        return False


def register_own_window(hwnd: int) -> None:
    """登记自家窗口排除在截图外"""
    if not hwnd:
        return
    with _own_lock:
        _own_hwnds.add(int(hwnd))
    _set_affinity(int(hwnd), _WDA_EXCLUDEFROMCAPTURE)


def unregister_own_window(hwnd: int) -> None:
    """注销随生随灭的自家窗口 否则死句柄堆积被回收复用会误排除别家窗口"""
    if not hwnd:
        return
    with _own_lock:
        _own_hwnds.discard(int(hwnd))


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
    """定位要截的显示器"""
    try:
        win = gw.getActiveWindow()
        if win is not None and win.width > 0 and win.height > 0:
            rect = _monitor_rect_at(win.left + win.width // 2, win.top + win.height // 2)
            if rect is not None:
                return rect
    except Exception:
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
    rect = _monitor_rect_at(x, y)
    if rect is not None:
        _put_geom(rect)


def current_geom() -> tuple[int, int, int, int]:
    return _get_geom()


def set_geom(geom: tuple[int, int, int, int]) -> None:
    _put_geom(geom)


def _scale(w: int, h: int) -> float:
    """编码前的缩放系数"""
    long_edge = max(w, h)
    return min(1.0, _MAX_LONG_EDGE / long_edge) if long_edge else 1.0


def image_to_screen(ix: float, iy: float, geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """图像坐标转屏幕坐标"""
    ox, oy, ow, oh = geom if geom is not None else _get_geom()
    s = _scale(ow, oh) or 1.0  # 防除零
    return int(round(ox + ix / s)), int(round(oy + iy / s))


def screen_to_image(ax: float, ay: float, geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """屏幕坐标转图像坐标"""
    ox, oy, ow, oh = geom if geom is not None else _get_geom()
    s = _scale(ow, oh)
    return int(round((ax - ox) * s)), int(round((ay - oy) * s))


@dataclass
class Capture:

    png_bytes: bytes
    width: int
    height: int
    focus_title: str | None = None
    region: tuple[int, int, int, int] | None = None


def capture_screen(
    mode: str, include_self: bool = False, region: tuple[int, int, int, int] | None = None
) -> Capture:
    """截屏总入口 抓屏 掩蔽 裁剪 编码"""
    image = _grab(include_self)
    focus_title: str | None = None
    if mode == CAPTURE_WINDOW:
        image, focus_title = _mask_to_active_window(image)
    used: tuple[int, int, int, int] | None = None
    if region is not None:
        image, used = _crop_region(image, region)
    jpeg, enc_w, enc_h = _encode(image)
    return Capture(jpeg, enc_w, enc_h, focus_title, used)


def _crop_region(
    image: Image.Image, region: tuple[int, int, int, int]
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """按region裁图"""
    left, top, w, h = region
    if w <= 0 or h <= 0 or left < 0 or top < 0:
        raise ValueError("region 非法：left/top 不能为负、width/height 必须为正")
    s = _scale(image.width, image.height) or 1.0
    l, t = int(left / s), int(top / s)
    r, b = min(image.width, int((left + w) / s)), min(image.height, int((top + h) / s))  # 夹到原图边界
    if l >= r or t >= b:
        raise ValueError("region 超出屏幕、裁出来是空的——核对 left,top,width,height(图像像素)")
    # 回报实际裁到的尺寸
    return image.crop((l, t, r, b)), (left, top, int(round((r - l) * s)), int(round((b - t) * s)))


def grab_active() -> Image.Image:
    return grab_active_geom()[0]


def grab_active_geom() -> tuple[Image.Image, tuple[int, int, int, int]]:
    """抓活动显示器整屏带geom"""
    import mss  # 延迟导入

    geom = _active_monitor_rect()
    _put_geom(geom)  # 记到本线程 让随后本线程的点击坐标按这块屏换算
    ox, oy, ow, oh = geom
    with mss.mss() as sct:
        raw = sct.grab({"left": ox, "top": oy, "width": ow, "height": oh})
    return Image.frombytes("RGB", raw.size, raw.rgb), geom


def _grab(include_self: bool) -> Image.Image:
    """抓屏 include_self时临时放开自家窗口"""
    with _own_lock:
        hwnds = list(_own_hwnds)  # 拍快照再遍历 主线程此刻 add discard 都不撞 RuntimeError
    if not (include_self and hwnds):
        return grab_active()
    for hwnd in hwnds:
        _set_affinity(hwnd, _WDA_NONE)
    time.sleep(_RECOMPOSE_S)  # 等dwm重新合成
    try:
        return grab_active()
    finally:
        # 还原排除标志
        for hwnd in hwnds:
            _set_affinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)


def _mask_to_active_window(image: Image.Image) -> tuple[Image.Image, str | None]:
    """活动窗口外整屏涂黑"""
    ox, oy, _ow, _oh = _get_geom()
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
    """活动窗口在截图里的框"""
    try:
        window = gw.getActiveWindow()
    except Exception:
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
    """缩放并编码jpeg"""
    long_edge = max(image.width, image.height)
    if long_edge > _MAX_LONG_EDGE:
        scale = _MAX_LONG_EDGE / long_edge
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.BILINEAR,
        )
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
    return buffer.getvalue(), image.width, image.height


def to_data_url(jpeg_bytes: bytes) -> str:
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
