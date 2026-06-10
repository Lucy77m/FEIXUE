# 坐标换算（图像像素 ↔ 绝对屏幕像素）：显式传 geom，不依赖全局状态。
import pytest

from desktop_pet.eyes import capture


class TestScale:
    def test_no_upscale_below_limit(self):
        assert capture._scale(2560, 1440) == 1.0
        assert capture._scale(3840, 2160) == 1.0

    def test_downscale_above_limit(self):
        assert capture._scale(7680, 2160) == pytest.approx(0.5)

    def test_zero_size_safe(self):
        assert capture._scale(0, 0) == 1.0


class TestConversions:
    GEOM_1X = (100, 50, 2560, 1440)
    GEOM_HALF = (-7680, 0, 7680, 2160)

    def test_screen_to_image_at_scale_1(self):
        assert capture.screen_to_image(101, 51, self.GEOM_1X) == (1, 1)
        assert capture.screen_to_image(100, 50, self.GEOM_1X) == (0, 0)

    def test_screen_to_image_downscaled(self):
        assert capture.screen_to_image(-7680 + 200, 100, self.GEOM_HALF) == (100, 50)

    def test_roundtrip_scale_1(self):
        for pt in [(0, 0), (123, 456), (2559, 1439)]:
            img = capture.screen_to_image(self.GEOM_1X[0] + pt[0], self.GEOM_1X[1] + pt[1], self.GEOM_1X)
            back = capture.image_to_screen(*img, self.GEOM_1X)
            assert back == (self.GEOM_1X[0] + pt[0], self.GEOM_1X[1] + pt[1])

    def test_roundtrip_downscaled_within_one_native_pixel(self):
        for sx, sy in [(-7680, 0), (-4000, 1000), (-1, 2159)]:
            ix, iy = capture.screen_to_image(sx, sy, self.GEOM_HALF)
            bx, by = capture.image_to_screen(ix, iy, self.GEOM_HALF)
            assert abs(bx - sx) <= 2 and abs(by - sy) <= 2

    def test_explicit_geom_ignores_global(self):
        saved = capture.current_geom()
        try:
            capture.set_geom((9999, 9999, 800, 600))
            assert capture.screen_to_image(101, 51, self.GEOM_1X) == (1, 1)
        finally:
            capture.set_geom(saved)


class TestCropRegion:

    @staticmethod
    def _img(w, h):
        from PIL import Image

        return Image.new("RGB", (w, h))

    def test_basic_crop_scale_1(self):
        out, used = capture._crop_region(self._img(1920, 1080), (100, 50, 200, 100))
        assert out.size == (200, 100)
        assert used == (100, 50, 200, 100)

    def test_clamps_to_screen_edge(self):
        out, used = capture._crop_region(self._img(1920, 1080), (1800, 1000, 500, 500))
        assert out.size == (120, 80)
        assert used == (1800, 1000, 120, 80)

    def test_downscaled_image_space_crops_native(self):
        out, used = capture._crop_region(self._img(7680, 2160), (100, 100, 200, 100))
        assert out.size == (400, 200)
        assert used == (100, 100, 200, 100)

    @pytest.mark.parametrize("region", [
        (-1, 0, 10, 10), (0, -5, 10, 10), (0, 0, 0, 10), (0, 0, 10, 0),
    ])
    def test_invalid_region_raises(self, region):
        with pytest.raises(ValueError):
            capture._crop_region(self._img(800, 600), region)

    def test_fully_outside_raises(self):
        with pytest.raises(ValueError):
            capture._crop_region(self._img(800, 600), (900, 0, 100, 100))
