# 把omniparser v2的icon_detect导出成ui_detect.onnx 构建期一次性脚本 产物上传github releases

from __future__ import annotations

import sys
from pathlib import Path

REPO = "microsoft/OmniParser-v2.0"
PT_IN_REPO = "icon_detect/model.pt"
IMGSZ = int(sys.argv[1]) if len(sys.argv) > 1 else 640
OUT = Path(__file__).resolve().parent / ("ui_detect.onnx" if IMGSZ == 640 else f"ui_detect_{IMGSZ}.onnx")


def main() -> int:
    from huggingface_hub import hf_hub_download

    print(f"[1/4] 下载 {REPO}::{PT_IN_REPO} …")
    pt_path = hf_hub_download(repo_id=REPO, filename=PT_IN_REPO)
    print("      ->", pt_path)

    print(f"[2/4] ultralytics 导出 ONNX (imgsz={IMGSZ}, raw output, 自带 NMS 关闭) …")
    from ultralytics import YOLO

    model = YOLO(pt_path)
    exported = model.export(format="onnx", imgsz=IMGSZ, opset=12, simplify=True, nms=False)
    Path(exported).replace(OUT)
    print("      ->", OUT, f"({OUT.stat().st_size/1e6:.1f} MB)")

    print("[3/4] 校验 I/O 契约是否与现役 ui_detect.onnx 一致 …")
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(str(OUT), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    out = sess.get_outputs()[0]
    print(f"      INPUT  {inp.name} {inp.shape}")
    print(f"      OUTPUT {out.name} {out.shape}")
    ish = inp.shape
    assert len(ish) == 4 and ish[1] == 3 and ish[2] == IMGSZ and ish[3] == IMGSZ, f"输入形状异常: {ish}"
    osh = out.shape
    assert len(osh) == 3 and osh[1] == 5, f"输出形状非单类 YOLOv8: {osh}（detect.py 仍能解码多类，但与现役不一致，请确认）"
    print("      ✓ 契约一致：单类 YOLOv8，[1,3,%d,%d] -> [1,5,N]" % (IMGSZ, IMGSZ))

    print("[4/4] 走 detect.py 的真实解码路径跑一遍（确认无损接入）…")
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    from PIL import Image, ImageDraw

    from desktop_pet.eyes import detect as det

    det._session = None
    det._disabled = False
    det._model_path = lambda: OUT
    img = Image.new("RGB", (1280, 800), (240, 240, 240))
    d = ImageDraw.Draw(img)
    for (x, y) in [(100, 100), (300, 200), (700, 500)]:
        d.rectangle((x, y, x + 120, y + 40), fill=(70, 130, 200), outline=(20, 20, 20), width=2)
        d.text((x + 12, y + 12), "OK", fill=(255, 255, 255))
    boxes = det.detect(img)
    assert isinstance(boxes, list), "detect() 没返回列表"
    for (l, t, r, b) in boxes:
        assert 0 <= l < r <= img.width and 0 <= t < b <= img.height, f"框越界: {(l, t, r, b)}"
    print(f"      ✓ 解码链路通过，合成图上检出 {len(boxes)} 个框（数量不重要，重在链路无异常、坐标合法）")
    print("      provider:", det.active_provider() or "(cpu)")

    print("\n完成。产物：", OUT)
    print("下一步：把它上传到 GitHub releases 替换 ui_detect.onnx；或本地放到 data/models/ 直接生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
