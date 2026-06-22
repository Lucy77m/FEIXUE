from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap


ATLAS_WIDTH = 1536
ATLAS_HEIGHT = 1872
COLS = 8
ROWS = 9
CELL_WIDTH = ATLAS_WIDTH // COLS
CELL_HEIGHT = ATLAS_HEIGHT // ROWS
BASE_VIEW_WIDTH = 250
BASE_VIEW_HEIGHT = 220


@dataclass(frozen=True)
class SpriteRow:
    row: int
    durations: tuple[float, ...]

    @property
    def total_duration(self) -> float:
        return sum(self.durations)


SPRITE_ROWS: dict[str, SpriteRow] = {
    "idle": SpriteRow(0, (0.28, 0.11, 0.11, 0.14, 0.14, 0.26)),
    "running-right": SpriteRow(1, (0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.18)),
    "running-left": SpriteRow(2, (0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.18)),
    "waving": SpriteRow(3, (0.14, 0.14, 0.14, 0.20)),
    "jumping": SpriteRow(4, (0.12, 0.12, 0.12, 0.12, 0.16)),
    "failed": SpriteRow(5, (0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.24)),
    "waiting": SpriteRow(6, (0.16, 0.16, 0.16, 0.16, 0.16, 0.16)),
    "running": SpriteRow(7, (0.11, 0.11, 0.11, 0.11, 0.11, 0.11)),
    "review": SpriteRow(8, (0.15, 0.15, 0.15, 0.15, 0.15, 0.15)),
}

PERFORMANCE_ROWS: dict[str, SpriteRow] = {
    "dance": SpriteRow(0, (0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.20)),
    "fish": SpriteRow(1, (0.45, 0.40, 0.65, 1.00, 0.30, 0.45, 0.85, 0.55)),
    "yarn": SpriteRow(2, (0.45, 0.45, 0.45, 0.45, 0.45, 0.55, 0.75, 0.55)),
    "coffee": SpriteRow(3, (0.50, 0.40, 0.40, 0.80, 0.80, 0.60, 0.70, 0.50)),
    "read": SpriteRow(4, (0.45, 0.45, 0.80, 0.80, 0.45, 0.70, 0.60, 0.45)),
    "stars": SpriteRow(5, (0.45, 0.45, 0.75, 0.70, 0.70, 0.45, 0.75, 0.45)),
}
PERFORMANCE_ATLAS_HEIGHT = CELL_HEIGHT * len(PERFORMANCE_ROWS)


ONE_SHOT_DURATIONS = {
    "waving": 1.30,
    "jumping": 1.15,
    "failed": 1.35,
    "waiting": 1.20,
    "review": 1.50,
    "running": 0.95,
    "dance": 3.80,
}


PRIORITY_IDLE = 0
PRIORITY_IDLE_ACTION = 10
PRIORITY_TALK = 20
PRIORITY_ATTENTION = 25
PRIORITY_THINK = 30
PRIORITY_REACTION = 40
PRIORITY_HURT = 50

TALK_WAVE_GAP = (4.0, 7.0)
IDLE_ACTION_GAP = (8.0, 18.0)
IDLE_ACTIONS = (("waving", 0.55), ("jumping", 0.25), ("review", 0.20))
SPRITE_FOOT_PAD = 6.0


@dataclass
class SpriteAction:
    state: str
    duration: float
    priority: int


