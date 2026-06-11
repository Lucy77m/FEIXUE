# author: bdth
# email: 2074055628@qq.com
# 桌宠角色BlobPet 状态机推进与qpainter形象绘制

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)

from desktop_pet.emotion.tags import EXPRESSIONS as _EXPRESSIONS
from desktop_pet.pet import adornments, palette, props
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.behaviors import Category, registry
from desktop_pet.pet.behaviors.easing import ease_in, ease_out, ease_out_back
from desktop_pet.pet.fx import smooth_font

_INK = palette.INK
_SKIN = palette.SKIN


_BLOB_BASE = 150
BLOB_HALF_H = _BLOB_BASE * 0.22
BLOB_HALF_W = _BLOB_BASE * 0.31
_BLINK_DUR = 0.16
_SETTLE_DUR = 0.45
_EXPR_HOLD = 5.0
_LOOK_AT_HOLD = 1.2


_IDLE_FIDGETS = (
    "bounce", "nod", "wobble", "pop", "peek", "stretch", "hop2", "perk_up", "boing",
    "yawn", "happy_wiggle", "double_take", "puff_up", "ponder",
)


_DREAM_GLYPHS = ("♪", "♫", "★", "♥", "✦", "?", "～", "♬")
_DREAM_COLORS = palette.DREAM_COLORS
_DAYDREAM_GAP = (22.0, 48.0)
_DAYDREAM_DUR = (3.0, 5.5)
_DREAM_SPAWN = (0.5, 1.1)
_DREAM_LIFE = (1.5, 2.1)


_ACTIVITIES = {
    "coffee": ("coffee", 0.0, "puff_up", [
        ("pour", 3.2, "～"),
        ("lift", 1.2, ""),
        ("sip", 4.5, "～"),
    ]),
    "fish": ("fishing", 0.35, "jump_spin", [
        ("cast", 2.0, ""),
        ("wait", 6.5, "～"),
        ("bite", 1.0, "!"),
        ("reel", 1.8, ""),
        ("catch", 2.4, "★"),
    ]),
    "sleuth": ("sherlock", 0.5, "celebrate", [
        ("scan", 5.5, "?"),
        ("closer", 3.0, "?"),
        ("aha", 2.0, "!"),
    ]),
    "read": ("book", 0.0, "nod", [
        ("open", 1.2, ""),
        ("read", 7.0, ""),
        ("good", 2.0, "!"),
    ]),
    "music": ("headphones", 0.0, "happy_wiggle", [
        ("on", 1.2, "♪"),
        ("vibe", 8.0, "♫"),
    ]),
    "game": ("gaming", 0.0, "cheer", [
        ("play", 7.0, "✦"),
        ("tense", 2.0, "!"),
        ("win", 1.5, "★"),
    ]),
    "stars": ("telescope", 0.6, "puff_up", [
        ("aim", 2.0, ""),
        ("gaze", 6.5, "★"),
        ("wow", 2.0, "✦"),
    ]),
    "void": ("void", 0.5, "puff_up", [
        ("notice", 3.0, "?"),
        ("crack", 4.0, "…"),
        ("peer", 4.5, "·"),
        ("brace", 2.0, "!"),
        ("leap", 1.4, "✦"),
        ("gone", 3.0, ""),
        ("return", 2.2, "★"),
        ("seal", 3.5, "～"),
    ]),
    "clone": ("clone", 0.0, "happy_wiggle", [
        ("focus", 3.0, "…"),
        ("split", 2.0, "!"),
        ("mirror", 6.0, "♪"),
        ("swap", 4.5, "✦"),
        ("merge", 2.0, "✦"),
    ]),
    "meteor": ("meteor", -0.3, "cheer", [
        ("spot", 3.0, "?"),
        ("fall", 5.0, "✦"),
        ("scramble", 3.0, "!"),
        ("catch", 1.5, "★"),
        ("cradle", 3.0, "♥"),
        ("release", 2.5, "～"),
    ]),
    "sprout": ("sprout", 0.3, "happy_wiggle", [
        ("dig", 3.0, ""),
        ("plant", 2.5, "·"),
        ("water", 4.0, "～"),
        ("wait", 6.0, "…"),
        ("sprout", 4.0, "✦"),
        ("bloom", 3.5, "★"),
        ("sniff", 3.0, "♥"),
    ]),
    "yarn": ("yarn", 0.3, "happy_wiggle", [
        ("eye", 2.2, "?"),
        ("bat", 5.5, "!"),
        ("chase", 4.0, "✦"),
        ("tangle", 3.5, "～"),
        ("rest", 2.5, "♥"),
    ]),
    "bubbles": ("bubbles", 0.0, "happy_wiggle", [
        ("dip", 1.8, ""),
        ("blow", 2.6, "～"),
        ("watch", 4.5, "✦"),
        ("pop", 1.6, "!"),
    ]),
    "balloon": ("balloon", 0.0, "jump_spin", [
        ("grab", 1.6, ""),
        ("bob", 5.0, "～"),
        ("float", 3.0, "♥"),
    ]),
    "icecream": ("icecream", 0.0, "puff_up", [
        ("hold", 1.6, ""),
        ("lick", 5.5, "～"),
        ("melt", 2.6, "～"),
    ]),
    "paperplane": ("paperplane", 0.0, "celebrate", [
        ("fold", 2.2, ""),
        ("throw", 1.0, "!"),
        ("glide", 5.5, "～"),
    ]),
    "kite": ("kite", 0.0, "jump_spin", [
        ("run", 3.0, "～"),
        ("fly", 6.0, "✦"),
    ]),
    "camera": ("camera", 0.0, "celebrate", [
        ("aim", 3.0, "?"),
        ("flash", 0.8, "!"),
        ("aim", 2.0, "♥"),
    ]),
    "bubbletea": ("bubbletea", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("sip", 5.5, "～"),
    ]),
    "tanghulu": ("tanghulu", 0.0, "puff_up", [
        ("hold", 1.6, ""),
        ("bite", 5.0, "～"),
    ]),
    "dandelion": ("dandelion", 0.0, "happy_wiggle", [
        ("hold", 1.8, ""),
        ("blow", 2.2, "～"),
        ("watch", 4.0, "✦"),
    ]),
    "guitar": ("guitar", 0.0, "happy_wiggle", [
        ("tune", 1.6, "?"),
        ("strum", 6.0, "✦"),
    ]),
    "watermelon": ("watermelon", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "fireworks": ("fireworks", 0.0, "celebrate", [
        ("launch", 2.0, "～"),
        ("burst", 5.0, "✦"),
    ]),
    "yoyo": ("yoyo", 0.0, "jump_spin", [
        ("throw", 1.6, ""),
        ("sleep", 3.5, "✦"),
        ("back", 1.4, "!"),
    ]),
    "painting": ("painting", 0.0, "celebrate", [
        ("setup", 1.6, ""),
        ("paint", 6.0, "✦"),
    ]),
    "watering": ("watering", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("pour", 3.5, "～"),
        ("grow", 2.5, "✦"),
    ]),
    "blocks": ("blocks", 0.0, "celebrate", [
        ("stack", 6.0, "✦"),
        ("done", 1.5, "!"),
    ]),
    "lollipop": ("lollipop", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("lick", 6.0, "～"),
    ]),
    "popcorn": ("popcorn", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("toss", 5.0, "～"),
    ]),
    "pinwheel": ("pinwheel", 0.0, "jump_spin", [
        ("hold", 1.4, ""),
        ("spin", 5.5, "✦"),
    ]),
    "donut": ("donut", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "soda": ("soda", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("sip", 5.5, "～"),
    ]),
    "corn": ("corn", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "sushi": ("sushi", 0.0, "happy_wiggle", [
        ("pick", 2.0, "?"),
        ("eat", 3.0, "～"),
    ]),
    "rubik": ("rubik", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("turn", 6.0, "?"),
    ]),
    "magic": ("magic", 0.0, "celebrate", [
        ("wave", 2.5, "～"),
        ("poof", 2.0, "✦"),
    ]),
    "knitting": ("knitting", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("knit", 6.0, "～"),
    ]),
    "phone": ("phone", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("tap", 6.0, "♥"),
    ]),
    "harmonica": ("harmonica", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "～"),
    ]),
    "popsicle": ("popsicle", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("bite", 5.0, "～"),
    ]),
    "butterfly": ("butterfly", 0.0, "jump_spin", [
        ("spot", 2.0, "!"),
        ("chase", 5.0, "✦"),
    ]),
    "fishmoon": ("fishmoon", 0.0, "happy_wiggle", [
        ("cast", 2.0, "～"),
        ("wait", 5.0, "✦"),
    ]),
    "ringtoss": ("ringtoss", 0.0, "celebrate", [
        ("toss", 6.0, "✦"),
        ("done", 1.5, "!"),
    ]),
    "lantern": ("lantern", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("light", 6.0, "✦"),
    ]),
    "cottoncandy": ("cottoncandy", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("eat", 5.5, "～"),
    ]),
    "burger": ("burger", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "noodles": ("noodles", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("slurp", 6.0, "～"),
    ]),
    "tea": ("tea", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("sip", 6.0, "～"),
    ]),
    "marshmallow": ("marshmallow", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("roast", 5.5, "✦"),
    ]),
    "calligraphy": ("calligraphy", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("write", 6.0, "✦"),
    ]),
    "darts": ("darts", 0.0, "celebrate", [
        ("aim", 2.0, "?"),
        ("throw", 4.0, "!"),
    ]),
    "paperboat": ("paperboat", 0.0, "happy_wiggle", [
        ("set", 1.6, ""),
        ("float", 6.0, "～"),
    ]),
    "pizza": ("pizza", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("munch", 5.0, "～"),
    ]),
    "spintop": ("spintop", 0.0, "jump_spin", [
        ("hold", 1.4, ""),
        ("spin", 6.0, "✦"),
    ]),
    "crane": ("crane", 0.0, "happy_wiggle", [
        ("fold", 6.0, "～"),
        ("done", 1.5, "✦"),
    ]),
    "piano": ("piano", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "✦"),
    ]),
    "piggybank": ("piggybank", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("save", 5.0, "✦"),
    ]),
    "crystalball": ("crystalball", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("gaze", 6.0, "✦"),
    ]),
    "cards": ("cards", 0.0, "celebrate", [
        ("hold", 1.4, ""),
        ("fan", 5.5, "?"),
    ]),
    "matryoshka": ("matryoshka", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("open", 4.0, "✦"),
    ]),
    "sheep": ("sheep", 0.0, "happy_wiggle", [
        ("count", 6.0, "～"),
    ]),
    "bouquet": ("bouquet", 0.0, "happy_wiggle", [
        ("hold", 2.0, ""),
        ("sniff", 5.0, "♥"),
    ]),
    "sweetpotato": ("sweetpotato", 0.0, "puff_up", [
        ("hold", 1.4, ""),
        ("eat", 5.0, "～"),
    ]),
    "trumpet": ("trumpet", 0.0, "happy_wiggle", [
        ("hold", 1.4, ""),
        ("play", 6.0, "✦"),
    ]),
    "frisbee": ("frisbee", 0.0, "jump_spin", [
        ("throw", 2.0, "!"),
        ("watch", 4.0, "✦"),
    ]),
    "cupcake": ("cupcake", 0.0, "celebrate", [
        ("hold", 2.0, ""),
        ("blow", 3.0, "✦"),
    ]),
    "snowglobe": ("snowglobe", 0.0, "happy_wiggle", [
        ("hold", 1.6, ""),
        ("shake", 5.5, "✦"),
    ]),
}
_ACTIVITY_GAP = (150.0, 300.0)
_TRAVEL = "__travel__"


