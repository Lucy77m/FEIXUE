# author: bdth
# email: 2074055628@qq.com
# 屏幕视觉执行器：OCR 识别屏幕文字 + 纯 numpy FFT 模板图像匹配，返回可点击的中心坐标

from __future__ import annotations

import threading

_MAX_HITS = 60
_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_engine():
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    with _ocr_lock:
        if _ocr_engine is None:
            _ocr_engine = RapidOCR()
    return _ocr_engine


def prewarm() -> None:
    def _build() -> None:
        try:
            _get_engine()
        except Exception:
            pass

    threading.Thread(target=_build, daemon=True, name="ocr-prewarm").start()


def _screen_array():
    import numpy as np

    from desktop_pet.eyes.capture import grab_active

    rgb = np.array(grab_active())
    return rgb[:, :, ::-1].copy()


def ocr_screen(region: str = "") -> str:
    engine = _get_engine()
    if engine is None:
        return "[OCR unavailable: rapidocr-onnxruntime not installed]"

    img = _screen_array()
    from desktop_pet.eyes.capture import _scale, current_geom, screen_to_image

    mox, moy, mw, mh = current_geom()
    s = _scale(mw, mh) or 1.0
    ox, oy = 0, 0
    if region.strip():
        try:
            left, top, w, h = (int(v) for v in region.split(","))
        except (ValueError, IndexError):
            return "[region must be left,top,width,height (image pixels)]"
        if w <= 0 or h <= 0 or left < 0 or top < 0:
            return "[region 非法：left/top 不能为负、width/height 必须为正]"
        ox, oy = int(left / s), int(top / s)
        img = img[oy : oy + int(h / s), ox : ox + int(w / s)]
        if img.size == 0:
            return "[region 超出屏幕、裁出来是空的——核对 left,top,width,height(图像像素)]"

    result, _ = engine(img)
    if not result:
        return "(no text recognized)"
    lines = []
    for box, text, score in result[:_MAX_HITS]:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        nx = ox + sum(xs) / len(xs)
        ny = oy + sum(ys) / len(ys)
        cx, cy = screen_to_image(mox + nx, moy + ny)
        lines.append(f'"{text}"  @({cx}, {cy})')
    tail = f"\n…({len(result)} total, showing first {_MAX_HITS})" if len(result) > _MAX_HITS else ""
    return "On-screen text (with clickable center coordinates):\n" + "\n".join(lines) + tail


def ocr_boxes(bgr, ox: int, oy: int) -> list[dict]:
    engine = _get_engine()
    if engine is None:
        return []
    try:
        result, _ = engine(bgr)
    except Exception:
        return []
    boxes: list[dict] = []
    for box, text, score in result or []:
        text = (text or "").strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        l, t, r, b = min(xs), min(ys), max(xs), max(ys)
        boxes.append({
            "text": text,
            "rect_abs": (int(ox + l), int(oy + t), int(ox + r), int(oy + b)),
            "center_abs": (int(ox + (l + r) / 2), int(oy + (t + b) / 2)),
        })
    return boxes


def _to_gray(img) -> "object":
    import numpy as np

    return np.asarray(img.convert("L"), dtype=np.float64)


def _match_template_ncc(image, template) -> tuple[float, int, int]:
    """纯 numpy 归一化互相关，返回 (峰值相关度, 峰值左上角 x, 峰值左上角 y)。"""
    import numpy as np

    ih, iw = image.shape
    th, tw = template.shape
    n = th * tw
    t0 = template - template.mean()
    t_ss = float(np.sum(t0 * t0))
    if t_ss <= 1e-9:
        return 0.0, 0, 0

    fh, fw = ih + th - 1, iw + tw - 1
    ones = np.ones((th, tw))
    f_img = np.fft.rfft2(image, s=(fh, fw))
    f_img2 = np.fft.rfft2(image * image, s=(fh, fw))
    f_t0 = np.fft.rfft2(t0[::-1, ::-1], s=(fh, fw))
    f_ones = np.fft.rfft2(ones, s=(fh, fw))
    num_full = np.fft.irfft2(f_img * f_t0, s=(fh, fw))
    sum_full = np.fft.irfft2(f_img * f_ones, s=(fh, fw))
    sqsum_full = np.fft.irfft2(f_img2 * f_ones, s=(fh, fw))

    ys, xs = slice(th - 1, ih), slice(tw - 1, iw)
    num = num_full[ys, xs]
    local_sum = sum_full[ys, xs]
    local_sqsum = sqsum_full[ys, xs]

    var = np.maximum(local_sqsum - local_sum * local_sum / n, 0.0)
    denom = np.sqrt(var * t_ss)
    ncc = np.zeros_like(num)
    nz = denom > 1e-9
    ncc[nz] = num[nz] / denom[nz]

    idx = int(np.argmax(ncc))
    py, px = divmod(idx, ncc.shape[1])
    return float(ncc[py, px]), int(px), int(py)


def find_on_screen(template_path: str, confidence: float = 0.8) -> str:
    import os

    if not os.path.isfile(template_path):
        return f"[template image not found: {template_path}]"
    try:
        import numpy  # noqa: F401
        from PIL import Image
    except ImportError:
        return "[find-on-screen unavailable: numpy / Pillow not installed]"
    from desktop_pet.eyes.capture import current_geom, grab_active, screen_to_image

    try:
        template = _to_gray(Image.open(template_path))
    except Exception:
        return f"[couldn't read the template image (unsupported format?): {template_path}]"
    screen = _to_gray(grab_active())
    th, tw = template.shape
    if th > screen.shape[0] or tw > screen.shape[1]:
        return "[template is larger than the screen — can't match]"

    score, px, py = _match_template_ncc(screen, template)
    if score < float(confidence):
        return f"[not found on screen (best match {score:.2f} < threshold {confidence}) — use a clearer template or lower confidence]"
    mox, moy, _mw, _mh = current_geom()
    cx, cy = screen_to_image(mox + px + tw / 2, moy + py + th / 2)
    return f"Found it, match {score:.2f}, center @({cx}, {cy}) — click it directly."