class SpriteAtlasSkin:
    """Cached renderer for Codex pet 8x9 sprite atlases."""

    def __init__(self, skin_name: str) -> None:
        self.skin_name = skin_name.strip()
        self.path = self._asset_path(self.skin_name)
        self.performance_path = self.path.with_name("performances.webp")
        self.error = ""
        self.performance_error = ""
        self._frames: dict[str, tuple[QPixmap, ...]] = {}
        self._scaled_cache: dict[tuple[str, int, int, int], QPixmap] = {}
        self.available = self._load()

    @staticmethod
    def _asset_path(skin_name: str) -> Path:
        root = Path(__file__).resolve().parent.parent
        return root / "assets" / "skins" / skin_name / "spritesheet.webp"

    @property
    def atlas_size(self) -> tuple[int, int]:
        return (ATLAS_WIDTH, ATLAS_HEIGHT) if self.available else (0, 0)

    @property
    def cell_size(self) -> tuple[int, int]:
        return CELL_WIDTH, CELL_HEIGHT

    def _load(self) -> bool:
        if (
            not self.skin_name
            or self.skin_name in {".", ".."}
            or "/" in self.skin_name
            or "\\" in self.skin_name
        ):
            self.error = "invalid skin name"
            return False
        if not self.path.exists():
            self.error = f"missing skin asset: {self.path}"
            return False
        image = QImage(str(self.path))
        if image.isNull():
            self.error = f"failed to load skin asset: {self.path}"
            return False
        if image.width() != ATLAS_WIDTH or image.height() != ATLAS_HEIGHT:
            self.error = (
                f"invalid atlas size: {image.width()}x{image.height()}, "
                f"expected {ATLAS_WIDTH}x{ATLAS_HEIGHT}"
            )
            return False
        for name, spec in SPRITE_ROWS.items():
            frames: list[QPixmap] = []
            for frame in range(len(spec.durations)):
                rect = QRect(frame * CELL_WIDTH, spec.row * CELL_HEIGHT, CELL_WIDTH, CELL_HEIGHT)
                frames.append(QPixmap.fromImage(image.copy(rect)))
            self._frames[name] = tuple(frames)
        self._load_performances()
        return True

    def _load_performances(self) -> None:
        if not self.performance_path.exists():
            return
        image = QImage(str(self.performance_path))
        if image.isNull():
            self.performance_error = f"failed to load performance asset: {self.performance_path}"
            return
        if image.width() != ATLAS_WIDTH or image.height() != PERFORMANCE_ATLAS_HEIGHT:
            self.performance_error = (
                f"invalid performance atlas size: {image.width()}x{image.height()}, "
                f"expected {ATLAS_WIDTH}x{PERFORMANCE_ATLAS_HEIGHT}"
            )
            return
        for name, spec in PERFORMANCE_ROWS.items():
            frames: list[QPixmap] = []
            for frame in range(len(spec.durations)):
                rect = QRect(frame * CELL_WIDTH, spec.row * CELL_HEIGHT, CELL_WIDTH, CELL_HEIGHT)
                frames.append(QPixmap.fromImage(image.copy(rect)))
            self._frames[name] = tuple(frames)

    def has_state(self, state: str) -> bool:
        return state in self._frames

    def _state_spec(self, state: str) -> tuple[str, SpriteRow]:
        if state not in self._frames:
            return "idle", SPRITE_ROWS["idle"]
        return state, PERFORMANCE_ROWS.get(state, SPRITE_ROWS.get(state, SPRITE_ROWS["idle"]))

    def frame_index(self, state: str, elapsed_s: float) -> int:
        _state, spec = self._state_spec(state)
        total = spec.total_duration
        cursor = elapsed_s % total if total > 0 else 0.0
        for idx, duration in enumerate(spec.durations):
            cursor -= duration
            if cursor < 0:
                return idx
        return len(spec.durations) - 1

    def frame_rect(self, state: str, elapsed_s: float) -> QRect:
        state, spec = self._state_spec(state)
        frame = self.frame_index(state, elapsed_s)
        return QRect(frame * CELL_WIDTH, spec.row * CELL_HEIGHT, CELL_WIDTH, CELL_HEIGHT)

    def frame_pixmap(self, state: str, elapsed_s: float) -> QPixmap:
        if not self.available:
            return QPixmap()
        state, _spec = self._state_spec(state)
        frames = self._frames[state]
        return frames[self.frame_index(state, elapsed_s)]

    def _target_size(self, w: int, h: int) -> QSize:
        scale = min(w / BASE_VIEW_WIDTH, h / BASE_VIEW_HEIGHT)
        return QSize(max(1, int(CELL_WIDTH * scale)), max(1, int(CELL_HEIGHT * scale)))

    def target_rect(self, w: int, h: int) -> QRectF:
        target = self._target_size(w, h)
        return QRectF(
            (w - target.width()) / 2,
            h - target.height() - SPRITE_FOOT_PAD,
            target.width(),
            target.height(),
        )

    def _scaled_pixmap(self, state: str, frame: int, w: int, h: int) -> QPixmap:
        target = self._target_size(w, h)
        key = (state, frame, target.width(), target.height())
        cached = self._scaled_cache.get(key)
        if cached is not None:
            return cached
        state, _spec = self._state_spec(state)
        frames = self._frames[state]
        pixmap = frames[frame].scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if len(self._scaled_cache) >= 256:
            self._scaled_cache.clear()
        self._scaled_cache[key] = pixmap
        return pixmap

    def paint(self, painter: QPainter, w: int, h: int, state: str, elapsed_s: float) -> None:
        if not self.available:
            return
        state, _spec = self._state_spec(state)
        frame = self.frame_index(state, elapsed_s)
        pixmap = self._scaled_pixmap(state, frame, w, h)
        target_rect = self.target_rect(w, h)
        painter.drawPixmap(target_rect, pixmap, QRectF(pixmap.rect()))


