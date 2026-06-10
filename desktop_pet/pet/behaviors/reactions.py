# author: bdth
# email: 2074055628@qq.com
# 桌宠反应动作库：定义各种姿态曲线函数并注册为 REACTION 行为

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
    """蓄力下蹲(前 20%)→ 起跳腾空一周。oy 正方向朝下，所以 -sin 才是往上的抛物线弧。"""
    if p < 0.2:
        k = ease_in(p / 0.2)
        return PoseDelta(0.0, bh * 0.16 * k, 0.0, 1 + 0.14 * k, 1 - 0.18 * k)
    q = (p - 0.2) / 0.8
    oy = -math.sin(q * math.pi) * bh * 0.8
    rot = 360 * ease_out(q)
    up = max(math.cos(q * math.pi), 0.0)  # 只取上升段(cos>0)，落下时不再拉伸
    sxm, sym = 1 - 0.16 * up, 1 + 0.24 * up
    if q > 0.8:
        # 最后 0.2 落地缓冲：反过来压扁一下，免得直挺挺地杵下来
        lk = (q - 0.8) / 0.2
        sxm, sym = 1 + 0.2 * lk, 1 - 0.24 * lk
    return PoseDelta(0.0, oy, rot, sxm, sym)


def _bounce(p: float, bw: float, bh: float) -> PoseDelta:
    """蹲—跳的小一号版：jump_spin 去掉旋转，弹得也矮(0.5bh)，日常用得最多。"""
    if p < 0.25:
        k = ease_in(p / 0.25)
        return PoseDelta(0.0, bh * 0.12 * k, 0.0, 1 + 0.1 * k, 1 - 0.12 * k)
    q = (p - 0.25) / 0.75
    oy = -math.sin(q * math.pi) * bh * 0.5
    stretch = max(math.cos(q * math.pi), 0.0)  # 上升段拉伸、下落不拉，免得落地像橡皮
    return PoseDelta(0.0, oy, 0.0, 1 - 0.1 * stretch, 1 + 0.16 * stretch)