def _void_body(stage, p, t, bw, bh):
    """虚空一跃的身体位姿"""
    if stage == "notice":
        e = ease_out(p)
        return 0.10 * bw * e, 0.0, 6.0 * e, 1.0, 1.0
    if stage == "peer":
        wob = math.sin(t * 4.0) * 3.0
        return 0.20 * bw, 0.05 * bh, 12.0 + wob, 1.03, 0.97
    if stage == "brace":
        e = ease_in(p)
        return 0.18 * bw, 0.10 * bh * e, 8.0, 1.0 + 0.20 * e, 1.0 - 0.28 * e
    if stage == "leap":
        if p < 0.3:
            e = ease_out(p / 0.3)
            return 0.18 * bw, -0.05 * bh * e, 8.0, 1.0 - 0.12 * e, 1.0 + 0.18 * e
        e = ease_in((p - 0.3) / 0.7)
        ox = (0.18 + 0.55 * e) * bw
        oy = (-0.55 * math.sin(e * math.pi) + 0.30 * e) * bh
        s = max(0.06, 1.0 - 0.92 * e)
        return ox, oy, 8.0 + 360.0 * e, s, s
    if stage == "gone":
        return 0.73 * bw, 0.30 * bh, 0.0, 0.001, 0.001
    if stage == "return":
        e = ease_out_back(p)
        ox = (0.73 - 0.73 * e) * bw
        oy = (0.30 - 0.30 * e) * bh - math.sin(p * math.pi) * 0.12 * bh
        s = max(0.06, 0.08 + 0.92 * e)
        return ox, oy, 0.0, s, s
    if stage == "seal":
        return 0.10 * bw * (1.0 - ease_out(p)), 0.0, 4.0 * (1.0 - p), 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _clone_body(stage, p, t, bw, bh):
    """影分身的身体位姿"""
    if stage == "focus":
        e = ease_in(p)
        return 0.0, 0.0, math.sin(t * 20.0) * 2.0 * e, 1.0 + 0.04 * e, 1.0 - 0.06 * e
    if stage == "split":
        e = ease_out(p)
        return -0.16 * bw * e, 0.0, -6.0 * e, 1.0 + 0.10 * math.sin(p * math.pi), 1.0
    if stage == "mirror":
        return math.sin(t * 3.0) * 0.18 * bw, 0.0, math.sin(t * 3.0) * 8.0, 1.0, 1.0
    if stage == "swap":
        return math.cos(t * 1.8) * 0.22 * bw, math.sin(t * 1.8) * 0.10 * bh, 0.0, 1.0, 1.0
    if stage == "merge":
        e = ease_out(p)
        ox = -0.16 * bw * (1.0 - e)
        k = ease_in(max(0.0, (p - 0.7) / 0.3))
        return ox, 0.0, 0.0, 1.0 + 0.18 * k, 1.0 - 0.14 * k
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _meteor_body(stage, p, t, bw, bh):
    """接流星的身体位姿"""
    if stage == "spot":
        e = ease_out(p)
        return -0.05 * bw * e, -0.04 * bh * e, -4.0 * e, 1.0, 1.0
    if stage == "fall":
        return math.sin(t * 2.2) * 0.12 * bw, -0.02 * bh, 0.0, 1.0, 1.0
    if stage == "scramble":
        hop = -abs(math.sin(t * 8.0)) * 0.05 * bh
        return 0.20 * bw * ease_out(p), hop, 0.0, 1.0, 1.0 + 0.04 * abs(math.sin(t * 8.0))
    if stage == "catch":
        up = math.sin(p * math.pi)
        return 0.15 * bw, -0.12 * bh * up, 0.0, 1.0 - 0.08 * up, 1.0 + 0.20 * up
    if stage == "cradle":
        return 0.10 * bw, math.sin(t * 2.0) * 0.03 * bh, 0.0, 1.0, 1.0
    if stage == "release":
        e = ease_out(p)
        return 0.10 * bw * (1.0 - e), -0.04 * bh * math.sin(p * math.pi), 0.0, 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _sprout_body(stage, p, t, bw, bh):
    """种花的身体位姿"""
    if stage == "dig":
        e = ease_out(p)
        return 0.0, 0.06 * bh * e, 6.0 * e, 1.0, 1.0
    if stage in ("plant", "water"):
        sway = math.sin(t * 4.0) * 0.05 * bw if stage == "water" else 0.0
        return sway, 0.06 * bh, 6.0, 1.0, 1.0
    if stage == "wait":
        return math.sin(t * 0.8) * 0.03 * bw, 0.0, math.sin(t * 0.8) * 2.0, 1.0, 1.0
    if stage == "sprout":
        return 0.0, 0.03 * bh * ease_out(p), 0.0, 1.0, 1.0
    if stage == "bloom":
        up = math.sin(p * math.pi)
        return 0.0, -0.04 * bh * up, 0.0, 1.0, 1.0 + 0.05 * up
    if stage == "sniff":
        e = ease_out(p)
        return 0.12 * bw * e, 0.05 * bh * e, 8.0 * e, 1.0, 1.0
    return 0.0, 0.0, 0.0, 1.0, 1.0


def _yarn_body(stage, p, t, bw, bh):
    """玩毛线球的身体位姿"""
    if stage == "eye":
        e = ease_out(p)
        # 歪头盯球 屁股微撅蓄势
        return 0.05 * bw * e, 0.03 * bh * e, 9.0 * e, 1.0 + 0.04 * e, 1.0 - 0.05 * e
    if stage == "bat":
        sw = math.sin(p * math.pi * 4)  # 跟球的节奏扑
        pounce = abs(math.sin(p * math.pi * 8))
        return sw * bw * 0.13, 0.05 * bh + pounce * bh * 0.025, sw * 10, 1 + 0.05 * pounce, 1 - 0.07 * pounce
    if stage == "chase":
        sw = math.sin(p * math.pi * 2)
        return sw * bw * 0.22, 0.04 * bh, sw * 14, 1.02, 0.96
    if stage == "tangle":
        wig = math.sin(t * 7) * ease_out(p)
        return wig * bw * 0.03, 0.05 * bh, wig * 6, 1.0 + 0.03 * abs(wig), 1.0 - 0.04 * abs(wig)
    if stage == "rest":
        e = ease_out(p)
        return 0.05 * bw, 0.08 * bh * e, 4.0, 1.0 - 0.03 * e, 1.0 - 0.04 * e
    return 0.0, 0.0, 0.0, 1.0, 1.0


_ACTIVITY_BODY = {
    "void": _void_body,
    "clone": _clone_body,
    "meteor": _meteor_body,
    "sprout": _sprout_body,
    "yarn": _yarn_body,
}


_SLEEP_FADE = 1.2
_SLEEP_SINK = 0.05
_SLEEP_BREATH_HZ = 0.9
_ZZZ_CYCLE = 2.4
_ZZZ_STAGGER = 0.33
_ZZZ_ALPHA_MAX = 200
_ZZZ_INK = QColor(150, 160, 180)


_CATNAP_GAP = (45.0, 120.0)
_CATNAP_DUR = (4.0, 9.0)
_CATNAP_CHANCE = 0.5


_DRAG_SWAY_HZ = 5.0
_DRAG_SWAY_DEG = 7.0
_DRAG_SINK = 0.05
_DRAG_STRETCH = 0.12


_OUTLINE = QColor(46, 46, 54)
_THINK_HOME = 0
_THINK_XFADE_DUR = 0.5

_THINK_DWELL = (
    (2.5, 5.0), (1.5, 3.0), (2.0, 4.5), (2.5, 5.0), (2.0, 4.0),
    (2.5, 4.5), (2.0, 3.5), (0.8, 1.4), (1.5, 3.0),
    (1.2, 2.5), (1.8, 3.5), (2.0, 4.0), (3.0, 6.0), (2.0, 4.0), (2.5, 5.5),
)


_THINK_POSE_WEIGHTS = {
    0: 0.75, 1: 0.8, 2: 0.8, 3: 0.8, 4: 0.8, 5: 0.85, 6: 0.7, 7: 0.25,
    8: 0.5, 9: 0.65, 10: 0.6, 11: 0.7, 12: 0.65, 13: 0.7, 14: 0.75,
}
_THINK_MIN_DWELL = 1.2
_THINK_CUE_TTL = 2.5


