import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet.pet.character import BlobPet
from desktop_pet.pet.sprite_skin import (
    CELL_HEIGHT,
    CELL_WIDTH,
    PERFORMANCE_ATLAS_HEIGHT,
    PERFORMANCE_ROWS,
    PRIORITY_IDLE_ACTION,
    SPRITE_ROWS,
    SpriteAtlasSkin,
    SpritePetController,
)
from desktop_pet.pet.window import PET_SCALE_PRESETS, PetWindow
from desktop_pet.pet.tray import Tray
from desktop_pet.app.agent_bridge import AgentBridgeMixin


def test_xiaofeixue_skin_loads_fixed_codex_atlas():
    skin = SpriteAtlasSkin("xiaofeixue")

    assert skin.available, skin.error
    assert skin.atlas_size == (1536, 1872)
    assert skin.cell_size == (192, 208)


def test_sprite_skin_crops_all_first_frames():
    skin = SpriteAtlasSkin("xiaofeixue")

    for state in SPRITE_ROWS:
        rect = skin.frame_rect(state, 0.0)
        pixmap = skin.frame_pixmap(state, 0.0)
        assert rect.width() == CELL_WIDTH
        assert rect.height() == CELL_HEIGHT
        assert not pixmap.isNull()


def test_sprite_skin_playable_frames_are_not_empty():
    skin = SpriteAtlasSkin("xiaofeixue")

    for state, spec in SPRITE_ROWS.items():
        for frame in range(len(spec.durations)):
            pixmap = skin.frame_pixmap(state, sum(spec.durations[:frame]))
            image = pixmap.toImage()
            has_alpha = False
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() > 0:
                        has_alpha = True
                        break
                if has_alpha:
                    break
            assert has_alpha, f"{state} frame {frame} is empty"


def test_xiaofeixue_performance_atlas_loads_all_frames():
    skin = SpriteAtlasSkin("xiaofeixue")

    assert skin.performance_error == ""
    assert skin.performance_path.exists()
    for state, spec in PERFORMANCE_ROWS.items():
        assert skin.has_state(state)
        for frame in range(len(spec.durations)):
            pixmap = skin.frame_pixmap(state, sum(spec.durations[:frame]))
            assert not pixmap.isNull()
            assert pixmap.width() == CELL_WIDTH
            assert pixmap.height() == CELL_HEIGHT

    from PySide6.QtGui import QImage

    image = QImage(str(skin.performance_path))
    assert (image.width(), image.height()) == (CELL_WIDTH * 8, PERFORMANCE_ATLAS_HEIGHT)


def test_missing_sprite_skin_is_unavailable_for_blob_fallback():
    skin = SpriteAtlasSkin("definitely-missing-skin")

    assert not skin.available


def test_sprite_controller_uses_explicit_actions_then_returns_to_base():
    pet = SpritePetController("xiaofeixue")

    assert pet.available
    assert pet.state == "idle"
    pet.set_busy(True)
    assert pet.state == "review"
    pet.react("celebrate")
    assert pet.state == "jumping"
    pet.advance(2.0)
    assert pet.state == "review"
    pet.set_busy(False)
    assert pet.state == "idle"


def test_sprite_controller_dragging_overrides_one_shots():
    pet = SpritePetController("xiaofeixue")

    pet.react("celebrate")
    assert pet.state == "jumping"
    pet.set_dragging(True)
    assert pet.state == "running"
    pet.advance(2.0)
    assert pet.state == "running"
    pet.set_dragging(False)
    assert pet.state == "idle"


def test_sprite_controller_idle_action_waits_until_fully_idle():
    pet = SpritePetController("xiaofeixue")

    pet._idle_action_left = 0.01
    pet.set_busy(True)
    pet.advance(1.0)
    assert pet.state == "review"

    pet.set_busy(False)
    pet._idle_action_left = 0.01
    pet.advance(0.02)
    assert pet.state in {"waving", "jumping", "review"}


def test_sprite_controller_talking_uses_waiting_base_and_periodic_wave():
    pet = SpritePetController("xiaofeixue")

    pet.set_talking(True)
    assert pet.state == "waiting"
    pet._talk_wave_left = 0.01
    pet.advance(0.02)
    assert pet.state == "waving"
    pet.advance(2.0)
    assert pet.state == "waiting"


def test_sprite_controller_priority_blocks_lower_priority_actions():
    pet = SpritePetController("xiaofeixue")

    pet.react("splat")
    assert pet.state == "failed"
    assert not pet.play("waving", priority=PRIORITY_IDLE_ACTION)
    assert pet.state == "failed"


