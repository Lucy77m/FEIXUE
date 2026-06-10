# author: bdth
# email: 2074055628@qq.com
# 桌宠行为包,导出行为注册表 API 并触发 reactions 行为注册

from desktop_pet.pet.behaviors import reactions as _reactions
from desktop_pet.pet.behaviors.registry import (
    COMMON,
    NEUTRAL,
    RARE,
    UNCOMMON,
    BehaviorSpec,
    Category,
    PoseDelta,
    evaluate,
    get,
    names,
    register,
)

__all__ = [
    "COMMON",
    "UNCOMMON",
    "RARE",
    "NEUTRAL",
    "BehaviorSpec",
    "Category",
    "PoseDelta",
    "evaluate",
    "get",
    "names",
    "register",
]
