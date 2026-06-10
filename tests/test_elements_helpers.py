# elements 融合层的纯函数测试：命中判断、图标找标签、屏幕指纹、操作后验证。
import numpy as np
from PIL import Image

from desktop_pet.eyes import elements


class TestInside:
    def test_center_and_edges_inclusive(self):
        rect = (0, 0, 10, 10)
        assert elements._inside((5, 5), rect)
        assert elements._inside((0, 0), rect)
        assert elements._inside((10, 10), rect)

    def test_outside(self):
        assert not elements._inside((11, 5), (0, 0, 10, 10))
        assert not elements._inside((5, -1), (0, 0, 10, 10))


def _ocr(text, rect):
    return {"text": text, "rect_abs": rect}


class TestLabelForIcon:
    ICON = (100, 100, 140, 140)

    def test_picks_caption_right_below(self):
        ocr = [_ocr("设置", (105, 145, 135, 160))]
        assert elements._label_for_icon(self.ICON, ocr) == "设置"

    def test_picks_text_inside_icon(self):
        ocr = [_ocr("OK", (110, 110, 130, 130))]
        assert elements._label_for_icon(self.ICON, ocr) == "OK"

    def test_rejects_horizontally_misaligned(self):
        ocr = [_ocr("别处", (160, 145, 200, 160))]
        assert elements._label_for_icon(self.ICON, ocr) == ""

    def test_rejects_too_far_below(self):
        ocr = [_ocr("太远", (105, 200, 135, 215))]
        assert elements._label_for_icon(self.ICON, ocr) == ""

    def test_prefers_closer_more_centered(self):
        ocr = [
            _ocr("偏的", (118, 145, 158, 160)),
            _ocr("正的", (105, 145, 135, 160)),
        ]
        assert elements._label_for_icon(self.ICON, ocr) == "正的"

    def test_degenerate_icon_rect(self):
        assert elements._label_for_icon((10, 10, 10, 30), [_ocr("x", (0, 0, 5, 5))]) == ""

    def test_label_capped_at_46_chars(self):
        long = "字" * 60
        ocr = [_ocr(long, (105, 145, 135, 160))]
        assert elements._label_for_icon(self.ICON, ocr) == long[:46]


class TestFingerprint:
    def test_fixed_size_and_sensitivity(self):
        img1 = Image.new("RGB", (1920, 1080), (30, 30, 30))
        img2 = Image.new("RGB", (1920, 1080), (200, 200, 200))
        fp1, fp2 = elements._fingerprint(img1), elements._fingerprint(img2)
        assert len(fp1) == 320 * 180
        assert fp1 != fp2
        assert fp1 == elements._fingerprint(Image.new("RGB", (1920, 1080), (30, 30, 30)))


class TestVerifyChanged:

    @staticmethod
    def _blank():
        return np.zeros((180, 320), dtype=np.int16)

    def test_big_change_is_true(self, monkeypatch):
        before = self._blank()
        after = before.copy()
        after[:90, :] = 200
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: after)
        assert elements._verify_changed(before) is True

    def test_tiny_change_is_false(self, monkeypatch):
        before = self._blank()
        after = before.copy()
        after[0:3, 0:3] = 200
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: after)
        assert elements._verify_changed(before) is False

    def test_no_change_is_false(self, monkeypatch):
        before = self._blank()
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: before.copy())
        assert elements._verify_changed(before) is False

    def test_snapshot_failure_is_none(self, monkeypatch):
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: None)
        assert elements._verify_changed(self._blank()) is None
        assert elements._verify_changed(None) is None

    def test_shape_mismatch_is_none(self, monkeypatch):
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: np.zeros((90, 160), dtype=np.int16))
        assert elements._verify_changed(self._blank()) is None
