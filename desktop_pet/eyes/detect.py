# author: bdth
# email: 2074055628@qq.com
# 基于 ONNX 模型检测截图中的 UI 元素，返回边界框列表

from __future__ import annotations

import threading
from pathlib import Path

from desktop_pet.settings import DATA_DIR


_MODEL_URL = "https://github.com/dulaiduwang003/MOCHI/releases/download/models/ui_detect.onnx"


def _data_model() -> Path:
    return DATA_DIR / "models" / "ui_detect.onnx"


def _model_path():
    """先找随包发布的模型(源码/打包都在 eyes/models/)，再找数据目录下用户自备/下载的。"""
    for p in (Path(__file__).resolve().parent / "models" / "ui_detect.onnx", _data_model()):
        if p.exists():
            return p
    return None


def download(proxy: str = "", on_progress=None) -> str:
    """可选增强：下载 UI 元素检测模型到数据目录(可写)，下完检测器自动启用。
    返回 'ok' 或 '[失败:…]'。含网络，调用方放后台线程。on_progress(done,total) 报进度。"""
    from desktop_pet.settings import build_http_client

    target = _data_model()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        client = build_http_client(proxy)
        try:
            with client.stream("GET", _MODEL_URL, follow_redirects=True) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                tmp = target.with_name("ui_detect.onnx.part")
                done = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(65536):
                        f.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, total)
                tmp.replace(target)
        finally:
            client.close()
    except Exception as exc:
        return f"[失败: {str(exc)[:120]}]"
    global _session, _disabled
    _session, _disabled = None, False   # 重置缓存，让 _load 用新模型
    return "ok"


_CONF = 0.30
_IOU = 0.45
_MAX_DET = 120

_session = None
_input_name = ""
_imgsz = 640
_disabled = False
_lock = threading.Lock()


def available() -> bool:
    return _load() is not None


def _load():
    global _session, _input_name, _imgsz, _disabled
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

            sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            inp = sess.get_inputs()[0]
            _input_name = inp.name
            shape = inp.shape
            if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0:
                _imgsz = int(shape[2])
            _session = sess
            return _session
        except Exception:
            _disabled = True
            return None


def detect(pil_image) -> list[tuple[int, int, int, int]]:
    sess = _load()
    if sess is None:
        return []
    try:
        import numpy as np

        orig_w, orig_h = pil_image.width, pil_image.height
        scale = min(_imgsz / orig_w, _imgsz / orig_h)
        nw, nh = int(round(orig_w * scale)), int(round(orig_h * scale))
        resized = pil_image.convert("RGB").resize((nw, nh))
        canvas = np.full((_imgsz, _imgsz, 3), 114, dtype=np.uint8)
        px, py = (_imgsz - nw) // 2, (_imgsz - nh) // 2
        canvas[py : py + nh, px : px + nw] = np.array(resized)
        blob = canvas.astype(np.float32)[None].transpose(0, 3, 1, 2) / 255.0

        out = sess.run(None, {_input_name: blob})[0]
        pred = np.squeeze(out, 0)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T
        if pred.shape[1] < 5:
            return []
        scores = pred[:, 4:].max(axis=1)
        keep = scores >= _CONF
        pred, scores = pred[keep], scores[keep]
        if len(pred) == 0:
            return []
        cx, cy, w, h = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
        boxes = np.stack([cx - w / 2, cy - h / 2, w, h], axis=1)
        idxs = _nms(boxes, scores, _IOU)[:_MAX_DET]

        out_boxes: list[tuple[int, int, int, int]] = []
        for i in idxs:
            bx, by, bw, bh = boxes[i]
            l = (bx - px) / scale
            t = (by - py) / scale
            r = (bx + bw - px) / scale
            b = (by + bh - py) / scale
            l, t = max(0, int(l)), max(0, int(t))
            r, b = min(orig_w, int(r)), min(orig_h, int(b))
            if r - l >= 6 and b - t >= 6:
                out_boxes.append((l, t, r, b))
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
