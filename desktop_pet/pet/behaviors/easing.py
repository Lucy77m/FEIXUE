# author: bdth
# email: 2074055628@qq.com
# 缓动函数集合，把 0~1 的线性进度映射为带加减速的动画曲线

from __future__ import annotations


def ease_in(p: float) -> float:
    return p * p


def ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    c = 1.70158
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2
