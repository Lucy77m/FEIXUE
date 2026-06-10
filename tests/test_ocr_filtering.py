# OCR 结果过滤与坐标偏移：用假引擎注入结果，不依赖 rapidocr 模型。
from desktop_pet.executor import vision


def _box(l, t, r, b):
    return [(l, t), (r, t), (r, b), (l, b)]


class FakeEngine:
    def __init__(self, results):
        self._results = results

    def __call__(self, _img):
        return self._results, None


class TestOcrBoxes:
    def test_filters_low_score_and_blank_text(self, monkeypatch):
        monkeypatch.setattr(vision, "_ocr_engine", FakeEngine([
            (_box(0, 0, 10, 10), "good", 0.9),
            (_box(20, 20, 30, 30), "noise", 0.2),
            (_box(40, 40, 50, 50), "   ", 0.99),
        ]))
        boxes = vision.ocr_boxes(None, ox=100, oy=200)
        assert [b["text"] for b in boxes] == ["good"]

    def test_applies_monitor_offset(self, monkeypatch):
        monkeypatch.setattr(vision, "_ocr_engine", FakeEngine([
            (_box(10, 20, 30, 40), "hi", 0.9),
        ]))
        (b,) = vision.ocr_boxes(None, ox=1000, oy=500)
        assert b["rect_abs"] == (1010, 520, 1030, 540)
        assert b["center_abs"] == (1020, 530)

    def test_unparseable_score_is_kept(self, monkeypatch):
        monkeypatch.setattr(vision, "_ocr_engine", FakeEngine([
            (_box(0, 0, 10, 10), "text", None),
        ]))
        assert len(vision.ocr_boxes(None, 0, 0)) == 1

    def test_empty_result(self, monkeypatch):
        monkeypatch.setattr(vision, "_ocr_engine", FakeEngine([]))
        assert vision.ocr_boxes(None, 0, 0) == []
