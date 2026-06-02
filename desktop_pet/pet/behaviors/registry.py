# author: bdth
# email: 2074055628@qq.com
# 桌宠行为注册表：定义行为规格与姿态偏移，按分类注册/查询/求值

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


class PoseDelta(NamedTuple):
    ox: float = 0.0
    oy: float = 0.0
    rot: float = 0.0
    sx: float = 1.0
    sy: float = 1.0


NEUTRAL = PoseDelta()

CurveFn = Callable[[float, float, float], PoseDelta]


class Category(str, Enum):
    REACTION = "reaction"


COMMON = 0
UNCOMMON = 1
RARE = 2


@dataclass(frozen=True)
class BehaviorSpec:
    name: str
    category: Category
    duration: float
    curve: CurveFn = field(default=lambda p, bw, bh: NEUTRAL)
    valence: float = 0.0
    arousal: float = 0.5
    weight: float = 1.0
    rarity: int = COMMON
    intimacy: float = 0.0


_REGISTRY: dict[str, BehaviorSpec] = {}
_BY_CATEGORY: dict[Category, list[str]] = {}


def register(spec: BehaviorSpec) -> BehaviorSpec:
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
    spec = _REGISTRY.get(name)
    return spec.curve(p, bw, bh) if spec is not None else NEUTRAL
