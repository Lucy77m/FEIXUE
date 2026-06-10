# 幽灵鼠标（后台消息点击）：纯逻辑 + act_element 三档 mode 的分支行为。不投递真实消息。
import pytest

from desktop_pet.eyes import elements
from desktop_pet.hands import ghost, mouse


class TestPackLparam:
    def test_packs_xy(self):
        assert ghost._pack_lparam(10, 20) == (20 << 16) | 10
        assert ghost._pack_lparam(0, 0) == 0

    def test_masks_to_16_bits(self):
        assert ghost._pack_lparam(0x1FFFF, 0) == 0xFFFF
        assert ghost._pack_lparam(0, 0x10001) == (1 << 16)


class TestBgClickGuards:
    def test_rejects_null_and_invalid_hwnd(self):
        assert ghost.bg_click(0, 100, 100) is False
        assert ghost.bg_click(0xDEAD0001, 100, 100) is False


def _fake_element(**over):
    el = {
        "idx": 1, "source": "icon", "kind": "icon", "name": "播放",
        "rect_abs": (100, 100, 140, 140), "center_abs": (120, 120),
        "ctrl": None, "invokable": False, "hwnd": 12345,
    }
    el.update(over)
    return el


def _no_real_mouse(monkeypatch):
    monkeypatch.setattr(mouse, "click_screen", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("real mouse must not be used here")))


class TestActElementModes:
    def setup_method(self):
        elements._LAST[:] = [_fake_element()]

    def teardown_method(self):
        elements._LAST[:] = []

    @pytest.fixture(autouse=True)
    def _skip_real_verify(self, monkeypatch):
        monkeypatch.setattr(elements, "_verify_snapshot", lambda: None)


    def test_auto_prefers_ghost_and_skips_real_mouse(self, monkeypatch):
        posted = []
        monkeypatch.setattr(ghost, "bg_click", lambda h, x, y, k: posted.append((h, x, y, k)) or True)
        _no_real_mouse(monkeypatch)
        out = elements.act_element(1)
        assert posted == [(12345, 120, 120, "click")]
        assert "NOT moved" in out

    def test_auto_falls_back_to_real_mouse_when_delivery_fails(self, monkeypatch):
        monkeypatch.setattr(ghost, "bg_click", lambda *a: False)
        called = []
        monkeypatch.setattr(mouse, "click_screen", lambda x, y, k="click": called.append((x, y, k)) or True)
        out = elements.act_element(1, "right", mode="auto")
        assert called == [(120, 120, "right")]
        assert "right-clicked" in out


    def test_ghost_failure_never_touches_real_mouse(self, monkeypatch):
        monkeypatch.setattr(ghost, "bg_click", lambda *a: False)
        _no_real_mouse(monkeypatch)
        out = elements.act_element(1, "click", mode="ghost")
        assert "failed" in out and "mode=real" in out

    def test_ghost_type_without_value_pattern_refuses(self, monkeypatch):
        _no_real_mouse(monkeypatch)
        out = elements.act_element(1, "type", text="hello", mode="ghost")
        assert "ghost mode" in out and "mode=real" in out


    def test_real_skips_ghost_entirely(self, monkeypatch):
        monkeypatch.setattr(ghost, "bg_click", lambda *a: (_ for _ in ()).throw(
            AssertionError("ghost must not be tried in real mode")))
        called = []
        monkeypatch.setattr(mouse, "click_screen", lambda x, y, k="click": called.append((x, y, k)) or True)
        out = elements.act_element(1, "click", mode="real")
        assert called == [(120, 120, "click")]
        assert "clicked" in out

    def test_real_type_skips_accessibility_set_value(self, monkeypatch):
        from desktop_pet.eyes import uia
        monkeypatch.setattr(uia, "set_value", lambda *a: (_ for _ in ()).throw(
            AssertionError("set_value must not be tried in real mode")))
        clicked = []
        monkeypatch.setattr(mouse, "click_screen", lambda x, y, k="click": clicked.append((x, y)) or True)
        import desktop_pet.hands.keyboard as kb
        monkeypatch.setattr(kb, "press_keys", lambda *a: "")
        monkeypatch.setattr(kb, "type_text", lambda *a: "")
        elements._LAST[:] = [_fake_element(ctrl=object())]
        out = elements.act_element(1, "type", text="hi", mode="real")
        assert clicked == [(120, 120)]
        assert "typed" in out
