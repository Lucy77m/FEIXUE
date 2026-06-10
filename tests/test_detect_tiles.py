# 分块推理的切块布局（纯函数，不加载 ONNX 模型）。
from desktop_pet.eyes import detect


def _covers(tiles, w, h):
    step = 37
    for x in range(0, w, step):
        for y in range(0, h, step):
            if not any(l <= x < l + tw and t <= y < t + th for l, t, tw, th in tiles):
                return False
    return True


class TestTiles:
    def test_small_screen_no_tiling(self):
        assert detect._tiles(1280, 720) == []
        assert detect._tiles(640, 480) == []

    def test_1080p_splits_horizontally(self):
        tiles = detect._tiles(1920, 1080)
        assert len(tiles) == 2
        assert _covers(tiles, 1920, 1080)

    def test_4k_grid(self):
        tiles = detect._tiles(3840, 2160)
        assert len(tiles) == 6
        assert _covers(tiles, 3840, 2160)

    def test_tiles_stay_in_bounds(self):
        for w, h in [(1920, 1080), (2560, 1440), (3840, 2160), (5120, 1440)]:
            for l, t, tw, th in detect._tiles(w, h):
                assert l >= 0 and t >= 0 and l + tw <= w and t + th <= h
                assert tw > 0 and th > 0

    def test_max_tiles_budget(self):
        tiles = detect._tiles(10000, 10000, max_tiles=8)
        assert 1 < len(tiles) <= 8
        assert _covers(tiles, 10000, 10000)

    def test_adjacent_tiles_overlap(self):
        tiles = detect._tiles(2560, 1440)
        row0 = sorted([t for t in tiles if t[1] == 0], key=lambda t: t[0])
        assert len(row0) >= 2
        first, second = row0[0], row0[1]
        assert second[0] < first[0] + first[2]
