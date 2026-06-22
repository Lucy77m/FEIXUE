# 思考姿态mixin 沉思换pose 摸下巴敲桌子那套小动作

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen

from desktop_pet.pet.behaviors.easing import ease_out
from desktop_pet.pet.blob_defs import (
    _OUTLINE,
    _SKIN,
    _THINK_CUE_TTL,
    _THINK_DWELL,
    _THINK_DWELL_SCALE_CALM,
    _THINK_DWELL_SCALE_HOT,
    _THINK_HAND_R,
    _THINK_HOME,
    _THINK_LEAN,
    _THINK_MIN_DWELL,
    _THINK_POSE_WEIGHTS,
    _THINK_SCRATCH_DEG,
    _THINK_SCRATCH_HZ,
    _THINK_SCRATCH_TILT,
    _THINK_SINK,
    _THINK_SQUASH,
    _THINK_SWAY_DEG,
    _THINK_SWAY_HZ,
    _THINK_TAP_HZ,
    _THINK_TEMPLE_TILT,
    _THINK_TILT_DEG,
    _THINK_XFADE_DUR,
    _lerp,
    _weighted_pick,
)


class ThinkMixin:
    """思考时的姿态轮换和手势"""

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
