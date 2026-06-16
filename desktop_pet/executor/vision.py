# author: bdth
# email: 2074055628@qq.com
# 屏幕视觉执行器 ocr 识别屏幕文字和 fft 模板匹配 返回可点中心坐标

from __future__ import annotations

import threading

_MAX_HITS = 60
_OCR_MAX_SIDE = 3200
_MIN_OCR_SCORE = 0.5
_ocr_engine = None
_ocr_lock = threading.Lock()
# 推理串行化:同一个 RapidOCR 实例被 worker 线程(ocr_screen)和入库 daemon 线程(ocr_boxes 来自 PDF OCR)同时调
# 并发 __call__ 会让结果错乱或抛异常(被吞成空结果 喂进库的文档丢字)。OCR 本就是瓶颈 串行无妨
_infer_lock = threading.Lock()


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
            # 三个子模型都走 directml 起不来自动回落 cpu max_side_len 限长边
            _ocr_engine = RapidOCR(
                max_side_len=_OCR_MAX_SIDE,
                det_use_dml=True, cls_use_dml=True, rec_use_dml=True,
            )
    return _ocr_engine


def prewarm() -> None:
    """后台线程预热 ocr 引擎"""
    def _build() -> None:
        try:
            _get_engine()
        except Exception:
            pass

    threading.Thread(target=_build, daemon=True, name="ocr-prewarm").start()


def _score_of(value) -> float:
    # score 转不动就当 1.0 放行
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0


def _screen_array():
    import numpy as np

    from desktop_pet.eyes.capture import grab_active_geom

    img, geom = grab_active_geom()
    rgb = np.array(img)
    # geom 跟同一帧一起带出去
    return rgb[:, :, ::-1].copy(), geom  # rgb 转 bgr rapidocr 吃 bgr


def ocr_screen(region: str = "") -> str:
    """ocr 当前活动窗口 带可点中心坐标 region 可裁一块再认"""
    engine = _get_engine()
    if engine is None:
        return "[OCR unavailable: rapidocr-onnxruntime not installed]"

    img, geom = _screen_array()
    from desktop_pet.eyes.capture import _scale, screen_to_image

    mox, moy, mw, mh = geom
    # region 先除 s 换回 img 坐标系再裁
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

    with _infer_lock:  # 和入库 daemon 的 OCR 串行 别并发用同一个引擎
        result, _ = engine(img)
    # 滤掉低置信结果
    result = [r for r in (result or []) if _score_of(r[2]) >= _MIN_OCR_SCORE]
    if not result:
        return "(no text recognized)"
    lines = []
    for box, text, score in result[:_MAX_HITS]:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        # 四点均值当中心 补回 region 偏移
        nx = ox + sum(xs) / len(xs)
        ny = oy + sum(ys) / len(ys)
        cx, cy = screen_to_image(mox + nx, moy + ny, geom)
        lines.append(f'"{text}"  @({cx}, {cy})')
    tail = f"\n…({len(result)} total, showing first {_MAX_HITS})" if len(result) > _MAX_HITS else ""
    return "On-screen text (with clickable center coordinates):\n" + "\n".join(lines) + tail


def ocr_boxes(bgr, ox: int, oy: int) -> list[dict]:
    """对一块 bgr 图跑 ocr 返回绝对坐标矩形和中心点"""
    engine = _get_engine()
    if engine is None:
        return []
    try:
        with _infer_lock:  # 同上 和 worker 线程的截图 OCR 串行
            result, _ = engine(bgr)
    except Exception:
        return []
    boxes: list[dict] = []
    for box, text, score in result or []:
        text = (text or "").strip()
        if not text or _score_of(score) < _MIN_OCR_SCORE:
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


# 整屏先缩到长边 1366 再算 fft
_WORK_LONG_EDGE = 1366
# 多档缩放各试一遍取最高
_FIND_SCALES = (0.7, 0.85, 1.0, 1.18, 1.4)
_MIN_TMPL_SIDE = 24       # 缩完模板短边下限 再小触发提分
_WORK_BOOST_MAX = 2400    # 提分时工作图长边上限


def _gray_pil(img, size=None):
    import numpy as np
    from PIL import Image

    im = img.convert("L")
    if size is not None:
        im = im.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float64)


def _grad_mag(arr):
    """梯度幅值边缘图"""
    import numpy as np

    gx = np.zeros_like(arr)
    gy = np.zeros_like(arr)
    # 中央差分 边缘一圈留 0
    gx[:, 1:-1] = arr[:, 2:] - arr[:, :-2]
    gy[1:-1, :] = arr[2:, :] - arr[:-2, :]
    return np.sqrt(gx * gx + gy * gy)


def _combine_ncc(a, b):
    # 两路 ncc 逐点取大 任一为空用另一条
    if a is None:
        return b
    if b is None:
        return a
    import numpy as np

    return np.maximum(a, b)


