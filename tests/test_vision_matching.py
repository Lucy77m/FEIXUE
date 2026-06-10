# 模板匹配核心（纯 numpy NCC + 峰值抑制）的回归测试：全部是纯函数，不碰真实屏幕。
import numpy as np
import pytest

from desktop_pet.executor import vision


@pytest.fixture()
def rng():
    return np.random.default_rng(42)


class TestNccMap:
    def test_finds_embedded_template_at_exact_position(self, rng):
        image = rng.uniform(0, 255, size=(100, 120))
        template = image[30:50, 40:64].copy()
        ncc = vision._ncc_map(image, template)
        assert ncc is not None
        py, px = divmod(int(np.argmax(ncc)), ncc.shape[1])
        assert (py, px) == (30, 40)
        assert ncc[py, px] == pytest.approx(1.0, abs=1e-6)

    def test_flat_template_returns_none(self, rng):
        image = rng.uniform(0, 255, size=(60, 60))
        template = np.full((10, 10), 128.0)
        assert vision._ncc_map(image, template) is None

    def test_no_match_scores_below_one(self, rng):
        image = rng.uniform(0, 255, size=(80, 80))
        template = rng.uniform(0, 255, size=(16, 16))
        ncc = vision._ncc_map(image, template)
        assert ncc is not None
        assert float(ncc.max()) < 0.9


class TestPeaks:
    def test_suppresses_neighbors_keeps_distant_peaks(self):
        ncc = np.zeros((50, 50))
        ncc[10, 20] = 0.95
        ncc[12, 22] = 0.93
        ncc[40, 40] = 0.90
        peaks = vision._peaks(ncc, 0.8, tw=10, th=10)
        assert [(px, py) for _s, px, py in peaks] == [(20, 10), (40, 40)]
        assert peaks[0][0] == pytest.approx(0.95)

    def test_threshold_filters_low_scores(self):
        ncc = np.zeros((30, 30))
        ncc[5, 5] = 0.7
        assert vision._peaks(ncc, 0.8, tw=8, th=8) == []

    def test_max_hits_cap(self):
        ncc = np.zeros((100, 100))
        for i in range(20):
            ncc[(i * 5) % 100, (i * 23) % 100] = 0.9
        assert len(vision._peaks(ncc, 0.5, tw=2, th=2, max_hits=12)) <= 12


class TestGradientMatch:

    def test_grad_mag_invariant_to_offset_and_inversion(self, rng):
        a = rng.uniform(0, 255, size=(24, 24))
        assert np.allclose(vision._grad_mag(a + 50), vision._grad_mag(a))
        assert np.allclose(vision._grad_mag(255.0 - a), vision._grad_mag(a))

    def test_combine_handles_none_and_takes_max(self):
        a = np.array([[0.5, 0.2]])
        b = np.array([[0.1, 0.9]])
        assert vision._combine_ncc(None, a) is a
        assert vision._combine_ncc(a, None) is a
        assert vision._combine_ncc(None, None) is None
        assert vision._combine_ncc(a, b).tolist() == [[0.5, 0.9]]

    def test_gradient_finds_inverted_region_where_intensity_fails(self, rng):
        img = rng.uniform(0, 255, size=(80, 90))
        tmpl = img[20:44, 30:58].copy()
        themed = img.copy()
        themed[20:44, 30:58] = 255.0 - themed[20:44, 30:58]

        ncc_i = vision._ncc_map(themed, tmpl)
        ncc_g = vision._ncc_map(vision._grad_mag(themed), vision._grad_mag(tmpl))
        yg, xg = divmod(int(np.argmax(ncc_g)), ncc_g.shape[1])
        assert (yg, xg) == (20, 30)
        assert ncc_g[20, 30] > 0.8
        assert ncc_i[20, 30] < 0.5
        combined = vision._combine_ncc(ncc_i, ncc_g)
        assert combined[20, 30] == ncc_g[20, 30]


class TestScoreOf:
    @pytest.mark.parametrize("raw, expected", [
        (0.83, 0.83),
        ("0.5", 0.5),
        (None, 1.0),
        ("n/a", 1.0),
    ])
    def test_parses_or_defaults(self, raw, expected):
        assert vision._score_of(raw) == pytest.approx(expected)