_THINK_STEP_POSE = {"new_turn": _THINK_HOME, "tool": 2, "inner": 1}

_THINK_DWELL_SCALE_CALM = 1.2
_THINK_DWELL_SCALE_HOT = 0.6


_THINK_GLANCE_HZ = 0.23
_THINK_GLANCE_GATE = 0.8
_THINK_GLANCE_AMT = 0.35
_THINK_SETTLE = 0.6
_THINK_TILT_DEG = 10.0
_THINK_LEAN = 0.06
_THINK_SINK = 0.055
_THINK_SQUASH = 0.05
_THINK_SWAY_HZ = 0.9
_THINK_SWAY_DEG = 1.2
_THINK_SCRATCH_TILT = 3.0
_THINK_SCRATCH_HZ = 2.2
_THINK_SCRATCH_DEG = 2.5
_THINK_TEMPLE_TILT = 2.0
_THINK_TAP_HZ = 5.0
_THINK_HAND_R = 0.095


_FX_EDGE_FADE = 32.0


def _edge_alpha(y: float, win_h: float) -> float:
    """特效靠近窗口上下边缘把透明度淡到0"""
    near_top = y / _FX_EDGE_FADE
    near_bottom = (win_h - y) / _FX_EDGE_FADE
    return max(0.0, min(1.0, near_top, near_bottom))


def _lerp(a: QPointF, b: QPointF, t: float) -> QPointF:
    return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)


def _weighted_pick(weights: dict[int, float], exclude: int | None = None) -> int:
    """按权重抽一个pose 排掉exclude"""
    items = [(k, w) for k, w in weights.items() if k != exclude]
    if not items:
        return _THINK_HOME
    r = random.uniform(0.0, sum(w for _, w in items))
    upto = 0.0
    for k, w in items:
        upto += w
        if r <= upto:
            return k
    return items[-1][0]


