# author: bdth
# email: 2074055628@qq.com
# computer-use 路径的逻辑层测试 坐标变换 幽灵点击 lparam 打包 点在元素框内判定 web 搜索降级链
# 真鼠标 UIA 网络在 CI 测不到 这些纯逻辑能测

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("STAR_DATA_DIR", tempfile.mkdtemp(prefix="mochi_cu_"))

import pytest  # noqa: E402

from desktop_pet.eyes import capture  # noqa: E402
from desktop_pet.eyes import elements  # noqa: E402
from desktop_pet.executor import web  # noqa: E402
from desktop_pet.hands import ghost  # noqa: E402


# ---------- 坐标变换 截图坐标和屏幕坐标 ----------

def test_scale_no_downscale_when_within_cap():
    # 长边不超 _MAX_LONG_EDGE 就 1 1
    assert capture._scale(1920, 1080) == 1.0
    assert capture._scale(capture._MAX_LONG_EDGE, 100) == 1.0


def test_scale_downscales_oversized():
    big = capture._MAX_LONG_EDGE * 2
    assert capture._scale(big, 100) == pytest.approx(0.5)


def test_scale_zero_safe():
    assert capture._scale(0, 0) == 1.0  # 不除零


def test_image_to_screen_identity_when_unscaled():
    geom = (0, 0, 1920, 1080)  # s=1.0
    assert capture.image_to_screen(100, 200, geom) == (100, 200)


def test_image_to_screen_applies_monitor_offset():
    geom = (1920, 0, 1920, 1080)  # 副屏 原点偏右
    assert capture.image_to_screen(50, 60, geom) == (1970, 60)


def test_image_to_screen_undoes_downscale():
    geom = (0, 0, capture._MAX_LONG_EDGE * 2, 1000)  # s=0.5 屏幕坐标是图像坐标的 2 倍
    assert capture.image_to_screen(100, 200, geom) == (200, 400)


def test_screen_image_roundtrip():
    # 屏幕图像屏幕往返 应回到原点附近 取整误差不超过1
    for geom in [(0, 0, 1920, 1080), (1920, 0, 2560, 1440), (0, 0, capture._MAX_LONG_EDGE * 3, 2000)]:
        for sx, sy in [(geom[0] + 10, geom[1] + 10), (geom[0] + geom[2] - 5, geom[1] + geom[3] - 5)]:
            ix, iy = capture.screen_to_image(sx, sy, geom)
            bx, by = capture.image_to_screen(ix, iy, geom)
            assert abs(bx - sx) <= 1 and abs(by - sy) <= 1, (geom, sx, sy, bx, by)


# ---------- 幽灵点击 坐标打进 lParam 的低高字 ----------

def test_pack_lparam_low_high_words():
    lp = ghost._pack_lparam(10, 20)
    assert lp & 0xFFFF == 10            # 低字=x
    assert (lp >> 16) & 0xFFFF == 20    # 高字=y


def test_pack_lparam_zero_and_max():
    assert ghost._pack_lparam(0, 0) == 0
    assert ghost._pack_lparam(0xFFFF, 0xFFFF) == 0xFFFFFFFF


def test_pack_lparam_negative_wraps_16bit():
    assert ghost._pack_lparam(-1, -1) == 0xFFFFFFFF  # -1 变 0xFFFF 双字


# ---------- 点是否落在元素框 left top right bottom 内 ----------

def test_inside_rect():
    rect = (10, 20, 110, 70)
    assert elements._inside((10, 20), rect)      # 左上角闭区间
    assert elements._inside((110, 70), rect)     # 右下角
    assert elements._inside((60, 45), rect)      # 正中
    assert not elements._inside((9, 45), rect)   # 左外
    assert not elements._inside((60, 71), rect)  # 下外


# ---------- web 搜索降级链 一家抛或空就换下一家 ----------

def _backends(monkeypatch, spec):
    """造一组假后端"""
    def make(beh):
        def fn(q, n):
            if beh == "throw":
                raise RuntimeError("boom")
            return list(beh)
        return fn
    monkeypatch.setattr(web, "_SEARCH_BACKENDS", tuple((nm, make(b)) for nm, b in spec))


def test_search_falls_through_to_working_backend(monkeypatch):
    hit = [{"title": "T", "url": "u", "body": "b"}]
    _backends(monkeypatch, [("a", "throw"), ("b", []), ("c", hit)])
    out = web.web_search("q")
    assert "(via c)" in out and "T" in out      # 跳过抛错和空结果 用了 c


def test_search_uses_first_with_results(monkeypatch):
    h1 = [{"title": "first", "url": "u1", "body": ""}]
    h2 = [{"title": "second", "url": "u2", "body": ""}]
    _backends(monkeypatch, [("a", h1), ("b", h2)])
    out = web.web_search("q")
    assert "(via a)" in out and "first" in out and "second" not in out


def test_search_all_fail_reports_errors(monkeypatch):
    _backends(monkeypatch, [("a", "throw"), ("b", "throw")])
    out = web.web_search("q")
    assert "failed on all engines" in out and "a:" in out and "b:" in out


def test_search_empty_query():
    assert "no search query" in web.web_search("   ")