def _ncc_map(image, template):
    """numpy fft 算归一化互相关 返回整张相关度图"""
    import numpy as np

    ih, iw = image.shape
    th, tw = template.shape
    n = th * tw
    t0 = template - template.mean()
    t_ss = float(np.sum(t0 * t0))
    if t_ss <= 1e-9:   # 模板纯色直接放弃
        return None

    # 线性卷积尺寸 防循环卷积绕回
    fh, fw = ih + th - 1, iw + tw - 1
    ones = np.ones((th, tw))
    f_img = np.fft.rfft2(image, s=(fh, fw))
    f_img2 = np.fft.rfft2(image * image, s=(fh, fw))   # 算窗口局部方差用
    f_t0 = np.fft.rfft2(t0[::-1, ::-1], s=(fh, fw))     # 模板翻转 卷积变互相关
    f_ones = np.fft.rfft2(ones, s=(fh, fw))             # 全 1 核做盒式求和
    num_full = np.fft.irfft2(f_img * f_t0, s=(fh, fw))
    sum_full = np.fft.irfft2(f_img * f_ones, s=(fh, fw))
    sqsum_full = np.fft.irfft2(f_img2 * f_ones, s=(fh, fw))

    # 切掉前导偏移 留模板完整覆盖的有效区域
    ys, xs = slice(th - 1, ih), slice(tw - 1, iw)
    num = num_full[ys, xs]
    local_sum = sum_full[ys, xs]
    local_sqsum = sqsum_full[ys, xs]

    # 方差 clip 到 0 防 sqrt 出 nan
    var = np.maximum(local_sqsum - local_sum * local_sum / n, 0.0)
    denom = np.sqrt(var * t_ss)
    ncc = np.zeros_like(num)
    nz = denom > 1e-9          # 分母接近 0 的点不算留 0
    ncc[nz] = num[nz] / denom[nz]
    return ncc


def _peaks(ncc, thresh: float, tw: int, th: int, max_hits: int = 12):
    """反复挑最高峰做非极大抑制"""
    import numpy as np

    work = ncc.copy()   # 别动传进来的原图
    out = []
    while len(out) < max_hits:
        idx = int(np.argmax(work))
        py, px = divmod(idx, work.shape[1])
        score = float(work[py, px])
        if score < thresh:
            break
        out.append((score, px, py))
        # 峰区涂成 -1 防重复命中
        work[max(0, py - th // 2): py + th // 2 + 1, max(0, px - tw // 2): px + tw // 2 + 1] = -1.0
    return out


def find_on_screen(template_path: str, confidence: float = 0.8) -> str:
    """拿模板图在当前屏上找 命中回可点中心坐标"""
    import os

    if not os.path.isfile(template_path):
        return f"[template image not found: {template_path}]"
    import importlib.util
    # 只查 spec 不真 import
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("PIL") is None:
        return "[find-on-screen unavailable: numpy / Pillow not installed]"
    from PIL import Image

    from desktop_pet.eyes.capture import grab_active_geom, screen_to_image

    try:
        tmpl_pil = Image.open(template_path)
        tw0, th0 = tmpl_pil.size
    except Exception:
        return f"[couldn't read the template image (unsupported format?): {template_path}]"
    screen_pil, geom = grab_active_geom()
    sw0, sh0 = screen_pil.size
    if th0 > sh0 or tw0 > sw0:
        return "[template is larger than the screen — can't match]"

    conf = float(confidence)
    # wf 工作缩放比 整屏压到长边 1366 提速
    wf = min(1.0, _WORK_LONG_EDGE / max(sw0, sh0))
    # 模板太小就放大工作图撑回最小可用尺寸
    if min(tw0, th0) * wf < _MIN_TMPL_SIDE:
        wf = min(1.0, _WORK_BOOST_MAX / max(sw0, sh0), _MIN_TMPL_SIDE / min(tw0, th0))
    screen = _gray_pil(screen_pil, (max(1, round(sw0 * wf)), max(1, round(sh0 * wf))))
    screen_g = _grad_mag(screen)
    sh, sw = screen.shape
    mox, moy, _mw, _mh = geom

    raw: list[tuple[float, float, float]] = []
    best_seen = 0.0
    textured = False
    for sc in _FIND_SCALES:
        tw, th = int(round(tw0 * wf * sc)), int(round(th0 * wf * sc))
        if tw < 8 or th < 8 or th > sh or tw > sw:   # 太小或比屏大这档跳过
            continue
        tmpl_gray = _gray_pil(tmpl_pil, (tw, th))
        ncc = _combine_ncc(_ncc_map(screen, tmpl_gray), _ncc_map(screen_g, _grad_mag(tmpl_gray)))
        if ncc is None:
            continue
        textured = True   # 有一档算出有效相关图
        best_seen = max(best_seen, float(ncc.max()))
        # 工作图坐标还原成屏幕像素中心
        for score, px, py in _peaks(ncc, conf, tw, th):
            raw.append((score, mox + (px + tw / 2) / wf, moy + (py + th / 2) / wf))
    # 全部尺度无效就是模板纯色
    if not textured:
        return "[template has no texture/contrast to match against — use a more distinctive image]"

    # 跨尺度去重 高分优先 离太近的丢掉
    raw.sort(key=lambda r: -r[0])
    radius2 = (0.4 * min(tw0, th0)) ** 2   # 比距离平方省开方
    kept: list[tuple[float, float, float]] = []
    for score, ax, ay in raw:
        if any((ax - kx) ** 2 + (ay - ky) ** 2 < radius2 for _, kx, ky in kept):
            continue
        kept.append((score, ax, ay))
        if len(kept) >= 8:   # 最多回 8 个
            break

    if not kept:
        return (f"[not found on screen (best match {best_seen:.2f} < threshold {conf}) "
                "— use a clearer template or lower confidence]")
    # 屏幕绝对坐标换回逻辑像素
    coords = [(s, *screen_to_image(ax, ay, geom)) for s, ax, ay in kept]
    if len(coords) == 1:
        s, cx, cy = coords[0]
        return f"Found it, match {s:.2f}, center @({cx}, {cy}) — click it directly."
    body = "\n".join(f"· match {s:.2f} @({cx}, {cy})" for s, cx, cy in coords)
    return f"Found {len(coords)} matches (best first; click the one you want):\n" + body
