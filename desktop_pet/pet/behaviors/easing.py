# author: bdth
# email: 2074055628@qq.com
# 缓动函数集合，把 0~1 的线性进度映射为带加减速的动画曲线

from __future__ import annotations


def ease_in(p: float) -> float:
    """慢起步：二次方，起手轻、越走越快。用在「冒头/淡入」这类不想一上来就猛冲的动作"""
    return p * p


def ease_out(p: float) -> float:
    """急刹车：三次方收尾，临近终点几乎贴住，落点不飘——移动到位/对齐用它"""
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    """带回弹的 ease_out：先冲过头一点再缩回 1，那种「Q 弹」手感（弹窗、表情切换）"""
    c = 1.70158  # 标准 back 系数，约 10% 过冲；调大过冲更狠，太大就甩过头了
    q = p - 1
    return 1 + (c + 1) * q ** 3 + c * q ** 2