class SpritePetController:
    """Small action controller for sprite pets, separate from Blob body poses."""

    def __init__(self, skin_name: str) -> None:
        self.skin = SpriteAtlasSkin(skin_name)
        self._base_state = "idle"
        self._active: SpriteAction | None = None
        self._clock = 0.0
        self._last_state = ""
        self._last_frame = -1
        self._dirty = True
        self._talk_wave_left = random.uniform(*TALK_WAVE_GAP)
        self._idle_action_left = random.uniform(*IDLE_ACTION_GAP)
        self._busy = False
        self._talking = False
        self._lecturing = False
        self._dragging = False
        self._hidden = False
        self._walking = False
        self._walking_state = "running"
        self._asleep = False
        self._sad = False
        self._activity: str | None = None

    @property
    def available(self) -> bool:
        return self.skin.available

    @property
    def state(self) -> str:
        if self._dragging or self._hidden:
            return "running"
        if self._walking:
            return self._walking_state
        if self._active is not None:
            return self._active.state
        return self._desired_base_state()

    def advance(self, dt: float) -> bool:
        before_state = self.state
        before_frame = self.skin.frame_index(before_state, self._clock) if self.available else -1
        self._clock += dt
        if self._active is not None:
            self._active.duration -= dt
            if self._active.duration <= 0.0:
                self._active = None
        self._advance_talk_cadence(dt)
        self._advance_idle_actions(dt)
        after_state = self.state
        after_frame = self.skin.frame_index(after_state, self._clock) if self.available else -1
        changed = self._dirty or before_state != after_state or before_frame != after_frame
        self._dirty = False
        self._last_state = after_state
        self._last_frame = after_frame
        return changed

    def paint(self, painter: QPainter, w: int, h: int) -> None:
        self.skin.paint(painter, w, h, self.state, self._clock)

    def visual_anchors(self, w: int, h: int) -> dict[str, QPointF]:
        rect = self.skin.target_rect(w, h)
        foot = QPointF(rect.center().x(), h - SPRITE_FOOT_PAD)
        head = QPointF(rect.center().x() + rect.width() * 0.18, rect.top() + rect.height() * 0.22)
        head_top = QPointF(rect.center().x(), rect.top() + rect.height() * 0.06)
        return {"foot": foot, "head": head, "head_top": head_top}

    def set_talking(self, on: bool) -> None:
        on = bool(on)
        if self._talking != on:
            self._dirty = True
        self._talking = on
        if on:
            self._talk_wave_left = min(self._talk_wave_left, random.uniform(0.3, 1.2))

    def set_busy(self, on: bool) -> None:
        on = bool(on)
        if self._busy != on:
            self._dirty = True
        self._busy = on
        if on:
            self._sad = False
            self._idle_action_left = random.uniform(*IDLE_ACTION_GAP)

    def set_lecturing(self, on: bool) -> None:
        on = bool(on)
        if self._lecturing != on:
            self._dirty = True
        self._lecturing = on

    def set_dragging(self, on: bool) -> None:
        on = bool(on)
        if self._dragging != on:
            self._dirty = True
        self._dragging = on
        if on:
            self._active = None

    def set_hidden(self, on: bool) -> None:
        on = bool(on)
        if self._hidden != on:
            self._dirty = True
        self._hidden = on
        if on:
            self._active = None

    def set_walking(self, on: bool, direction: int = 0) -> None:
        on = bool(on)
        state = "running-right" if direction > 0 else "running-left" if direction < 0 else "running"
        if self._walking != on:
            self._dirty = True
        if self._walking_state != state:
            self._dirty = True
        self._walking = on
        self._walking_state = state
        if on:
            self._active = None

    def set_asleep(self, on: bool) -> None:
        on = bool(on)
        if self._asleep != on:
            self._dirty = True
        self._asleep = on

    def set_expression(self, name: str) -> None:
        sad = name == "sad"
        if self._sad != sad:
            self._dirty = True
        self._sad = sad
        if name == "happy":
            self.play("jumping", priority=PRIORITY_REACTION)

    def start_activity(self, name: str) -> None:
        if self._activity != name:
            self._dirty = True
        self._activity = name
        self._idle_action_left = random.uniform(*IDLE_ACTION_GAP)
        if self.skin.has_state(name):
            self._active = None
            self._clock = 0.0
            self._dirty = True
        elif name in {"read", "sleuth", "camera", "painting", "rubik", "calligraphy"}:
            self.play("review", 1.5, PRIORITY_THINK)
        elif name in {"kite", "butterfly", "frisbee", "paperplane", "yoyo", "spintop"}:
            self.play("running", 0.95, PRIORITY_THINK)
        else:
            self.play("waiting", 1.2, PRIORITY_THINK)

    def end_activity(self) -> None:
        if self._activity is not None:
            self._dirty = True
        self._activity = None

    def react(self, name: str) -> None:
        state = name if self.skin.has_state(name) else _reaction_state(name)
        priority = PRIORITY_HURT if state == "failed" else PRIORITY_REACTION
        self.play(state, priority=priority)

    def think_step(self, kind: str) -> None:
        if kind in {"tool", "inner", "new_turn"}:
            self.play("review", 0.75, PRIORITY_THINK)

    def notice(self) -> bool:
        if not self._idle_available():
            return False
        return self.play("waving", 0.62, PRIORITY_ATTENTION)

    def play(self, state: str, duration: float | None = None, priority: int = PRIORITY_REACTION) -> bool:
        if not self.skin.has_state(state):
            state = "idle"
        if self._dragging or self._hidden:
            return False
        if self._active is not None and priority < self._active.priority:
            return False
        self._active = SpriteAction(
            state,
            duration if duration is not None else ONE_SHOT_DURATIONS.get(state, 1.0),
            priority,
        )
        self._dirty = True
        return True

    def _desired_base_state(self) -> str:
        if self._busy or self._lecturing:
            return "review"
        if self._activity is not None:
            return self._activity if self.skin.has_state(self._activity) else "waiting"
        if self._asleep:
            return "waiting"
        if self._talking:
            return "waiting"
        if self._sad:
            return "failed"
        return self._base_state

    def _advance_talk_cadence(self, dt: float) -> None:
        if not self._talking or self._busy or self._lecturing or self._activity is not None:
            self._talk_wave_left = random.uniform(*TALK_WAVE_GAP)
            return
        if self._dragging or self._hidden:
            return
        self._talk_wave_left -= dt
        if self._talk_wave_left <= 0.0:
            if self.play("waving", 0.62, PRIORITY_TALK):
                self._talk_wave_left = random.uniform(*TALK_WAVE_GAP)

    def _advance_idle_actions(self, dt: float) -> None:
        if not self._idle_available():
            self._idle_action_left = random.uniform(*IDLE_ACTION_GAP)
            return
        self._idle_action_left -= dt
        if self._idle_action_left <= 0.0:
            state = _weighted_choice(IDLE_ACTIONS)
            if self.play(state, priority=PRIORITY_IDLE_ACTION):
                self._idle_action_left = random.uniform(*IDLE_ACTION_GAP)

    def _idle_available(self) -> bool:
        return not (
            self._busy or self._talking or self._lecturing or self._dragging or self._hidden
            or self._walking or self._asleep or self._activity is not None or self._active is not None
        )


def _reaction_state(name: str) -> str:
    if name in {"wave", "perk_up", "peek", "nod", "purr"}:
        return "waving"
    if name in {
        "celebrate", "jump_spin", "cheer", "bounce", "hop2", "happy_wiggle",
        "boing", "dance", "flip", "spin", "giggle", "pop",
    }:
        return "jumping"
    if name in {"slump", "droop", "deflate", "recoil", "shake", "splat", "tip_over"}:
        return "failed"
    if name in {"ponder"}:
        return "review"
    return "waiting"


def _weighted_choice(items: tuple[tuple[str, float], ...]) -> str:
    total = sum(weight for _, weight in items)
    pick = random.random() * total
    for state, weight in items:
        pick -= weight
        if pick <= 0.0:
            return state
    return items[-1][0]