class BlobPet:
    """桌宠形象本体 状态机加绘制"""

    def __init__(self) -> None:
        self._t = 0.0
        self._expr = "neutral"
        self._costume: str | None = None
        self._talking = False
        self._blinking = False
        self._blink_e = 0.0
        self._next_blink = random.uniform(1.0, 3.0)
        self._react: tuple[str, float, float] | None = None
        self._react_intensity = 1.0
        self._shy = False
        self._shy_e = 0.0
        self._hot = False
        self._hot_e = 0.0
        self._squeeze = False
        self._squeeze_e = 0.0
        self._lowbatt = False
        self._lowbatt_e = 0.0
        self._blanket = False
        self._blanket_e = 0.0
        self._cake = False
        self._cake_e = 0.0
        self._cake_lit = True
        self._cake_smoke = 0.0
        self.on_activity_done = None  # 小品演完的回调 上层挂
        self._weather = ""  # rain snow melt
        self._weather_e = 0.0
        self._calm_e = 1.0  # 非演出的渐变量 装饰让位演出
        self._settle = 0.0
        self._hold = 0.0
        self._busy = False
        self._lecturing = False
        self._turn = 0.0
        self._turn_target = 0.0
        self._look_timer = random.uniform(2.0, 4.0)
        self._look_hold = 0.0
        self._fidget_timer = random.uniform(14.0, 28.0)
        self._daydream_timer = random.uniform(*_DAYDREAM_GAP)
        self._daydream_left = 0.0
        self._dream_spawn = 0.0
        self._dream_bubbles: list[list] = []
        self._win_h = 220.0
        self._fx_origin_y = 110.0
        self._activity: str | None = None
        self._act_sticky = False  # 点名要求的演出 说话思考不打断
        self._pending_perform: str | None = None
        self._wants_travel = False
        self._activity_timer = random.uniform(*_ACTIVITY_GAP)
        self._stage_i = 0
        self._stage_left = 0.0
        self._stage_dur = 1.0
        self._stage_p = 0.0
        self._activity_bubble = 0.0
        self._think_e = 0.0
        self._think_pose = 0
        self._think_pose_prev = 0
        self._think_xfade = 1.0
        self._think_dwell_left = 0.0
        self._think_held = 0.0
        self._think_cue_pose: int | None = None
        self._think_cue_age = 0.0
        self._think_energy = 0.5
        self._asleep = False
        self._falling_asleep = False
        self._sleep_e = 0.0
        self._dragging = False
        self._hidden = False
        self._catnap_timer = random.uniform(*_CATNAP_GAP)
        self._catnap_left = 0.0


    def set_shy(self, on: bool) -> None:
        """看到密码框捂眼回避"""
        self._shy = bool(on)

    def set_hot(self, on: bool) -> None:
        """cpu烧起来了 冒汗扇扇子"""
        self._hot = bool(on)

    def set_squeeze(self, on: bool) -> None:
        """内存满了被挤扁"""
        self._squeeze = bool(on)

    def set_low_batt(self, on: bool) -> None:
        """电量告急 焦躁"""
        self._lowbatt = bool(on)

    def set_blanket(self, on: bool) -> None:
        """深夜盖小被子"""
        self._blanket = bool(on)

    def set_cake(self, on: bool) -> None:
        """端出纪念日蛋糕"""
        self._cake = bool(on)
        if on:
            self._cake_lit = True
            self._cake_smoke = 0.0

    def blow_cake(self) -> bool:
        """吹蜡烛 蜡烛亮着才有效"""
        if not self._cake or not self._cake_lit:
            return False
        self._cake_lit = False
        self._cake_smoke = 2.2
        return True

    def set_weather(self, kind: str) -> None:
        """天气拟态 rain打伞 snow堆雪人 melt热化"""
        if kind in ("rain", "snow", "melt"):
            self._weather = kind
        else:
            self._weather = ""

    def set_expression(self, name: str) -> None:
        if name in _EXPRESSIONS:
            self._expr = name
            self._hold = 0.0 if name == "neutral" else _EXPR_HOLD

    def set_costume(self, name: str | None) -> None:
        self._costume = name if name in props.COSTUMES else None
        if self._costume:
            self._hold = max(self._hold, _EXPR_HOLD)

    def set_talking(self, on: bool) -> None:
        self._talking = on

    @property
    def is_talking(self) -> bool:
        return self._talking

    def set_busy(self, busy: bool) -> None:
        # busy时强制思考脸并清掉发呆反应
        self._busy = busy
        if busy:
            self._expr = "thinking"
            self._hold = 0.0
            self._react = None
            self._settle = 0.0
            self._dream_bubbles = []
            self._daydream_left = 0.0
        elif self._expr == "thinking":
            self.set_expression("neutral")

    def set_lecturing(self, on: bool) -> None:
        self._lecturing = on

    @property
    def _pondering(self) -> bool:
        return self._busy or self._expr == "thinking"

    @property
    def _performing(self) -> bool:
        """正在说话思考演反应或小品 环境装饰要让位"""
        return (self._talking or self._busy or self._lecturing or self._dragging
                or self._hidden or self._react is not None or self._activity is not None
                or self._expr == "thinking")

    @property
    def _worn_costume(self) -> bool:
        return self._costume in props.WORN_COSTUMES

    def set_think_energy(self, arousal: float) -> None:
        self._think_energy = max(0.0, min(1.0, arousal))

    def on_think_step(self, kind: str) -> None:
        """agent每出一步给个暗示pose"""
        pose = _THINK_STEP_POSE.get(kind)
        if pose is not None:
            self._think_cue_pose = pose
            self._think_cue_age = 0.0

    def fall_asleep(self) -> None:
        if self._asleep or self._falling_asleep:
            return
        if (self._busy or self._pondering or self._talking or self._lecturing
                or self._activity or self._dragging):
            return                      # 非空闲不睡
        self._falling_asleep = True
        self.react("yawn")

    def wake(self) -> None:
        if self._asleep or self._falling_asleep:
            self._asleep = False
            self._falling_asleep = False
            self.react("stretch")

    @property
    def is_asleep(self) -> bool:
        return self._asleep or self._falling_asleep

    @property
    def is_catnapping(self) -> bool:
        return self._catnap_left > 0.0

    def set_dragging(self, on: bool) -> None:
        self._dragging = on

    def set_hidden(self, on: bool) -> None:
        self._hidden = on

    def look_at(self, turn: float) -> None:
        if self._asleep or self._dragging:
            return
        self._turn_target = max(-1.0, min(1.0, turn))
        self._look_hold = _LOOK_AT_HOLD

    def celebrate(self) -> None:
        self.set_expression("happy")
        self.set_costume("party")
        self.react("celebrate")

    def slump(self) -> None:
        self.set_expression("sad")
        self.set_costume("raincloud")
        self.react("slump")

    def react(self, name: str, intensity: float = 1.0) -> None:
        if self._activity is not None and self._act_sticky:
            return  # 点名演出进行中 身体反应让位 表情不受影响
        spec = registry.get(name)
        if spec is not None and spec.category == Category.REACTION:
            self._react = (name, 0.0, spec.duration)
            self._react_intensity = intensity

    def start_activity(self, name: str) -> bool:
        if name not in _ACTIVITIES:
            return False
        self.wake()
        self._react = None
        self._activity = name
        self._act_sticky = True  # 点名演出 自己的回复气泡不许掐它
        self._costume = _ACTIVITIES[name][0]
        self._stage_i = 0
        self._enter_stage(_ACTIVITIES[name][3][0])
        self._activity_timer = random.uniform(*_ACTIVITY_GAP)
        return True

    @property
    def is_reacting(self) -> bool:
        return self._react is not None

    @property
    def in_activity(self) -> bool:
        return self._activity is not None

    def take_travel_request(self) -> bool:
        """取走一次穿越请求"""
        if self._wants_travel:
            self._wants_travel = False
            return True
        return False

    def clear_pending(self) -> None:
        self._pending_perform = None

    def perform(self, name: str) -> bool:
        """点名小品或反应 入队等空闲再播"""
        if name in _ACTIVITIES or (
            (spec := registry.get(name)) is not None and spec.category == Category.REACTION
        ):
            self._pending_perform = name
            self.wake()
            return True
        return False

    def _do_perform(self, name: str) -> None:
        if name in _ACTIVITIES:
            self.start_activity(name)
        else:
            self.react(name)


    def advance(self, dt: float) -> None:
        """每帧推进一次状态机"""
        self._t += dt
        if self._pending_perform is not None and not (
            self._busy or self._pondering or self._talking or self._asleep
            or self._dragging or self._hidden or self._react or self._activity
        ):
            name, self._pending_perform = self._pending_perform, None
            self._do_perform(name)
        if self._pondering:
            if self._think_e <= 0.0:
                self._enter_think()
            self._think_e = min(1.0, self._think_e + dt)
            self._advance_think(dt)
        else:
            self._think_e = max(0.0, self._think_e - dt * 2.0)
        if self._asleep:
            self._sleep_e = min(1.0, self._sleep_e + dt / _SLEEP_FADE)
        else:
            self._sleep_e = max(0.0, self._sleep_e - dt / _SLEEP_FADE * 1.5)
        if self._shy:
            self._shy_e = min(1.0, self._shy_e + dt * 3.5)
        else:
            self._shy_e = max(0.0, self._shy_e - dt * 2.5)
        for flag, attr in (("_hot", "_hot_e"), ("_squeeze", "_squeeze_e"),
                           ("_lowbatt", "_lowbatt_e"), ("_cake", "_cake_e")):
            e = getattr(self, attr)
            if getattr(self, flag):
                setattr(self, attr, min(1.0, e + dt * 1.6))
            else:
                setattr(self, attr, max(0.0, e - dt * 1.2))
        # 被子只有真睡着才盖 醒了就掀
        if self._blanket and self._asleep:
            self._blanket_e = min(1.0, self._blanket_e + dt * 1.6)
        else:
            self._blanket_e = max(0.0, self._blanket_e - dt * 2.0)
        # 只有真正"演出"(小品/反应/拖拽/藏起)时环境装饰才平滑退场——
        # 说话/思考不算，否则伞之类的持续装饰会随每句话一闪一闪
        if self._dragging or self._hidden or self._react is not None or self._activity is not None:
            self._calm_e = max(0.0, self._calm_e - dt * 3.5)
        else:
            self._calm_e = min(1.0, self._calm_e + dt * 2.0)
        if self._cake_smoke > 0.0:
            self._cake_smoke = max(0.0, self._cake_smoke - dt)
        if self._weather:
            self._weather_e = min(1.0, self._weather_e + dt * 1.2)
        else:
            self._weather_e = max(0.0, self._weather_e - dt * 1.0)
        if self._hold > 0.0 and not self._busy and self._activity is None:
            self._hold -= dt
            if self._hold <= 0.0:
                self._expr = "neutral"
                self._costume = None
        self._advance_blink(dt)
        self._advance_look(dt)
        self._advance_daydream(dt)
        self._advance_activity(dt)
        self._advance_catnap(dt)
        if self._react:
            name, elapsed, dur = self._react
            elapsed += dt
            if elapsed >= dur:
                self._react = None
                self._settle = _SETTLE_DUR
                self._fidget_timer = max(self._fidget_timer, random.uniform(9.0, 16.0))
                if self._falling_asleep:        # 哈欠放完才正式睡着
                    self._asleep = True
                    self._falling_asleep = False
            else:
                self._react = (name, elapsed, dur)
            return                              # 播反应时独占
        if self._settle > 0:
            self._settle = max(0.0, self._settle - dt)
        self._fidget_timer -= dt
        if self._fidget_timer <= 0:
            if not (self._pondering or self._asleep or self._dragging or self._hidden or self._talking
                    or self._lecturing or self._busy) and self._activity is None:
                fidget = selector.select(Category.REACTION, candidates=_IDLE_FIDGETS)
                if fidget:
                    self.react(fidget)
            self._fidget_timer = random.uniform(14.0, 28.0)

    def _advance_catnap(self, dt: float) -> None:
        # 自发打盹 有事立刻打断并重置计时
        if self._catnap_left > 0.0:
            if (self._busy or self._pondering or self._talking or self._lecturing
                    or self._dragging or self._activity):
                self._catnap_left = 0.0
                self._catnap_timer = random.uniform(*_CATNAP_GAP)
                self.wake()
                return
            self._catnap_left -= dt
            if self._catnap_left <= 0.0:
                self._catnap_left = 0.0
                self.wake()
            return
        if (self._pondering or self._asleep or self._falling_asleep or self._dragging
                or self._hidden or self._react or self._activity or self._talking
                or self._lecturing or self._busy):
            self._catnap_timer = random.uniform(*_CATNAP_GAP)
            return
        self._catnap_timer -= dt
        if self._catnap_timer <= 0.0:
            self._catnap_timer = random.uniform(*_CATNAP_GAP)
            if random.random() < _CATNAP_CHANCE:
                self._catnap_left = random.uniform(*_CATNAP_DUR)
                self.fall_asleep()

    def _advance_daydream(self, dt: float) -> None:
        idle = not (self._pondering or self._asleep or self._dragging or self._hidden or self._react or self._activity
                    or self._talking or self._lecturing or self._busy)
        if self._daydream_left > 0.0:
            self._daydream_left -= dt
            if not idle:
                self._daydream_left = 0.0
            else:
                self._dream_spawn -= dt
                if self._dream_spawn <= 0.0:
                    self._spawn_dream()
                    self._dream_spawn = random.uniform(*_DREAM_SPAWN)
        else:
            self._daydream_timer -= dt
            if self._daydream_timer <= 0.0:
                if idle:
                    self._daydream_left = random.uniform(*_DAYDREAM_DUR)
                    self._dream_spawn = 0.0
                self._daydream_timer = random.uniform(*_DAYDREAM_GAP)
        for bubble in self._dream_bubbles:
            bubble[2] += dt                     # age超寿命就剔掉
        self._dream_bubbles = [b for b in self._dream_bubbles if b[2] < b[3]]

    def _advance_activity(self, dt: float) -> None:
        # 小品逐阶段推进 走完最后一阶播收尾反应
        # 软打断(说话思考忙)只掐自发小品 点名的演完 硬打断(拖拽藏起睡着)谁都掐
        hard = self._asleep or self._dragging or self._hidden or self._react
        soft = self._pondering or self._talking or self._lecturing or self._busy
        idle = not (hard or soft)
        if self._activity is not None:
            if hard or (soft and not self._act_sticky):
                self._end_activity()
                return
            stages = _ACTIVITIES[self._activity][3]
            self._stage_left -= dt
            self._stage_dur = max(0.1, stages[self._stage_i][1])
            self._stage_p = 1.0 - max(0.0, self._stage_left) / self._stage_dur

            glyph = stages[self._stage_i][2]
            self._activity_bubble -= dt
            if glyph and self._activity_bubble <= 0.0:
                self._spawn_dream(glyph)
                self._activity_bubble = random.uniform(1.0, 2.2)
            if self._stage_left <= 0.0:
                self._stage_i += 1
                if self._stage_i >= len(stages):
                    done_name = self._activity
                    finish = _ACTIVITIES[self._activity][2]
                    self._end_activity()
                    self.react(finish)
                    if self.on_activity_done is not None:
                        try:
                            self.on_activity_done(done_name)
                        except Exception:
                            pass
                else:
                    self._enter_stage(stages[self._stage_i])
        else:
            self._activity_timer -= dt
            if self._activity_timer <= 0.0:
                self._activity_timer = random.uniform(*_ACTIVITY_GAP)
                if idle:
                    name = random.choice(list(_ACTIVITIES) + [_TRAVEL])  # 穿越混进抽签池
                    if name == _TRAVEL:
                        self._wants_travel = True
                    else:
                        self._activity = name
                        self._costume = _ACTIVITIES[name][0]
                        self._stage_i = 0
                        self._enter_stage(_ACTIVITIES[name][3][0])

    def _enter_stage(self, stage: tuple) -> None:
        self._stage_dur = max(0.1, stage[1])
        self._stage_left = self._stage_dur
        self._stage_p = 0.0
        self._activity_bubble = 0.0

    def _end_activity(self) -> None:
        self._activity = None
        self._act_sticky = False
        self._costume = None
        self._stage_i = 0
        self._stage_p = 0.0

    @property
    def _stage(self) -> str:
        if self._activity is None:
            return ""
        return _ACTIVITIES[self._activity][3][self._stage_i][0]

    def _activity_body_transform(self, bw: float, bh: float):
        """小品期间的身体位姿增量"""
        curve = _ACTIVITY_BODY.get(self._activity)
        if curve is None:
            return 0.0, 0.0, 0.0, 1.0, 1.0
        return curve(self._stage, self._stage_p, self._t, bw, bh)

    def _spawn_dream(self, glyph: str | None = None) -> None:
        self._dream_bubbles.append([
            glyph or random.choice(_DREAM_GLYPHS), random.uniform(-0.15, 0.55),
            0.0, random.uniform(*_DREAM_LIFE), random.choice(_DREAM_COLORS),
        ])

    def _draw_dream(self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float) -> None:
        font = smooth_font(QFont("Microsoft YaHei UI"))
        font.setPixelSize(max(11, int(bw * 0.26)))
        painter.setFont(font)
        for glyph, x_frac, age, life, color in self._dream_bubbles:
            frac = age / life                   # 前段淡入后段淡出 一边升一边飘
            if frac < 0.18:
                alpha = frac / 0.18
            elif frac > 0.6:
                alpha = max(0.0, (1.0 - frac) / 0.4)
            else:
                alpha = 1.0
            rise = ease_out(min(frac, 1.0)) * bh * 0.8
            x = cx + x_frac * bw + math.sin((age + x_frac) * 3.0) * bw * 0.05
            y = head_y - bh * 0.9 - rise
            alpha *= _edge_alpha(y, self._win_h)
            painter.setPen(QColor(color.red(), color.green(), color.blue(), int(225 * alpha)))
            painter.drawText(QPointF(x, y), glyph)

    def _advance_blink(self, dt: float) -> None:
        if self._blinking:
            self._blink_e += dt
            if self._blink_e >= _BLINK_DUR:
                self._blinking = False
                self._next_blink = random.uniform(2.5, 5.5)
        else:
            self._next_blink -= dt
            if self._next_blink <= 0:
                self._blinking = True
                self._blink_e = 0.0

    def _advance_look(self, dt: float) -> None:
        # 视线目标按优先级定
        if self._look_hold > 0.0:
            self._look_hold -= dt
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 6.0)
            return
        if self._activity is not None:
            self._turn_target = _ACTIVITIES[self._activity][1]
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 4.0)
            return
        if self._react is not None:
            self._turn_target = 0.0
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 5.0)
            return
        if self._pondering:
            wander = math.sin(self._t * _THINK_GLANCE_HZ)
            if abs(wander) > _THINK_GLANCE_GATE:    # 过门限才偏头看一眼
                reach = (abs(wander) - _THINK_GLANCE_GATE) / (1.0 - _THINK_GLANCE_GATE)
                self._turn_target = math.copysign(reach, wander) * _THINK_GLANCE_AMT
            else:
                self._turn_target = 0.0
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 3.0)
            return
        self._look_timer -= dt
        if self._look_timer <= 0:
            self._turn_target = random.choice([0.0, 0.0, 0.0, -0.8, 0.8, -0.5, 0.5])
            self._look_timer = random.uniform(1.5, 4.0)
        self._turn += (self._turn_target - self._turn) * min(1.0, dt * 4.0)


    def paint(self, painter: QPainter, w: int, h: int) -> None:
        """画一帧 各状态叠位姿增量后一次性变换出图"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._win_h = float(h)
        bw, bh = _BLOB_BASE * 0.62, _BLOB_BASE * 0.44
        cx, cy = w / 2, h / 2

        breath = math.sin(self._t * 2.0)       # 永远在呼吸
        ox = 0.0
        oy = breath * (bh * 0.032)
        rot = math.sin(self._t * 0.8) * 1.5
        sxm, sym = 1 - 0.06 * breath, 1 + 0.06 * breath

        if self._talking:
            oy += math.sin(self._t * 16) * (bh * 0.02)
        if self._expr == "confused":
            rot += math.sin(self._t * 2.4) * 4
        if self._lecturing:
            rot += math.sin(self._t * 1.6) * 2
        if self._dragging:
            rot += math.sin(self._t * _DRAG_SWAY_HZ) * _DRAG_SWAY_DEG
            oy += _DRAG_SINK * bh
            sxm *= 1 - _DRAG_STRETCH * 0.5
            sym *= 1 + _DRAG_STRETCH


        think_gate = ease_out(min(self._think_e / _THINK_SETTLE, 1.0))
        # 穿戏服时不叠思考姿势也不画思考手
        if think_gate > 0.0 and not self._react and not self._worn_costume:
            d_ox, d_oy, d_rot, d_sx, d_sy = self._think_transform(bw, bh, think_gate)
            ox += d_ox
            oy += d_oy
            rot += d_rot
            sxm *= d_sx
            sym *= d_sy

        if self._react:
            name, elapsed, dur = self._react
            d_ox, d_oy, d_rot, mx, my = self._react_transform(name, min(elapsed / dur, 1.0), bw, bh)
            k = self._react_intensity
            ox += d_ox * k
            oy += d_oy * k
            rot += d_rot * k
            sxm *= 1 + (mx - 1) * k
            sym *= 1 + (my - 1) * k
        elif self._settle > 0:
            te = _SETTLE_DUR - self._settle
            damp = math.exp(-te * 9) * math.sin(te * 38)    # 反应收尾衰减正弦回弹
            sym *= 1 + 0.09 * damp
            sxm *= 1 - 0.09 * damp

        if self._sleep_e > 0.0:
            slow = math.sin(self._t * _SLEEP_BREATH_HZ)
            oy += self._sleep_e * (_SLEEP_SINK * bh + slow * bh * 0.025)
            sxm *= 1 - 0.05 * self._sleep_e * slow
            sym *= 1 + 0.05 * self._sleep_e * slow

        if self._activity is not None:
            a_ox, a_oy, a_rot, a_sx, a_sy = self._activity_body_transform(bw, bh)
            ox += a_ox
            oy += a_oy
            rot += a_rot
            sxm *= a_sx
            sym *= a_sy

        if self._shy_e > 0.0:
            # 害羞侧身缩一点
            rot += self._shy_e * 7
            sxm *= 1 - 0.04 * self._shy_e
            oy += self._shy_e * bh * 0.02
        calm = self._calm_e  # 演出期间环境拟态全部让位
        if self._squeeze_e > 0.0 and calm > 0.0:
            # 被内存挤扁
            k = self._squeeze_e * calm
            sym *= 1 - 0.22 * k
            sxm *= 1 + 0.16 * k
            oy += bh * 0.1 * k
        if self._hot_e > 0.0 and calm > 0.0:
            # 热得发蔫 缓慢晃
            k = self._hot_e * calm
            oy += bh * 0.02 * k
            rot += math.sin(self._t * 1.1) * 2.0 * k
        if self._lowbatt_e > 0.0 and calm > 0.0:
            # 没电焦躁 高频小颤
            ox += math.sin(self._t * 23) * bw * 0.008 * self._lowbatt_e * calm
        if self._weather == "melt" and self._weather_e > 0.0 and calm > 0.0:
            # 热到化了 摊下去
            k = self._weather_e * calm
            sym *= 1 - 0.14 * k
            sxm *= 1 + 0.10 * k
            oy += bh * 0.07 * k

        head_y = cy + oy
        painter.save()
        painter.translate(cx + ox, head_y)
        painter.rotate(rot)
        painter.scale(sxm, sym)
        self._draw_body(painter, bw, bh)
        self._draw_eyes(painter, bw, bh)
        self._draw_mouth(painter, bw, bh)
        self._draw_costume_worn(painter, bw, bh)
        if self._shy_e > 0.01:
            adornments.draw_shy_hands(painter, bw, bh, self._shy_e, self._t)
        if self._squeeze_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_squeeze_marks(painter, bw, bh, self._squeeze_e * self._calm_e, self._t)
        if self._hot_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_hot(painter, bw, bh, self._hot_e * self._calm_e, self._t)
        if self._blanket_e > 0.01:
            adornments.draw_blanket(painter, bw, bh, self._blanket_e, self._t)
        if self._lowbatt_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_lowbatt(painter, bw, bh, self._lowbatt_e * self._calm_e, self._t)
        if self._weather_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_weather(painter, bw, bh, self._weather, self._weather_e * self._calm_e, self._t)
        if think_gate > 0.01 and not self._react and not self._worn_costume and self._shy_e < 0.3:
            self._draw_think_hand(painter, bw, bh, think_gate)
        if self._lecturing:
            props.draw_pointer(painter, bw, bh, self._t)
        painter.restore()

        self._draw_costume_ambient(painter, cx, head_y, bw, bh)
        if self._cake_e > 0.01 or self._cake_smoke > 0.0:
            adornments.draw_cake(
                painter, cx, head_y, bw, bh,
                self._cake_e, self._cake_lit, self._cake_smoke, self._t,
            )
        if self._sleep_e > 0.01:
            self._draw_zzz(painter, cx, head_y, bw, bh, self._sleep_e)


        if self._expr == "confused":
            self._draw_question(painter, cx, head_y, bw, bh)
        if self._dream_bubbles:
            self._draw_dream(painter, cx, head_y, bw, bh)
        if self._react:
            rname, relapsed, rdur = self._react
            self._draw_react_fx(painter, rname, min(relapsed / rdur, 1.0), cx, head_y, bw, bh)

    def _react_transform(
        self, name: str, p: float, bw: float, bh: float
    ) -> tuple[float, float, float, float, float]:
        return registry.evaluate(name, p, bw, bh)


    _FX_NOTES = frozenset({"dance", "headbang", "purr"})
    _FX_CONFETTI = frozenset({"cheer", "celebrate"})
    _FX_SWOOSH = frozenset({"spin", "jump_spin", "roll", "flip"})
    _FX_SHOCK = frozenset({"gasp", "double_take", "recoil"})
    _FX_RING = frozenset({"pop", "boing"})


    _FX_GLOOM = frozenset({"slump", "droop", "deflate", "sigh", "splat"})
    _FX_MUNCH = frozenset({"eating"})
    _FX_TICKLE = frozenset({"giggle"})
    _FX_WARM = frozenset({"snuggle"})
    _FX_WAVE = frozenset({"wave"})

    def _draw_react_fx(self, painter: QPainter, name: str, p: float, cx: float, cy: float,
                       bw: float, bh: float) -> None:
        """按反应名分发到对应特效"""
        if name not in (self._FX_NOTES | self._FX_CONFETTI | self._FX_SWOOSH | self._FX_SHOCK
                        | self._FX_RING | self._FX_GLOOM | self._FX_MUNCH | self._FX_TICKLE
                        | self._FX_WARM | self._FX_WAVE):
            return
        painter.save()
        self._fx_origin_y = cy
        painter.translate(cx, cy)
        if name in self._FX_NOTES:
            self._fx_notes(painter, p, bw, bh)
        elif name in self._FX_CONFETTI:
            self._fx_confetti(painter, p, bw, bh)
        elif name in self._FX_SWOOSH:
            self._fx_swoosh(painter, p, bw, bh)
        elif name in self._FX_SHOCK:
            self._fx_shock(painter, p, bw, bh)
        elif name in self._FX_RING:
            self._fx_ring(painter, p, bw, bh)
        elif name in self._FX_GLOOM:
            self._fx_gloom(painter, p, bw, bh)
        elif name in self._FX_MUNCH:
            self._fx_munch(painter, p, bw, bh)
        elif name in self._FX_TICKLE:
            self._fx_tickle(painter, p, bw, bh)
        elif name in self._FX_WARM:
            self._fx_warm(painter, p, bw, bh)
        elif name in self._FX_WAVE:
            self._fx_wave(painter, p, bw, bh)
        painter.restore()

    def _fx_wave(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """身侧的手画弧挥动"""
        gate = math.sin(min(p * 4, 1.0, (1 - p) * 4) * math.pi / 2)
        if gate <= 0.01:
            return
        swing = math.sin(p * math.pi * 6)
        hx = bw * 0.55 + swing * bw * 0.10
        hy = -bh * 0.30 - gate * bh * 0.16 - abs(swing) * bh * 0.05
        painter.setPen(self._think_hand_pen(bw))
        painter.setBrush(_SKIN)
        painter.drawEllipse(QPointF(hx, hy), bw * 0.10 * gate, bw * 0.10 * gate)

    def _fx_warm(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """身侧升起的热气波纹"""
        gate = math.sin(min(p * 3, 1.0, (1 - p) * 3) * math.pi / 2)
        for k in range(3):
            ph = (p * 1.6 + k * 0.33) % 1.0
            x0 = (k - 1) * bw * 0.34
            rise = ph * bh * 0.7
            a = max(0, int(170 * gate * math.sin(ph * math.pi)))
            pen = QPen(QColor(238, 150, 92, a))
            pen.setWidthF(max(1.6, bw * 0.018))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pts = QPolygonF()
            for i in range(9):
                t = i / 8.0
                pts.append(QPointF(x0 + math.sin((t * 2.2 + ph * 2) * math.pi) * bw * 0.05,
                                   bh * 0.1 - rise - t * bh * 0.28))
            painter.drawPolyline(pts)

    def _fx_tickle(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """痒得乱蹦的小星和墨点"""
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(7):
            ph = (p * 2.4 + k * 0.29) % 1.0
            side = 1 if k % 2 == 0 else -1
            x = side * (bw * 0.32 + ph * bw * 0.3) + math.sin(ph * math.pi * 3 + k) * bw * 0.04
            y = bh * 0.1 - math.sin(ph * math.pi) * bh * 0.55
            a = max(0, int(225 * (1 - ph)))
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(a)
            if k % 3 == 0:
                # 四角小星
                pen = QPen(col)
                pen.setWidthF(max(1.4, bw * 0.014))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                r = bw * 0.030 * (1 - ph * 0.4)
                painter.drawLine(QPointF(x - r, y), QPointF(x + r, y))
                painter.drawLine(QPointF(x, y - r), QPointF(x, y + r))
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                rr = bw * 0.018 * (1 - ph * 0.5)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(x, y), rr, rr)

    def _fx_munch(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """吃东西全程特效 文件落下 碎屑 咕咚 打嗝星"""
        mouth_y = bh * 0.26
        if p < 0.15:
            # 小文件从头顶落进嘴里 越落越小
            k = ease_in(p / 0.15)
            fy = -bh * 0.95 + (mouth_y + bh * 0.95) * k
            s = bw * 0.16 * (1 - 0.45 * k)
            painter.setPen(QPen(QColor(120, 118, 140, 230), max(1.2, bw * 0.012)))
            painter.setBrush(QColor(252, 252, 255, 240))
            painter.save()
            painter.translate(0.0, fy)
            painter.rotate(k * 24)
            painter.drawRoundedRect(QRectF(-s / 2, -s * 0.62, s, s * 1.24), s * 0.12, s * 0.12)
            # 折角和两道字纹
            painter.setBrush(QColor(214, 212, 232, 240))
            painter.drawPolygon(QPolygonF([QPointF(s * 0.5 - s * 0.3, -s * 0.62),
                                           QPointF(s * 0.5, -s * 0.62 + s * 0.3),
                                           QPointF(s * 0.5, -s * 0.62)]))
            for i in (0, 1):
                yy = -s * 0.15 + i * s * 0.3
                painter.drawRect(QRectF(-s * 0.3, yy, s * 0.6, s * 0.07))
            painter.restore()
            return
        if p < 0.55:
            # 嘴边崩碎屑 左右交替
            q = (p - 0.15) / 0.4
            painter.setPen(Qt.PenStyle.NoPen)
            for k in range(5):
                ph = (q * 3 + k * 0.37) % 1.0
                side = 1 if k % 2 == 0 else -1
                x = side * (bw * 0.1 + ph * bw * 0.22)
                y = mouth_y + ph * bh * 0.3 - math.sin(ph * math.pi) * bh * 0.12
                col = QColor(_INK)
                col.setAlpha(max(0, int(200 * (1 - ph))))
                painter.setBrush(col)
                r = bw * 0.014 * (1 - ph * 0.5)
                painter.drawEllipse(QPointF(x, y), r, r)
            return
        if p < 0.75:
            # 咕咚 一个圈从嘴滑到肚子
            q = (p - 0.55) / 0.2
            y = mouth_y + q * bh * 0.34
            alpha = max(0, int(150 * math.sin(q * math.pi)))
            pen = QPen(QColor(150, 170, 215, alpha))
            pen.setWidthF(max(1.2, bw * 0.014))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0.0, y), bw * 0.1 * (1 - q * 0.3), bh * 0.045 * (1 - q * 0.3))
            return
        # 打嗝小星星往上飘
        q = (p - 0.75) / 0.25
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            ph = max(0.0, q - k * 0.18)
            if ph <= 0:
                continue
            x = (k - 1) * bw * 0.16 + math.sin(ph * math.pi * 2 + k) * bw * 0.05
            y = -bh * 0.55 - ph * bh * 0.5
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(max(0, int(230 * (1 - ph))))
            painter.setBrush(col)
            r = bw * (0.030 - 0.008 * k)
            star = QPolygonF()
            for i in range(8):
                ang = i * math.pi / 4 - math.pi / 2
                rad = r if i % 2 == 0 else r * 0.45
                star.append(QPointF(x + math.cos(ang) * rad, y + math.sin(ang) * rad))
            painter.drawPolygon(star)

    def _fx_notes(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        for k in range(4):
            ph = (p * 1.7 + k / 4.0) % 1.0
            side = 1 if k % 2 == 0 else -1
            x = side * (bw * 0.46 + bw * 0.10 * math.sin(self._t * 3 + k))
            y = -bh * 0.18 - ph * bh * 0.95
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            col.setAlpha(max(0, int(math.sin(ph * math.pi) * 230)))
            props.draw_note(painter, QPointF(x, y), bw, bh, col, double=(k % 2 == 0))

    def _fx_confetti(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        n = 14
        for k in range(n):
            ang = -math.pi / 2 + (k - n / 2) / n * 2.4
            spd = 0.7 + ((k * 37) % 11) / 11.0 * 0.6
            launch = bw * 0.85 * spd
            x = math.cos(ang) * launch * p
            y = -bh * 0.55 + math.sin(ang) * launch * p + bh * 2.0 * p * p
            col = QColor(_DREAM_COLORS[k % len(_DREAM_COLORS)])
            edge = _edge_alpha(self._fx_origin_y + y, self._win_h)
            col.setAlpha(max(0, int(255 * (1 - p * 0.6) * edge)))
            painter.setBrush(col)
            painter.save()
            painter.translate(x, y)
            painter.rotate((self._t * 260 + k * 53) % 360)
            painter.drawRect(QRectF(-bw * 0.022, -bw * 0.013, bw * 0.044, bw * 0.026))
            painter.restore()

    def _fx_swoosh(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        pen = QPen(QColor(150, 170, 215, max(0, int(190 * (1 - p)))))
        pen.setWidthF(max(1.5, bw * 0.018))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        base = self._t * 680
        rect = QRectF(-bw * 0.62, -bh * 0.78, bw * 1.24, bh * 1.5)
        for k in range(3):
            painter.drawArc(rect, int((base + k * 120) * 16), int(54 * 16))

    def _fx_shock(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        k = max(0.0, 1.0 - p / 0.55)
        if k <= 0.02:
            return
        pen = QPen(QColor(90, 92, 110, int(230 * k)))
        pen.setWidthF(max(1.5, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        oy = -bh * 0.72
        for deg in range(0, 360, 45):
            a = math.radians(deg)
            r0 = bh * (0.18 + 0.12 * (1 - k))
            r1 = r0 + bh * 0.18
            painter.drawLine(QPointF(math.cos(a) * r0, oy + math.sin(a) * r0 * 0.7),
                             QPointF(math.cos(a) * r1, oy + math.sin(a) * r1 * 0.7))

    def _fx_ring(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        r = (0.35 + ease_out(p) * 0.45) * bw
        pen = QPen(QColor(150, 180, 230, max(0, int(235 * (1 - p) ** 0.7))))
        pen.setWidthF(max(2.0, bw * 0.03) * (1 - p * 0.5))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0.0, 0.0), r, r * 0.82)

    def _fx_gloom(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            ph = (p * 1.3 + k * 0.26) % 1.0
            x = bw * 0.34 + ph * bw * 0.40
            y = -bh * 0.08 - ph * bh * 0.30
            r = bh * (0.05 + 0.09 * ph)
            painter.setBrush(QColor(172, 177, 188, max(0, int(150 * math.sin(ph * math.pi)))))
            painter.drawEllipse(QPointF(x, y), r, r * 0.8)


    def _enter_think(self) -> None:
        self._think_pose = _THINK_HOME
        self._think_pose_prev = _THINK_HOME
        self._think_xfade = 1.0
        self._think_held = 0.0
        self._think_cue_pose = None
        self._think_dwell_left = random.uniform(0.6, 1.4)

    def _advance_think(self, dt: float) -> None:
        # 思考姿势换位调度 cue优先于随机轮换 停够再换 超时作废
        if self._think_xfade < 1.0:
            self._think_xfade = min(1.0, self._think_xfade + dt / _THINK_XFADE_DUR)
        self._think_held += dt
        self._think_dwell_left -= dt
        if self._think_cue_pose is not None:
            self._think_cue_age += dt
            if self._think_held >= _THINK_MIN_DWELL and self._think_cue_pose != self._think_pose:
                self._begin_think_transition(self._think_cue_pose)
                self._think_cue_pose = None
                return
            if self._think_cue_age >= _THINK_CUE_TTL:
                self._think_cue_pose = None
        if self._think_dwell_left <= 0.0:
            self._begin_think_transition(self._next_think_pose())

    def _next_think_pose(self) -> int:
        return _weighted_pick(_THINK_POSE_WEIGHTS, exclude=self._think_pose)

    def _roll_dwell(self, pose: int) -> float:
        # 停留时长随机抽 energy越高越短
        lo, hi = _THINK_DWELL[pose]
        scale = _THINK_DWELL_SCALE_CALM + (_THINK_DWELL_SCALE_HOT - _THINK_DWELL_SCALE_CALM) * self._think_energy
        return random.uniform(lo, hi) * scale

    def _begin_think_transition(self, target: int) -> None:
        self._think_pose_prev = self._think_pose
        self._think_pose = target
        self._think_xfade = 0.0
        self._think_held = 0.0
        self._think_dwell_left = self._roll_dwell(target)

    def _think_transform(
        self, bw: float, bh: float, s: float
    ) -> tuple[float, float, float, float, float]:
        cur = self._pose_motion(self._think_pose, bw, bh, s)
        if self._think_xfade >= 1.0:            # 没在过渡省掉上一姿势计算
            return cur
        prev = self._pose_motion(self._think_pose_prev, bw, bh, s)
        e = ease_out(self._think_xfade)
        return tuple(p + (c - p) * e for p, c in zip(prev, cur))

    def _pose_motion(
        self, idx: int, bw: float, bh: float, g: float
    ) -> tuple[float, float, float, float, float]:
        # 第idx号思考姿势的身体位姿 g是淡入门控
        t = self._t
        if idx == 0:
            rot = _THINK_TILT_DEG * g + math.sin(t * _THINK_SWAY_HZ) * _THINK_SWAY_DEG * g
            ox = -_THINK_LEAN * bw * g
            oy = _THINK_SINK * bh * g + math.sin(t * _THINK_SWAY_HZ + 1.3) * bh * 0.012 * g
            return ox, oy, rot, 1 + _THINK_SQUASH * 0.6 * g, 1 - _THINK_SQUASH * g
        if idx == 1:
            rot = (-_THINK_SCRATCH_TILT + math.sin(t * _THINK_SCRATCH_HZ) * _THINK_SCRATCH_DEG) * g
            ox = -bw * 0.02 * g
            oy = (-bh * 0.02 + math.sin(t * _THINK_SCRATCH_HZ * 2) * bh * 0.01) * g
            return ox, oy, rot, 1 - 0.02 * g, 1 + 0.02 * g
        if idx == 2:
            rot = (_THINK_TEMPLE_TILT + math.sin(t * 1.2)) * g
            return bw * 0.015 * g, math.sin(t * 1.5) * bh * 0.008 * g, rot, 1.0, 1.0
        if idx == 3:
            rot = -8.0 * g + math.sin(t * 0.7) * 1.4 * g
            return bw * 0.01 * g, -bh * 0.03 * g, rot, 1 - 0.015 * g, 1 + 0.03 * g
        if idx == 4:
            rot = 13.0 * g + math.sin(t * 0.8) * 1.6 * g
            return bw * 0.03 * g, bh * 0.005 * g, rot, 1.0, 1.0
        if idx == 5:
            nod = math.sin(t * 1.6)
            return 0.0, nod * bh * 0.018 * g, nod * 1.3 * g, 1.0, 1.0
        if idx == 6:
            sway = math.sin(t * 1.3)
            return sway * bw * 0.05 * g, 0.0, sway * 1.6 * g, 1.0, 1.0
        if idx == 7:
            return 0.0, -bh * 0.06 * g, math.sin(t * 3.0) * 1.5 * g, 1 - 0.03 * g, 1 + 0.06 * g
        if idx == 8:
            return 0.0, bh * 0.035 * g, -2.0 * g, 1 + 0.035 * g, 1 - 0.05 * g
        if idx == 9:
            return math.sin(t * 2.8) * bw * 0.01 * g, 0.0, math.sin(t * 2.8) * 5.0 * g, 1.0, 1.0
        if idx == 10:
            return 0.0, math.sin(t * 6.0) * bh * 0.006 * g, math.sin(t * 1.5) * 0.8 * g, 1.0, 1.0
        if idx == 11:
            return 0.0, bh * 0.012 * g, math.sin(t * 0.9) * 0.8 * g, 1 + 0.04 * g, 1 + 0.04 * g
        if idx == 12:
            sway = math.sin(t * 0.6)
            return sway * bw * 0.13 * g, 0.0, sway * 3.0 * g, 1.0, 1.0
        if idx == 13:
            return 0.0, abs(math.sin(t * 2.2)) * bh * 0.03 * g, math.sin(t * 2.2) * 2.0 * g, 1.0, 1.0

        return 0.0, math.sin(t * 0.35) * bh * 0.008 * g, math.sin(t * 0.4) * 0.8 * g, 1.0, 1.0

    def _think_hand_pen(self, bw: float) -> QPen:
        pen = QPen(_OUTLINE)
        pen.setWidthF(max(2.0, bw * 0.018))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _hand_point(self, idx: int, bw: float, bh: float) -> QPointF:
        # 各思考姿势对应的手落点
        t = self._t
        if idx == 0:
            return QPointF(bw * 0.26, bh * 0.40)
        if idx == 1:
            return QPointF(bw * 0.10 + math.sin(t * _THINK_SCRATCH_HZ) * bw * 0.05, -bh * 0.44)
        if idx == 2:
            poke = math.sin(t * _THINK_TAP_HZ) * bw * 0.02
            return QPointF(bw * 0.40, -bh * 0.06 - poke)
        if idx == 3:
            return QPointF(bw * 0.24, bh * 0.40)
        if idx == 4:
            return QPointF(bw * 0.32, bh * 0.10)
        if idx == 5:
            return QPointF(bw * (0.18 + math.sin(t * 1.6) * 0.06), bh * 0.42)
        if idx == 6:
            return QPointF(bw * 0.05, bh * (0.22 - abs(math.sin(t * 2.6)) * 0.06))
        if idx == 7:
            return QPointF(bw * 0.22, -bh * 0.50)
        if idx == 8:
            return QPointF(bw * 0.16, -bh * 0.28)
        if idx == 9:
            return QPointF(bw * 0.06, bh * 0.42)
        if idx == 10:
            return QPointF(bw * 0.30, bh * 0.28 + math.sin(t * 9.0) * bh * 0.035)
        if idx == 11:
            return QPointF(bw * 0.24, bh * 0.40)
        if idx == 12:
            return QPointF(bw * 0.20, bh * 0.40)
        if idx == 13:
            return QPointF(bw * 0.20, bh * 0.40)

        return QPointF(bw * 0.22, bh * 0.44)

    def _draw_think_hand(self, painter: QPainter, bw: float, bh: float, s: float) -> None:
        target = self._hand_point(self._think_pose, bw, bh)
        if self._think_xfade < 1.0:
            target = _lerp(
                self._hand_point(self._think_pose_prev, bw, bh), target, ease_out(self._think_xfade)
            )
        emerge = QPointF(bw * 0.16, bh * 0.30)  # 手钻出来的起点 s控制冒出程度
        hand = _lerp(emerge, target, s)
        painter.setPen(self._think_hand_pen(bw))
        painter.setBrush(_SKIN)
        painter.drawEllipse(hand, bw * _THINK_HAND_R, bw * _THINK_HAND_R)

    def _draw_zzz(self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float, e: float) -> None:
        painter.save()
        painter.translate(cx + bw * 0.28, head_y - bh * 0.42)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            ph = ((self._t / _ZZZ_CYCLE) - i * _ZZZ_STAGGER) % 1.0  # 三个z错相位飘
            a = math.sin(ph * math.pi)
            if a <= 0.0:
                continue
            sz = bh * (0.13 + i * 0.07)
            x, y = i * bw * 0.16, -i * bh * 0.34 - bh * 0.25 * (1 - a)
            pen = QPen(QColor(_ZZZ_INK.red(), _ZZZ_INK.green(), _ZZZ_INK.blue(), int(_ZZZ_ALPHA_MAX * a * e)))
            pen.setWidthF(max(1.5, sz * 0.16))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(
                QPolygonF([QPointF(x, y), QPointF(x + sz, y), QPointF(x, y + sz), QPointF(x + sz, y + sz)])
            )
        painter.restore()

    def _draw_body(self, painter: QPainter, bw: float, bh: float) -> None:
        grad = QLinearGradient(0.0, -bh / 2, 0.0, bh / 2)
        grad.setColorAt(0.0, _SKIN)
        grad.setColorAt(1.0, QColor(233, 236, 242))
        painter.setBrush(grad)
        pen = QPen(_OUTLINE)
        pen.setWidthF(max(2.0, bw * 0.018))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(-bw / 2, -bh / 2, bw, bh), bh * 0.48, bh * 0.48)

    def _draw_eyes(self, painter: QPainter, bw: float, bh: float) -> None:
        # 按表情画眼
        if self._sleep_e > 0.0:
            self._draw_sleeping_eyes(painter, bw, bh, self._sleep_e)
            return
        eat_p = self._eating_progress()
        if eat_p is not None:
            self._draw_eating_eyes(painter, eat_p, bw, bh)
            return
        if self._react is not None:
            rname, relapsed, rdur = self._react
            rp = min(1.0, relapsed / max(rdur, 0.001))
            gate = math.sin(min(rp * 3, 1.0, (1 - rp) * 3) * math.pi / 2)  # 进出渐变
            if rname in ("giggle", "purr", "snuggle"):
                adornments.draw_blush(painter, bw, bh, gate)
                dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
                self._eye_arc(painter, -dx, ey, ew, eh)
                self._eye_arc(painter, dx, ey, ew, eh)
                return
            if rname in ("happy_wiggle", "cheer", "celebrate", "bounce", "hop2", "dance", "headbang", "wave"):
                # 开心系反应统一笑眼 表演感拉满
                dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
                self._eye_arc(painter, -dx, ey, ew, eh)
                self._eye_arc(painter, dx, ey, ew, eh)
                return
            if rname == "splat" and rp < 0.55:
                # 摔懵了 X眼
                pen = QPen(_INK)
                pen.setWidthF(max(2.0, bw * 0.022))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                dx, ey = bw * 0.24, bh * 0.05
                r = bw * 0.055
                for sx in (-1, 1):
                    cx = sx * dx
                    painter.drawLine(QPointF(cx - r, ey - r), QPointF(cx + r, ey + r))
                    painter.drawLine(QPointF(cx + r, ey - r), QPointF(cx - r, ey + r))
                return
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        shift = self._turn * bw * 0.1           # 朝向偏移眼珠 远侧眼压扁
        scale_l = 1 - max(self._turn, 0.0) * 0.55
        scale_r = 1 - max(-self._turn, 0.0) * 0.55
        expr = self._expr

        if expr == "happy":
            self._eye_arc(painter, -dx + shift, ey, ew * scale_l, eh)
            self._eye_arc(painter, dx + shift, ey, ew * scale_r, eh)
            return
        if expr == "sad":
            self._eye_oval(painter, -dx + shift, ey + bh * 0.04, ew * scale_l, eh * 0.6)
            self._eye_oval(painter, dx + shift, ey + bh * 0.04, ew * scale_r, eh * 0.6)
            return
        if expr == "thinking":
            up = ey - eh * 0.3
            self._eye_oval(painter, -dx + shift, up, ew * scale_l, eh)
            self._eye_oval(painter, dx + shift, up, ew * scale_r, eh)
            return
        if expr == "confused":
            opening = self._blink_open()
            self._eye_oval(painter, -dx + shift, ey, ew * scale_l, eh * opening)
            self._eye_oval(painter, dx + shift, ey + bh * 0.02, ew * scale_r, eh * 0.4)
            return

        opening = self._blink_open()
        if expr == "surprised":
            ew, eh, opening = ew * 1.35, eh * 1.3, 1.0
        self._eye_oval(painter, -dx + shift, ey, ew * scale_l, max(eh * opening, eh * 0.08))
        self._eye_oval(painter, dx + shift, ey, ew * scale_r, max(eh * opening, eh * 0.08))

    def _eye_oval(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_INK)
        painter.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), w / 2, w / 2)

    def _eye_arc(self, painter: QPainter, cx: float, cy: float, ew: float, eh: float) -> None:
        pen = QPen(_INK)
        pen.setWidthF(eh * 0.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(cx - ew, cy - eh * 0.4, ew * 2, eh * 0.9), 20 * 16, 140 * 16)

    def _draw_sleeping_eyes(self, painter: QPainter, bw: float, bh: float, e: float) -> None:
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        oh = eh * (1 - e)
        for sx in (-1, 1):
            cx = sx * dx
            if oh > eh * 0.06:
                self._eye_oval(painter, cx, ey, ew, oh)
            if e > 0.1:
                pen = QPen(_INK)
                pen.setWidthF(max(1.5, eh * 0.3 * e))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawArc(QRectF(cx - ew, ey - eh * 0.1, ew * 2, eh * 0.5), 200 * 16, 140 * 16)

    def _draw_eating_eyes(self, painter: QPainter, p: float, bw: float, bh: float) -> None:
        """吃东西的眼神 追着文件看 咀嚼眯眼 吞咽闭眼 打嗝瞪圆再变笑"""
        dx, ey, ew, eh = bw * 0.24, bh * 0.05, bw * 0.15, bh * 0.26
        if p < 0.15:
            # 圆睁 视线从头顶追到嘴边
            k = ease_out(p / 0.15)
            look = -eh * 0.3 + k * eh * 0.55
            scale = 1.15 + 0.1 * math.sin(p * 50)  # 好奇放大
            self._eye_oval(painter, -dx, ey + look, ew * scale, eh * scale)
            self._eye_oval(painter, dx, ey + look, ew * scale, eh * scale)
            return
        if p < 0.55:
            # 满足地眯起 弧线随咀嚼微颤
            q = (p - 0.15) / 0.4
            wob = math.sin(q * math.pi * 12 - math.pi / 2) * eh * 0.03
            self._eye_arc(painter, -dx, ey + wob, ew, eh)
            self._eye_arc(painter, dx, ey + wob, ew, eh)
            return
        if p < 0.75:
            # 咽下去那一下闭紧
            pen = QPen(_INK)
            pen.setWidthF(max(2.0, eh * 0.18))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for sx in (-1, 1):
                painter.drawLine(QPointF(sx * dx - ew * 0.5, ey), QPointF(sx * dx + ew * 0.5, ey))
            return
        q = (p - 0.75) / 0.25
        if q < 0.45:
            # 打嗝把自己惊到 瞪圆
            self._eye_oval(painter, -dx, ey - eh * 0.06, ew * 1.3, eh * 1.25)
            self._eye_oval(painter, dx, ey - eh * 0.06, ew * 1.3, eh * 1.25)
            return
        # 回味的笑眼
        self._eye_arc(painter, -dx, ey, ew, eh)
        self._eye_arc(painter, dx, ey, ew, eh)

    def _eating_progress(self) -> float | None:
        """正在吃就给进度 不在吃给None"""
        if self._react is not None and self._react[0] == "eating":
            _name, elapsed, dur = self._react
            return min(1.0, elapsed / max(dur, 0.001))
        return None

    def _draw_mouth(self, painter: QPainter, bw: float, bh: float) -> None:
        my = bh * 0.26
        eat_p = self._eating_progress()
        if eat_p is not None:
            self._draw_eating_mouth(painter, eat_p, bw, bh, my)
            return
        if self._talking:
            opening = (math.sin(self._t * 18) + 1) / 2
            mw, mh = bw * 0.1, bh * 0.03 + bh * 0.1 * opening
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_INK)
            painter.drawRoundedRect(QRectF(-mw / 2, my, mw, mh), mw * 0.4, mw * 0.4)
            return
        pen = QPen(_INK)
        pen.setWidthF(max(1.8, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mw = bw * 0.16
        box = QRectF(-mw / 2, my - bh * 0.05, mw, bh * 0.12)
        if self._expr == "happy":
            painter.drawArc(box, 200 * 16, 140 * 16)
        elif self._expr in ("sad", "confused"):
            painter.drawArc(box, 20 * 16, 140 * 16)
        elif self._expr == "surprised":
            painter.setBrush(_INK)
            painter.drawEllipse(QPointF(0.0, my + bh * 0.01), bh * 0.05, bh * 0.05)

    def _draw_eating_mouth(self, painter: QPainter, p: float, bw: float, bh: float, my: float) -> None:
        """吃东西的嘴 张大等 咀嚼开合 吞咽抿线 满足圆嘴变笑"""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_INK)
        if p < 0.15:
            k = ease_out(p / 0.15)
            mw, mh = bw * (0.08 + 0.07 * k), bh * (0.02 + 0.12 * k)
            painter.drawEllipse(QRectF(-mw / 2, my - mh * 0.2, mw, mh))
            return
        if p < 0.55:
            q = (p - 0.15) / 0.4
            opening = (math.sin(q * math.pi * 12 - math.pi / 2) + 1) / 2  # 六次开合
            mw = bw * (0.12 - 0.04 * opening)
            mh = bh * 0.02 + bh * 0.1 * opening
            painter.drawRoundedRect(QRectF(-mw / 2, my, mw, mh), mw * 0.35, mw * 0.35)
            return
        pen = QPen(_INK)
        pen.setWidthF(max(1.8, bw * 0.016))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if p < 0.75:
            q = (p - 0.55) / 0.2
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            wob = math.sin(q * math.pi) * bh * 0.015  # 咽下去那一下嘴角动一动
            painter.drawLine(QPointF(-bw * 0.05, my + bh * 0.03 + wob), QPointF(bw * 0.05, my + bh * 0.03 - wob))
            return
        q = (p - 0.75) / 0.25
        if q < 0.45:  # 打嗝小圆嘴
            painter.drawEllipse(QPointF(0.0, my + bh * 0.02), bh * 0.035, bh * 0.035)
        else:  # 回味的笑
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mw = bw * 0.16
            painter.drawArc(QRectF(-mw / 2, my - bh * 0.05, mw, bh * 0.12), 200 * 16, 140 * 16)


    def _draw_costume_worn(self, painter: QPainter, bw: float, bh: float) -> None:
        layers = props.COSTUME_LAYERS.get(self._costume)
        if layers and layers[0]:
            layers[0](painter, bw, bh, self._t, self._stage, self._stage_p)


    def _draw_costume_ambient(
        self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float
    ) -> None:
        layers = props.COSTUME_LAYERS.get(self._costume)
        if not (layers and layers[1]):
            return
        painter.save()
        painter.translate(cx, head_y)
        layers[1](painter, bw, bh, self._t, self._stage, self._stage_p)
        painter.restore()

    def _draw_question(self, painter: QPainter, cx: float, cy: float, bw: float, bh: float) -> None:
        font = QFont()
        font.setPixelSize(int(bh * 0.42))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_INK)
        painter.drawText(
            QRectF(cx + bw * 0.3, cy - bh * 0.95, bh * 0.5, bh * 0.5),
            Qt.AlignmentFlag.AlignCenter,
            "?",
        )

    def _blink_open(self) -> float:
        # 眼睛睁开度 眨眼走v形
        if not self._blinking:
            return 1.0
        return abs(self._blink_e / _BLINK_DUR - 0.5) * 2
