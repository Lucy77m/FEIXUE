# author: bdth
# email: 2074055628@qq.com
# onnx模型检测截图里的ui元素

from __future__ import annotations

import threading
from pathlib import Path

from desktop_pet.settings import DATA_DIR


_MODEL_URL = "https://github.com/dulaiduwang003/MOCHI/releases/download/models/ui_detect.onnx"


def _data_model() -> Path:
    return DATA_DIR / "models" / "ui_detect.onnx"


def _model_path():
    """找模型路径"""
    for p in (Path(__file__).resolve().parent / "models" / "ui_detect.onnx", _data_model()):
        if p.exists():
            return p
    return None


def download(proxy: str = "", on_progress=None, should_cancel=None) -> str:
    """下载ui检测模型"""
    from desktop_pet.settings import build_http_client

    target = _data_model()
    tmp = target.with_name("ui_detect.onnx.part")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        client = build_http_client(proxy)
        try:
            with client.stream("GET", _MODEL_URL, follow_redirects=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                done = 0
                cancelled = False
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(65536):
                        if should_cancel is not None and should_cancel():
                            cancelled = True
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, total)
                if cancelled:
                    tmp.unlink(missing_ok=True)
                    return "cancelled"
                tmp.replace(target)
        finally:
            client.close()
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return f"[失败: {str(exc)[:120]}]"
    global _session, _disabled
    _session, _disabled = None, False   # 重置缓存
    return "ok"


_CONF = 0.30
_IOU = 0.45
_MAX_DET = 120

_session = None
_input_name = ""
_imgsz = 640
_disabled = False
_active_provider = ""
_lock = threading.Lock()


def active_provider() -> str:
    return _active_provider


def available() -> bool:
    return _load() is not None


def _load():
    global _session, _input_name, _imgsz, _disabled, _active_provider
    if _session is not None:
        return _session
    path = _model_path()
    if _disabled or path is None:
        return None
    with _lock:
        if _session is not None:
            return _session
        try:
            import onnxruntime as ort

            # dml优先 cpu兜底
            sess = ort.InferenceSession(str(path), providers=["DmlExecutionProvider", "CPUExecutionProvider"])
            _active_provider = (sess.get_providers() or [""])[0]   # 实际命中的provider
            inp = sess.get_inputs()[0]
            _input_name = inp.name
            shape = inp.shape
            if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0:
                _imgsz = int(shape[2])
            _session = sess
            return _session
        except Exception:
            _disabled = True   # 起不来直接禁用
            return None


_TILE_LONG = 1280
_TILE_OVERLAP = 96
_MAX_TILES = 8


def _tiles(w: int, h: int, max_tiles: int = _MAX_TILES) -> list[tuple[int, int, int, int]]:
    """把全屏切成带重叠的块"""
    import math

    nx, ny = math.ceil(w / _TILE_LONG), math.ceil(h / _TILE_LONG)
    if nx * ny <= 1:
        return []
    # 超过上限从长边减
    while nx * ny > max_tiles:
        if nx >= ny:
            nx -= 1
        else:
            ny -= 1
    if nx * ny <= 1:
        return []
    tw, th = math.ceil(w / nx), math.ceil(h / ny)
    out: list[tuple[int, int, int, int]] = []
    for j in range(ny):
        for i in range(nx):
            l = max(0, i * tw - _TILE_OVERLAP)
            t = max(0, j * th - _TILE_OVERLAP)
            r = min(w, (i + 1) * tw + _TILE_OVERLAP)
            b = min(h, (j + 1) * th + _TILE_OVERLAP)
            out.append((l, t, r - l, b - t))
    return out


def _infer(sess, pil_img, off_x: int, off_y: int) -> tuple[list[tuple[float, float, float, float]], list[float]]:
    """单图跑一遍模型返回boxes和scores"""
    import numpy as np
    from PIL import Image

    orig_w, orig_h = pil_img.width, pil_img.height
    scale = min(_imgsz / orig_w, _imgsz / orig_h)
    nw, nh = max(1, int(round(orig_w * scale))), max(1, int(round(orig_h * scale)))
    resized = pil_img.convert("RGB").resize((nw, nh), Image.Resampling.BILINEAR)
    canvas = np.full((_imgsz, _imgsz, 3), 114, dtype=np.uint8)
    px, py = (_imgsz - nw) // 2, (_imgsz - nh) // 2
    canvas[py : py + nh, px : px + nw] = np.array(resized)
    blob = canvas.astype(np.float32)[None].transpose(0, 3, 1, 2) / 255.0

    out = sess.run(None, {_input_name: blob})[0]
    pred = np.squeeze(out, 0)
    if pred.shape[0] < pred.shape[1]:
        pred = pred.T   # 统一成每行一个框
    if pred.shape[1] < 5:
        return [], []
    scores = pred[:, 4:].max(axis=1)
    keep = scores >= _CONF
    pred, scores = pred[keep], scores[keep]
    boxes: list[tuple[float, float, float, float]] = []
    for cx, cy, bw, bh in pred[:, :4]:
        l = max(0.0, (cx - bw / 2 - px) / scale) + off_x
        t = max(0.0, (cy - bh / 2 - py) / scale) + off_y
        r = min(float(orig_w), (cx + bw / 2 - px) / scale) + off_x
        b = min(float(orig_h), (cy + bh / 2 - py) / scale) + off_y
        boxes.append((l, t, r, b))
    return boxes, [float(s) for s in scores]


def detect(pil_image) -> list[tuple[int, int, int, int]]:
    """检测可点元素返回框列表"""
    sess = _load()
    if sess is None:
        return []
    try:
        import numpy as np

        w, h = pil_image.width, pil_image.height
        boxes, scores = _infer(sess, pil_image, 0, 0)   # 先全图一遍
        # 再切块细看小图标 cpu时减块数
        max_tiles = _MAX_TILES if "Dml" in _active_provider else 4
        for tl, tt, tw, th in _tiles(w, h, max_tiles):
            tile_boxes, tile_scores = _infer(sess, pil_image.crop((tl, tt, tl + tw, tt + th)), tl, tt)
            boxes += tile_boxes
            scores += tile_scores
        if not boxes:
            return []
        # 统一nms去重
        arr = np.array([[l, t, r - l, b - t] for l, t, r, b in boxes])
        idxs = _nms(arr, np.array(scores), _IOU)[:_MAX_DET]
        out_boxes: list[tuple[int, int, int, int]] = []
        for i in idxs:
            l, t, r, b = boxes[i]
            if r - l >= 6 and b - t >= 6:   # 太小的当噪声丢掉
                out_boxes.append((int(l), int(t), int(r), int(b)))
        return out_boxes
    except Exception:
        return []


def _nms(boxes, scores, iou_thresh: float):
    import numpy as np

    x1, y1 = boxes[:, 0], boxes[:, 1]
    x2, y2 = boxes[:, 0] + boxes[:, 2], boxes[:, 1] + boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][ovr <= iou_thresh]
    return keep
