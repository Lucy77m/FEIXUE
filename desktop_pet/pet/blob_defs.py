# author: bdth
# email: 2074055628@qq.com
# 角色状态机和绘制共用的常量小工具 拆出来给核心与各mixin一起引

from __future__ import annotations

import random

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from desktop_pet.pet import palette


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
