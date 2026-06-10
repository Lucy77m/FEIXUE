# author: bdth
# email: 2074055628@qq.com
# 桌宠反应动作库 定义姿态曲线并注册为 REACTION 行为

from __future__ import annotations

import math

from desktop_pet.pet.behaviors.easing import ease_in, ease_out
from desktop_pet.pet.behaviors.registry import (
    COMMON,
    NEUTRAL,
    UNCOMMON,
    BehaviorSpec,
    Category,
    PoseDelta,
    register,
)


def _jump_spin(p: float, bw: float, bh: float) -> PoseDelta:
    """蓄力下蹲再起跳转一周"""
    if p < 0.2:
        k = ease_in(p / 0.2)
        return PoseDelta(0.0, bh * 0.16 * k, 0.0, 1 + 0.14 * k, 1 - 0.18 * k)
    q = (p - 0.2) / 0.8
    oy = -math.sin(q * math.pi) * bh * 0.8
    rot = 360 * ease_out(q)
    up = max(math.cos(q * math.pi), 0.0)  # 只取上升段 落下不拉伸
    sxm, sym = 1 - 0.16 * up, 1 + 0.24 * up
    if q > 0.8:
        # 落地缓冲压扁一下
        lk = (q - 0.8) / 0.2
        sxm, sym = 1 + 0.2 * lk, 1 - 0.24 * lk
    return PoseDelta(0.0, oy, rot, sxm, sym)


def _bounce(p: float, bw: float, bh: float) -> PoseDelta:
    """小一号的蹲跳 不转弹得矮"""
    if p < 0.25:
        k = ease_in(p / 0.25)
        return PoseDelta(0.0, bh * 0.12 * k, 0.0, 1 + 0.1 * k, 1 - 0.12 * k)
    q = (p - 0.25) / 0.75
    oy = -math.sin(q * math.pi) * bh * 0.5
    stretch = max(math.cos(q * math.pi), 0.0)  # 上升段拉伸 下落不拉
    return PoseDelta(0.0, oy, 0.0, 1 - 0.1 * stretch, 1 + 0.16 * stretch)


