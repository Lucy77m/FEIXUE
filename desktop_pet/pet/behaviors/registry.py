# author: bdth
# email: 2074055628@qq.com
# 桌宠行为注册表：定义行为规格与姿态偏移，按分类注册/查询/求值

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


class PoseDelta(NamedTuple):
    """单帧姿态偏移量 —— 叠加到静止姿态上，不是绝对坐标。"""

    ox: float = 0.0
    oy: float = 0.0  # 像素位移；屏幕坐标系 y 向下，跳起来要给负值
    rot: float = 0.0  # deg，绕锚点
    sx: float = 1.0
    sy: float = 1.0  # 缩放是乘法 —— 默认 1.0 才是不变，0 会把宠物压没


NEUTRAL = PoseDelta()

# 行为曲线：入参 (p, bw, bh) —— p 是 0→1 的归一化进度，bw/bh 是宠物当前尺寸，
# 偏移随尺寸缩放才能在不同 DPI/缩放下看着一致。
CurveFn = Callable[[float, float, float], PoseDelta]


class Category(str, Enum):
    REACTION = "reaction"


COMMON = 0
UNCOMMON = 1
RARE = 2


@dataclass(frozen=True)
class BehaviorSpec:
    """一条行为的静态规格 —— frozen 保证注册后没人能就地改坏共享表里的同一份。"""

    name: str
    category: Category
    duration: float  # 秒；驱动 p 从 0 走到 1
    # 默认全程 NEUTRAL，占位用——光有时长不动也算合法行为
    curve: CurveFn = field(default=lambda p, bw, bh: NEUTRAL)
    valence: float = 0.0
    arousal: float = 0.5
    weight: float = 1.0
    rarity: int = COMMON
    intimacy: float = 0.0  # 亲密度没到这个门槛的行为不解锁


_REGISTRY: dict[str, BehaviorSpec] = {}
_BY_CATEGORY: dict[Category, list[str]] = {}


def register(spec: BehaviorSpec) -> BehaviorSpec:
    """回原 spec，方便 X = register(...) 一行写完。"""
    # 名字是查询的键，悄悄覆盖会让旧行为莫名其妙消失，所以重名直接抛
    if spec.name in _REGISTRY:
        raise ValueError(f"duplicate behavior name: {spec.name!r}")
    _REGISTRY[spec.name] = spec
    _BY_CATEGORY.setdefault(spec.category, []).append(spec.name)
    return spec


def get(name: str) -> BehaviorSpec | None:
    return _REGISTRY.get(name)


def names(category: Category) -> tuple[str, ...]:
    return tuple(_BY_CATEGORY.get(category, ()))


def evaluate(name: str, p: float, bw: float, bh: float) -> PoseDelta:
    """按名字算出当前帧的姿态偏移；名字不存在就给 NEUTRAL，渲染端不用做容错。"""
    spec = _REGISTRY.get(name)
    return spec.curve(p, bw, bh) if spec is not None else NEUTRAL
