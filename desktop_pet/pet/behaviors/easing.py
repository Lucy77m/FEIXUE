# 缓动函数集合 线性进度映射成动画曲线

from __future__ import annotations


def ease_in(p: float) -> float:
    """慢起步"""
    return p * p


def ease_out(p: float) -> float:
    """急刹车收尾"""
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    """带回弹的 ease_out 冲过头再缩回"""
    c = 1.70158  # 标准 back 系数
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2