def test_sprite_visual_anchors_track_drawn_target_rect():
    pet = SpritePetController("xiaofeixue")
    rect = pet.skin.target_rect(250, 220)
    anchors = pet.visual_anchors(250, 220)

    assert rect.contains(anchors["head"])
    assert rect.contains(anchors["head_top"])
    assert abs(anchors["foot"].y() - 214.0) < 0.01
    assert rect.left() <= anchors["foot"].x() <= rect.right()


def test_sprite_target_rect_scales_with_pet_window_presets():
    skin = SpriteAtlasSkin("xiaofeixue")

    for scale in PET_SCALE_PRESETS:
        width = round(250 * scale / 100)
        height = round(220 * scale / 100)
        rect = skin.target_rect(width, height)
        assert abs(rect.width() - CELL_WIDTH * scale / 100) <= 1.0
        assert abs(rect.height() - CELL_HEIGHT * scale / 100) <= 1.0


def test_pet_window_scale_preserves_global_foot_and_emits_change():
    pet = PetWindow("xiaofeixue", 100)
    pet.move(400, 300)
    old_foot = pet.below_blob()
    changes: list[int] = []
    pet.scale_changed.connect(changes.append)

    assert pet.set_pet_scale(125)
    assert pet.size().width() == 312
    assert pet.size().height() == 275
    assert pet.below_blob() == old_foot
    assert changes == [125]
    assert not pet.set_pet_scale(125)


def test_pet_window_invalid_scale_falls_back_to_default():
    pet = PetWindow("xiaofeixue", 99)

    assert pet.pet_scale == 100


def test_perform_submenu_survives_and_dispatches_to_sprite_pet():
    pet = PetWindow("xiaofeixue")
    tray = Tray(lambda: None, lambda: None, on_perform=pet.perform)

    assert tray._perform_menu is not None
    tray._perform_actions["wave"].trigger()
    pet._blob.advance(0.034)

    assert pet._blob._sprite.state == "waving"


def test_manual_perform_bypasses_stale_agent_cancellation_state():
    calls: list[str] = []

    class PetStub:
        def perform(self, name: str) -> None:
            calls.append(name)

    class BridgeStub(AgentBridgeMixin):
        _cancelling = True
        _pet = PetStub()

        def _wake(self) -> None:
            calls.append("wake")

    bridge = BridgeStub()
    bridge._on_perform("dance")
    assert calls == []

    bridge._on_manual_perform("dance")
    assert calls == ["wake", "dance"]


def test_explicit_perform_stops_sprite_walking_before_action():
    pet = PetWindow("xiaofeixue")
    pet._blob.set_sprite_walking(True, 1)

    assert pet.perform("wave")
    pet._blob.advance(0.034)

    assert pet._blob._sprite.state == "waving"


def test_sprite_advance_reports_only_state_or_frame_changes():
    pet = SpritePetController("xiaofeixue")

    assert pet.advance(0.001)
    assert not pet.advance(0.001)
    pet.react("celebrate")
    assert pet.advance(0.001)


def test_sprite_controller_notice_only_works_when_idle():
    pet = SpritePetController("xiaofeixue")

    assert pet.notice()
    assert pet.state == "waving"
    pet.advance(2.0)
    pet.set_busy(True)
    assert not pet.notice()
    assert pet.state == "review"


def test_sprite_controller_walking_uses_directional_running():
    pet = SpritePetController("xiaofeixue")

    pet.react("celebrate")
    assert pet.state == "jumping"
    pet.set_walking(True, 1)
    assert pet.state == "running-right"
    pet.set_walking(True, -1)
    assert pet.state == "running-left"
    pet.set_walking(False)
    assert pet.state == "idle"


def test_sprite_controller_uses_dedicated_dance_and_fish_rows():
    pet = SpritePetController("xiaofeixue")

    pet.react("dance")
    assert pet.state == "dance"
    pet.advance(4.0)
    assert pet.state == "idle"

    for activity in ("fish", "yarn", "coffee", "read", "stars"):
        pet.start_activity(activity)
        assert pet.state == activity
        pet.advance(6.0)
        assert pet.state == activity
        pet.end_activity()
        assert pet.state == "idle"


def test_blob_sprite_wander_gate_respects_busy_and_reactions():
    pet = BlobPet("xiaofeixue")

    assert pet.can_sprite_wander
    pet.set_busy(True)
    assert not pet.can_sprite_wander
    pet.set_busy(False)
    assert pet.can_sprite_wander
    pet.react("celebrate")
    assert not pet.can_sprite_wander
