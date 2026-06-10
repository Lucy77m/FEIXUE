# 鼠标坐标合法性判断：必须覆盖整个虚拟桌面（含负坐标副屏），不能只看主屏。
# 只测纯逻辑，不真正发送输入事件。
from desktop_pet.hands import mouse


def _fake_rect(left, top, w, h):
    return lambda: (left, top, w, h)


class TestOnscreen:
    def test_primary_only_layout(self, monkeypatch):
        monkeypatch.setattr(mouse, "_virtual_rect", _fake_rect(0, 0, 1920, 1080))
        assert mouse._onscreen(0, 0)
        assert mouse._onscreen(1919, 1079)
        assert not mouse._onscreen(1920, 500)
        assert not mouse._onscreen(-1, 500)

    def test_secondary_monitor_left_of_primary(self, monkeypatch):
        monkeypatch.setattr(mouse, "_virtual_rect", _fake_rect(-2560, 0, 2560 + 1920, 1440))
        assert mouse._onscreen(-2560, 0)
        assert mouse._onscreen(-100, 700)
        assert mouse._onscreen(1919, 1000)
        assert not mouse._onscreen(-2561, 0)
        assert not mouse._onscreen(4480, 0)

    def test_secondary_monitor_above_primary(self, monkeypatch):
        monkeypatch.setattr(mouse, "_virtual_rect", _fake_rect(0, -1440, 2560, 1440 + 1080))
        assert mouse._onscreen(100, -1440)
        assert mouse._onscreen(100, 1079)
        assert not mouse._onscreen(100, -1441)


class TestClickScreenBounds:
    def test_rejects_out_of_virtual_desktop(self, monkeypatch):
        monkeypatch.setattr(mouse, "_virtual_rect", _fake_rect(0, 0, 1920, 1080))
        sent = []
        monkeypatch.setattr(mouse, "_click_at", lambda *a, **k: sent.append(a))
        assert mouse.click_screen(99999, 99999) is False
        assert sent == []

    def test_accepts_negative_coords_on_left_monitor(self, monkeypatch):
        monkeypatch.setattr(mouse, "_virtual_rect", _fake_rect(-2560, 0, 4480, 1440))
        sent = []
        monkeypatch.setattr(mouse, "_click_at", lambda sx, sy, kind="click": sent.append((sx, sy, kind)))
        assert mouse.click_screen(-1000, 500, "right") is True
        assert sent == [(-1000, 500, "right")]


class TestScrollDataEncoding:
    def test_negative_amount_masked_to_dword(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(mouse, "_send", lambda flags, data=0: captured.update(flags=flags, data=data))
        mouse.scroll(-3)
        assert captured["flags"] == mouse._MOUSEEVENTF_WHEEL
        assert captured["data"] == -3 * mouse._WHEEL_DELTA