def _nod(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(0.0, math.sin(p * math.pi * 2) * bh * 0.16)


def _shake(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(rot=math.sin(p * math.pi * 6) * 14)


def _wobble(p: float, bw: float, bh: float) -> PoseDelta:
    # 晃动逐渐收住
    return PoseDelta(rot=math.sin(p * math.pi * 3) * 13 * (1 - p))


def _pop(p: float, bw: float, bh: float) -> PoseDelta:
    a = 1 + 0.3 * math.sin(p * math.pi)
    return PoseDelta(sx=a, sy=a)


def _flip(p: float, bw: float, bh: float) -> PoseDelta:
    """后空翻 两头各压扁一下"""
    oy = -math.sin(p * math.pi) * bh * 0.8
    rot = -360 * ease_out(p)
    sxm = sym = 1.0
    # 只两头加 squash 中段保持原形
    if p < 0.15:
        k = ease_in(p / 0.15)
        sxm, sym = 1 + 0.16 * k, 1 - 0.2 * k
    elif p > 0.85:
        k = (p - 0.85) / 0.15
        sxm, sym = 1 + 0.18 * k, 1 - 0.22 * k
    return PoseDelta(0.0, oy, rot, sxm, sym)


def _dance(p: float, bw: float, bh: float) -> PoseDelta:
    """左右摇摆配上下颠"""
    sway = math.sin(p * math.pi * 8)
    bounce = abs(math.sin(p * math.pi * 8))
    return PoseDelta(sway * bw * 0.26, -bounce * bh * 0.16, sway * 16,
                     1 - 0.06 * bounce, 1 + 0.08 * bounce)


def _peek(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(s * bw * 0.18, 0.0, s * 13)


def _stretch(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, -s * bh * 0.08, 0.0, 1 - 0.12 * s, 1 + 0.26 * s)


def _spin(p: float, bw: float, bh: float) -> PoseDelta:
    # 转一圈半 先快后缓
    return PoseDelta(0.0, -math.sin(p * math.pi) * bh * 0.06, 540 * ease_out(p))


def _hop2(p: float, bw: float, bh: float) -> PoseDelta:
    # 一个周期跳两下
    a = abs(math.sin(p * math.pi * 2))
    return PoseDelta(0.0, -a * bh * 0.32, 0.0, 1 - 0.1 * a, 1 + 0.14 * a)


def _roll(p: float, bw: float, bh: float) -> PoseDelta:
    # 横移出去再回来 一路转两圈
    return PoseDelta(math.sin(p * math.pi) * bw * 0.3, 0.0, 720 * p)


def _droop(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, s * bh * 0.1, 0.0, 1 + 0.08 * s, 1 - 0.18 * s)


def _sigh(p: float, bw: float, bh: float) -> PoseDelta:
    """叹气 先吸气再缓缓泄下去"""
    if p < 0.35:
        k = ease_out(p / 0.35)
        return PoseDelta(0.0, -k * bh * 0.07, 0.0, 1.0, 1 + 0.06 * k)
    # 接吸气末态往下泄
    k = (p - 0.35) / 0.65
    return PoseDelta(0.0, -bh * 0.07 + k * bh * 0.17, 0.0, 1.0, 1.06 - 0.22 * k)


def _ponder(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(0.0, math.sin(p * math.pi * 4) * bh * 0.02, math.sin(p * math.pi) * 13)


def _gasp(p: float, bw: float, bh: float) -> PoseDelta:
    # 倒吸一口气 猛窜到顶再松回
    k = ease_out(p / 0.25) if p < 0.25 else 1 - (p - 0.25) / 0.75
    return PoseDelta(0.0, -bh * 0.12 * k, 0.0, 1 - 0.1 * k, 1 + 0.18 * k)


def _double_take(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(math.sin(p * math.pi * 2) * bw * 0.2, 0.0, math.sin(p * math.pi * 2) * 8)


def _happy_wiggle(p: float, bw: float, bh: float) -> PoseDelta:
    wig = math.sin(p * math.pi * 8)
    return PoseDelta(wig * bw * 0.09, -abs(wig) * bh * 0.03, wig * 5)


def _hold_still(p: float, bw: float, bh: float) -> PoseDelta:
    # 啥也不做的占位反应
    return NEUTRAL


def _tip_over(p: float, bw: float, bh: float) -> PoseDelta:
    """歪倒又扶正 叠高频抖"""
    arc = math.sin(p * math.pi)
    return PoseDelta(arc * bw * 0.06, 0.0, arc * 22 + math.sin(p * math.pi * 7) * 5 * (1 - p))


def _boing(p: float, bw: float, bh: float) -> PoseDelta:
    # 弹簧余震 越抖越小
    osc = math.sin(p * math.pi * 5) * (1 - p)
    return PoseDelta(0.0, -osc * bh * 0.1, 0.0, 1 - 0.16 * osc, 1 + 0.16 * osc)


def _recoil(p: float, bw: float, bh: float) -> PoseDelta:
    # 往后一缩再慢慢凑回来
    k = ease_out(p / 0.3) if p < 0.3 else 1 - (p - 0.3) / 0.7
    return PoseDelta(-k * bw * 0.16, 0.0, -k * 10, 1 + 0.06 * k, 1 - 0.06 * k)


def _deflate(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, s * bh * 0.12, 0.0, 1 + 0.16 * s, 1 - 0.22 * s)


def _headbang(p: float, bw: float, bh: float) -> PoseDelta:
    beat = abs(math.sin(p * math.pi * 4))
    return PoseDelta(0.0, beat * bh * 0.14, 0.0, 1 + 0.04 * beat, 1 - 0.06 * beat)


def _cheer(p: float, bw: float, bh: float) -> PoseDelta:
    """欢呼 大跳叠高频小摆"""
    jump = math.sin(p * math.pi)
    wig = math.sin(p * math.pi * 8) * (1 - abs(2 * p - 1))
    return PoseDelta(wig * bw * 0.06, -jump * bh * 0.5, wig * 6, 1 - 0.1 * jump, 1 + 0.12 * jump)


def _perk_up(p: float, bw: float, bh: float) -> PoseDelta:
    """精神一振 快速挺起保持再落回"""
    rise = ease_out(p / 0.25) if p < 0.25 else 1.0
    settle = 1.0 if p < 0.7 else 1 - (p - 0.7) / 0.3
    a = rise * settle
    return PoseDelta(0.0, -a * bh * 0.08, 0.0, 1 - 0.04 * a, 1 + 0.08 * a)


def _puff_up(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, -s * bh * 0.03, 0.0, 1 + 0.12 * s, 1 + 0.1 * s)


def _yawn(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, -s * bh * 0.06, -s * 4, 1 - 0.1 * s, 1 + 0.2 * s)


def _celebrate(p: float, bw: float, bh: float) -> PoseDelta:
    # 加强版 cheer 连蹦带扭跳五下
    hop = abs(math.sin(p * math.pi * 5))
    wig = math.sin(p * math.pi * 10)
    return PoseDelta(wig * bw * 0.06, -hop * bh * 0.40, wig * 8, 1 - 0.12 * hop, 1 + 0.18 * hop)


def _slump(p: float, bw: float, bh: float) -> PoseDelta:
    """瘫下去 沉到底配轻微晃"""
    sink = ease_out(min(p / 0.4, 1.0))
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, sink * bh * 0.12, math.sin(p * math.pi * 2) * 3, 1 + 0.1 * s, 1 - 0.16 * s)


# 一行一个反应 名字 时长 曲线 valence arousal weight rarity
_REACTIONS = (
    ("hold_still", 1.2, _hold_still, 0.0, 0.2, 1.4, COMMON),
    ("nod", 1.1, _nod, 0.2, 0.4, 1.0, COMMON),
    ("wobble", 1.1, _wobble, -0.1, 0.4, 1.0, COMMON),
    ("peek", 1.3, _peek, 0.0, 0.45, 1.0, COMMON),
    ("stretch", 1.7, _stretch, 0.1, 0.3, 1.0, COMMON),
    ("ponder", 1.9, _ponder, 0.0, 0.35, 1.0, COMMON),
    ("bounce", 1.0, _bounce, 0.6, 0.6, 1.0, COMMON),
    ("hop2", 1.4, _hop2, 0.6, 0.65, 1.0, COMMON),
    ("happy_wiggle", 1.5, _happy_wiggle, 0.7, 0.6, 1.0, COMMON),
    ("pop", 0.8, _pop, 0.4, 0.7, 1.0, COMMON),
    ("shake", 1.2, _shake, -0.2, 0.5, 1.0, COMMON),
    ("double_take", 1.4, _double_take, -0.1, 0.7, 1.0, COMMON),
    ("gasp", 1.2, _gasp, 0.1, 0.85, 1.0, COMMON),
    ("droop", 2.0, _droop, -0.6, 0.2, 1.0, COMMON),
    ("sigh", 2.2, _sigh, -0.5, 0.25, 1.0, COMMON),
    ("jump_spin", 2.0, _jump_spin, 0.7, 0.85, 0.8, UNCOMMON),
    ("flip", 1.9, _flip, 0.8, 0.9, 0.6, UNCOMMON),
    ("dance", 3.8, _dance, 0.8, 0.7, 0.7, UNCOMMON),
    ("spin", 2.1, _spin, 0.5, 0.8, 0.7, UNCOMMON),
    ("roll", 2.2, _roll, 0.6, 0.7, 0.6, UNCOMMON),
    ("tip_over", 2.0, _tip_over, -0.1, 0.6, 0.8, UNCOMMON),
    ("boing", 1.5, _boing, 0.5, 0.65, 0.9, COMMON),
    ("recoil", 1.1, _recoil, -0.25, 0.7, 0.9, COMMON),
    ("deflate", 2.1, _deflate, -0.5, 0.25, 1.0, COMMON),
    ("headbang", 2.4, _headbang, 0.65, 0.85, 0.7, UNCOMMON),
    ("cheer", 2.4, _cheer, 0.9, 0.85, 0.8, UNCOMMON),
    ("perk_up", 1.2, _perk_up, 0.3, 0.6, 1.0, COMMON),
    ("puff_up", 1.8, _puff_up, 0.55, 0.45, 0.8, UNCOMMON),
    ("yawn", 2.2, _yawn, -0.05, 0.15, 0.3, UNCOMMON),
    ("celebrate", 3.6, _celebrate, 0.9, 0.8, 0.5, UNCOMMON),
    ("slump", 2.6, _slump, -0.7, 0.2, 0.5, UNCOMMON),
)

# 亲密向动作 好感度够高才放出来
_INTIMATE = frozenset(
    {"happy_wiggle", "bounce", "hop2", "dance", "cheer", "celebrate", "peek", "puff_up", "boing"}
)

# 表驱动统一注册
for _name, _dur, _curve, _val, _aro, _wt, _rar in _REACTIONS:
    register(
        BehaviorSpec(
            name=_name,
            category=Category.REACTION,
            duration=_dur,
            curve=_curve,
            valence=_val,
            arousal=_aro,
            weight=_wt,
            rarity=_rar,
            intimacy=1.0 if _name in _INTIMATE else 0.0,
        )
    )