def _nod(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(0.0, math.sin(p * math.pi * 2) * bh * 0.16)


def _shake(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(rot=math.sin(p * math.pi * 6) * 14)


def _wobble(p: float, bw: float, bh: float) -> PoseDelta:
    # (1-p) 让晃动逐渐收住，最后停在 0 度而不是半途被截断
    return PoseDelta(rot=math.sin(p * math.pi * 3) * 13 * (1 - p))


def _pop(p: float, bw: float, bh: float) -> PoseDelta:
    a = 1 + 0.3 * math.sin(p * math.pi)
    return PoseDelta(sx=a, sy=a)


def _flip(p: float, bw: float, bh: float) -> PoseDelta:
    """后空翻：rot 取负往后转一圈，起跳/落地两头各压一下扁。"""
    oy = -math.sin(p * math.pi) * bh * 0.8
    rot = -360 * ease_out(p)
    sxm = sym = 1.0
    # 只两头加 squash，中段腾空保持原形不变形
    if p < 0.15:
        k = ease_in(p / 0.15)
        sxm, sym = 1 + 0.16 * k, 1 - 0.2 * k
    elif p > 0.85:
        k = (p - 0.85) / 0.15
        sxm, sym = 1 + 0.18 * k, 1 - 0.22 * k
    return PoseDelta(0.0, oy, rot, sxm, sym)


def _dance(p: float, bw: float, bh: float) -> PoseDelta:
    """左右摇摆配上下颠。bounce 取绝对值 —— 只往上跳不往下沉。"""
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
    # 转一圈半(540°)而非整圈，结束停在侧脸更俏皮；ease_out 让转速先快后缓
    return PoseDelta(0.0, -math.sin(p * math.pi) * bh * 0.06, 540 * ease_out(p))


def _hop2(p: float, bw: float, bh: float) -> PoseDelta:
    # *2 + 绝对值 = 一个周期里跳两下，中间落地点回到原位
    a = abs(math.sin(p * math.pi * 2))
    return PoseDelta(0.0, -a * bh * 0.32, 0.0, 1 - 0.1 * a, 1 + 0.14 * a)


def _roll(p: float, bw: float, bh: float) -> PoseDelta:
    # 横移走半个正弦(出去再回来)，但 rot 用线性 720*p 一路转两圈 —— 滚出去滚回来的错觉
    return PoseDelta(math.sin(p * math.pi) * bw * 0.3, 0.0, 720 * p)


def _droop(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, s * bh * 0.1, 0.0, 1 + 0.08 * s, 1 - 0.18 * s)


def _sigh(p: float, bw: float, bh: float) -> PoseDelta:
    """叹气：前 0.35 吸气(微微抬高拔长)，后段缓缓泄气往下沉、纵向被压回去。"""
    if p < 0.35:
        k = ease_out(p / 0.35)
        return PoseDelta(0.0, -k * bh * 0.07, 0.0, 1.0, 1 + 0.06 * k)
    # 接吸气末态(-0.07bh、1.06)往下泄，终点落到比原位还低一点
    k = (p - 0.35) / 0.65
    return PoseDelta(0.0, -bh * 0.07 + k * bh * 0.17, 0.0, 1.0, 1.06 - 0.22 * k)


def _ponder(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(0.0, math.sin(p * math.pi * 4) * bh * 0.02, math.sin(p * math.pi) * 13)


def _gasp(p: float, bw: float, bh: float) -> PoseDelta:
    # 倒吸一口气：0.25 处猛地窜到顶(ease_out)，之后线性松回 —— 急起缓落才像"吓一跳"
    k = ease_out(p / 0.25) if p < 0.25 else 1 - (p - 0.25) / 0.75
    return PoseDelta(0.0, -bh * 0.12 * k, 0.0, 1 - 0.1 * k, 1 + 0.18 * k)


def _double_take(p: float, bw: float, bh: float) -> PoseDelta:
    return PoseDelta(math.sin(p * math.pi * 2) * bw * 0.2, 0.0, math.sin(p * math.pi * 2) * 8)


def _happy_wiggle(p: float, bw: float, bh: float) -> PoseDelta:
    wig = math.sin(p * math.pi * 8)
    return PoseDelta(wig * bw * 0.09, -abs(wig) * bh * 0.03, wig * 5)


def _hold_still(p: float, bw: float, bh: float) -> PoseDelta:
    # 啥也不做的占位反应：权重给得高，让桌宠多数时候安静待着、别一直蹦
    return NEUTRAL


def _tip_over(p: float, bw: float, bh: float) -> PoseDelta:
    """歪倒又扶正：主弧 arc 倾过去再回来，叠一层 *7 的高频抖且 (1-p) 衰减，像没站稳在晃。"""
    arc = math.sin(p * math.pi)
    return PoseDelta(arc * bw * 0.06, 0.0, arc * 22 + math.sin(p * math.pi * 7) * 5 * (1 - p))


def _boing(p: float, bw: float, bh: float) -> PoseDelta:
    # 弹簧余震：5 倍频快抖 + (1-p) 衰减，越抖越小最后归位
    osc = math.sin(p * math.pi * 5) * (1 - p)
    return PoseDelta(0.0, -osc * bh * 0.1, 0.0, 1 - 0.16 * osc, 1 + 0.16 * osc)


def _recoil(p: float, bw: float, bh: float) -> PoseDelta:
    # 往后一缩(ox 取负)再慢慢凑回来：0.3 处缩到底，急退缓回是"被吓退"的感觉
    k = ease_out(p / 0.3) if p < 0.3 else 1 - (p - 0.3) / 0.7
    return PoseDelta(-k * bw * 0.16, 0.0, -k * 10, 1 + 0.06 * k, 1 - 0.06 * k)


def _deflate(p: float, bw: float, bh: float) -> PoseDelta:
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, s * bh * 0.12, 0.0, 1 + 0.16 * s, 1 - 0.22 * s)


def _headbang(p: float, bw: float, bh: float) -> PoseDelta:
    beat = abs(math.sin(p * math.pi * 4))
    return PoseDelta(0.0, beat * bh * 0.14, 0.0, 1 + 0.04 * beat, 1 - 0.06 * beat)


def _cheer(p: float, bw: float, bh: float) -> PoseDelta:
    """欢呼：大跳托底叠高频小摆，摆动用三角窗包络 —— 腾空最高点摆得最浓、起落两头收住。"""
    jump = math.sin(p * math.pi)
    wig = math.sin(p * math.pi * 8) * (1 - abs(2 * p - 1))
    return PoseDelta(wig * bw * 0.06, -jump * bh * 0.5, wig * 6, 1 - 0.1 * jump, 1 + 0.12 * jump)


def _perk_up(p: float, bw: float, bh: float) -> PoseDelta:
    """精神一振：0~0.25 快速挺起(rise)，中段保持，0.7 后再缓缓落回(settle)，两段相乘成梯形包络。"""
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
    # 连蹦带扭的加强版 cheer：hop 一程跳 5 下(绝对值只往上)，wig 用 10 倍频跟着跳频对齐
    hop = abs(math.sin(p * math.pi * 5))
    wig = math.sin(p * math.pi * 10)
    return PoseDelta(wig * bw * 0.06, -hop * bh * 0.40, wig * 8, 1 - 0.12 * hop, 1 + 0.18 * hop)


def _slump(p: float, bw: float, bh: float) -> PoseDelta:
    """瘫下去：sink 在前 0.4 沉到底后一直撑住不回弹(min 截到 1.0)，配点轻微左右晃显得没精神。"""
    sink = ease_out(min(p / 0.4, 1.0))
    s = math.sin(p * math.pi)
    return PoseDelta(0.0, sink * bh * 0.12, math.sin(p * math.pi * 2) * 3, 1 + 0.1 * s, 1 - 0.16 * s)


# 一行一个反应：(名字, 时长秒, 曲线, valence效价, arousal唤醒, weight权重, rarity稀有度)
# valence 负=消极正=积极、arousal 高=激烈，情绪系统按这俩维度挑动作；weight 越大越常抽到
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

# 亲密向动作：只在好感度够高时才放出来，平时不会随机蹦这些
_INTIMATE = frozenset(
    {"happy_wiggle", "bounce", "hop2", "dance", "cheer", "celebrate", "peek", "puff_up", "boing"}
)

# 表驱动统一注册：在 _INTIMATE 里的 intimacy 给 1.0，其余 0.0，省得一条条手写 BehaviorSpec
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
