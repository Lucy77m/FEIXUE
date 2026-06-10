# author: bdth
# email: 2074055628@qq.com
# 桌宠行为注册表 定义行为规格和姿态偏移 按分类注册查询求值

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


class PoseDelta(NamedTuple):
    """单帧姿态偏移量 叠加到静止姿态上"""

    ox: float = 0.0
    oy: float = 0.0  # 像素位移 y 向下
    rot: float = 0.0  # deg 绕锚点
    sx: float = 1.0
    sy: float = 1.0  # 缩放是乘法


NEUTRAL = PoseDelta()

# 行为曲线 p 是进度 bw bh 是宠物尺寸
CurveFn = Callable[[float, float, float], PoseDelta]


class Category(str, Enum):
    REACTION = "reaction"


COMMON = 0
UNCOMMON = 1
RARE = 2


@dataclass(frozen=True)
class BehaviorSpec:
    """一条行为的静态规格"""

    name: str
    category: Category
    duration: float  # 秒 驱动 p 从 0 走到 1
    # 默认全程 NEUTRAL
    curve: CurveFn = field(default=lambda p, bw, bh: NEUTRAL)
    valence: float = 0.0
    arousal: float = 0.5
    weight: float = 1.0
    rarity: int = COMMON
    intimacy: float = 0.0  # 亲密度门槛 没到不解锁


_REGISTRY: dict[str, BehaviorSpec] = {}
_BY_CATEGORY: dict[Category, list[str]] = {}


def register(spec: BehaviorSpec) -> BehaviorSpec:
    """注册行为 回原 spec"""
    # 重名直接抛
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
    """按名字算当前帧姿态偏移 没有就给 NEUTRAL"""
    spec = _REGISTRY.get(name)
    return spec.curve(p, bw, bh) if spec is not None else NEUTRAL
