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
_RECOMPOSE_S = 0.06  # 撤掉排除标志后等 DWM 重新合成的间隔——太短会把自己拍进去，60ms 经验值够稳

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
    """给窗口设显示亲和性——拿它把自己标成"不进截图"。系统不支持/句柄无效时静默返回 False。"""
    if _set_affinity_fn is None or not hwnd:
        return False
    try:
        return bool(_set_affinity_fn(ctypes.c_void_p(int(hwnd)), value))
    except OSError:
        return False


def register_own_window(hwnd: int) -> None:
    """登记自家窗口(宠物/面板)——记下来好在 include_self 时临时放开，平时一律排除在截图外。"""
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
    """定位"该截哪块屏"：先按活动窗口中心 → 再退到鼠标位置 → 都不行才退主屏全尺寸。"""
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
    """编码前的缩放系数：长边超过 _MAX_LONG_EDGE(4K)才缩，否则原样 1.0。坐标换算靠它对齐。"""
    long_edge = max(w, h)
    return min(1.0, _MAX_LONG_EDGE / long_edge) if long_edge else 1.0


def image_to_screen(ix: float, iy: float, geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """模型给的图像像素坐标 → 真实屏幕坐标。必须跟截图时同一块屏(geom)，否则点偏到别的显示器。"""
    ox, oy, ow, oh = geom if geom is not None else _geom
    s = _scale(ow, oh) or 1.0  # s 可能为 0 时兜个 1.0，免得除零
    return int(round(ox + ix / s)), int(round(oy + iy / s))


def screen_to_image(ax: float, ay: float, geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """屏幕坐标 → 图像像素坐标，image_to_screen 的逆变换。"""
    ox, oy, ow, oh = geom if geom is not None else _geom
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
    """对外的一把抓：抓屏 → (窗口模式)只留活动窗口、其余涂黑 → (给了 region)裁剪 → 编码 JPEG。"""
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
    """按模型给的 region(图像像素坐标系)裁一块。region 是缩放后的坐标，要先除回 s 才对得上原图。"""
    left, top, w, h = region
    if w <= 0 or h <= 0 or left < 0 or top < 0:
        raise ValueError("region 非法：left/top 不能为负、width/height 必须为正")
    s = _scale(image.width, image.height) or 1.0
    l, t = int(left / s), int(top / s)
    r, b = min(image.width, int((left + w) / s)), min(image.height, int((top + h) / s))  # 夹到原图边界，越界不报错只截到边
    if l >= r or t >= b:
        raise ValueError("region 超出屏幕、裁出来是空的——核对 left,top,width,height(图像像素)")
    # 回报的尺寸用裁后实际像素 × s 折算——夹边后可能比请求的 w/h 小
    return image.crop((l, t, r, b)), (left, top, int(round((r - l) * s)), int(round((b - t) * s)))


def grab_active() -> Image.Image:
    return grab_active_geom()[0]


def grab_active_geom() -> tuple[Image.Image, tuple[int, int, int, int]]:
    """抓活动显示器整屏，连同它的 geom 一起返回——调用方做坐标换算要对上这块屏。"""
    import mss  # 延迟导入：mss 起 X/DC 资源，不抓屏时别让它进内存

    global _geom
    geom = _active_monitor_rect()
    _geom = geom
    ox, oy, ow, oh = geom
    with mss.mss() as sct:
        raw = sct.grab({"left": ox, "top": oy, "width": ow, "height": oh})
    return Image.frombytes("RGB", raw.size, raw.rgb), geom


def _grab(include_self: bool) -> Image.Image:
    """抓屏；include_self 时临时撤掉自家窗口的排除标志，让它能进画面，抓完 finally 里务必还原。"""
    if not (include_self and _own_hwnds):
        return grab_active()
    for hwnd in _own_hwnds:
        _set_affinity(hwnd, _WDA_NONE)
    time.sleep(_RECOMPOSE_S)  # 等 DWM 把窗口重新合成进去，否则刚撤标志就抓还是空的
    try:
        return grab_active()
    finally:
        # 不管抓没抓成都要把排除标志贴回去——漏了就会一直把自己拍进后续截图
        for hwnd in _own_hwnds:
            _set_affinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)


def _mask_to_active_window(image: Image.Image) -> tuple[Image.Image, str | None]:
    """窗口模式：除活动窗口那块外整屏涂黑，少喂无关画面给模型、也避免泄露别的窗口内容。"""
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
    """活动窗口在截图里的框(扣掉显示器原点 ox/oy、夹到图像边界)。窗口在屏外/取不到时返回 None。"""
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
    """缩到长边 ≤4K 再存 JPEG，返回(字节, 实际宽, 高)。返回的宽高要跟坐标换算用的 _scale 对齐。"""
    long_edge = max(image.width, image.height)
    if long_edge > _MAX_LONG_EDGE:
        scale = _MAX_LONG_EDGE / long_edge
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.BILINEAR,  # 双线性够用：缩图喂模型，不必上 LANCZOS 那点画质换不来识别提升
        )
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
    return buffer.getvalue(), image.width, image.height


def to_data_url(jpeg_bytes: bytes) -> str:
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
