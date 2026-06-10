# 检测器 NMS 的纯函数测试（不加载 ONNX 模型）。
import numpy as np

from desktop_pet.eyes import detect


class TestNms:
    def test_suppresses_high_overlap_keeps_distant(self):
        boxes = np.array([
            [0.0, 0.0, 10.0, 10.0],
            [1.0, 1.0, 10.0, 10.0],
            [100.0, 100.0, 10.0, 10.0],
        ])
        scores = np.array([0.9, 0.8, 0.7])
        assert detect._nms(boxes, scores, 0.45) == [0, 2]

    def test_keeps_all_when_no_overlap(self):
        boxes = np.array([[0.0, 0.0, 5.0, 5.0], [50.0, 50.0, 5.0, 5.0], [200.0, 0.0, 5.0, 5.0]])
        scores = np.array([0.5, 0.9, 0.7])
        assert detect._nms(boxes, scores, 0.45) == [1, 2, 0]

    def test_single_box(self):
        assert detect._nms(np.array([[0.0, 0.0, 10.0, 10.0]]), np.array([0.9]), 0.45) == [0]
