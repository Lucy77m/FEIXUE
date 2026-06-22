# 桌宠行为选择器 按情绪亲密度稀有度和近期去重加权随机挑行为

from __future__ import annotations

import math
import random
from collections import deque

from desktop_pet.pet.behaviors import registry
from desktop_pet.pet.behaviors.registry import Category

_VA_SIGMA = 0.5
_RECENT_N = 5
_RECENCY_PENALTY = 0.15
_INTIMACY_DAMP = 0.8
_RARITY_WEIGHT = (1.0, 0.45, 0.15)


class BehaviorSelector:
    """情绪驱动的行为加权随机器"""

    def __init__(self) -> None:
        self._valence = 0.0
        self._arousal = 0.5
        self._rapport = 0.15
        self._recent: deque[str] = deque(maxlen=_RECENT_N)

    def set_emotion(self, valence: float, arousal: float, rapport: float) -> None:
        self._valence, self._arousal, self._rapport = valence, arousal, rapport

    def select(
        self,
        category: Category,
        candidates: tuple[str, ...] | None = None,
        mood: tuple[float, float] | None = None,
    ) -> str | None:
        """挑一个行为名 没候选返回None"""
        names = candidates if candidates is not None else registry.names(category)
        valence, arousal = mood if mood is not None else (self._valence, self._arousal)
        scored = [
            (name, self._score(spec, name, valence, arousal))
            for name in names
            if (spec := registry.get(name)) is not None
        ]
        if not scored:
            return None
        name = self._weighted_pick(scored)
        self._recent.append(name)
        return name

    def _score(self, spec: registry.BehaviorSpec, name: str, valence: float, arousal: float) -> float:
        """算单个行为的权重 四个乘子相乘"""
        dv = valence - spec.valence
        da = arousal - spec.arousal
        affinity = math.exp(-(dv * dv + da * da) / (2 * _VA_SIGMA * _VA_SIGMA))  # 离当前情绪越远高斯衰减
        rarity = _RARITY_WEIGHT[min(spec.rarity, len(_RARITY_WEIGHT) - 1)]  # rarity档位下标 超出钳到最后一档
        recency = _RECENCY_PENALTY if name in self._recent else 1.0  # 最近出过的降权
        intimacy = 1.0 - spec.intimacy * _INTIMACY_DAMP * (1.0 - self._rapport)  # 亲密行为靠rapport解锁
        return spec.weight * rarity * affinity * recency * intimacy

    @staticmethod
    def _weighted_pick(scored: list[tuple[str, float]]) -> str:
        """按分数轮盘赌选名 全0退化成均匀随机"""
        total = sum(score for _, score in scored)
        if total <= 0.0:
            return random.choice([name for name, _ in scored])
        r = random.uniform(0.0, total)
        upto = 0.0
        for name, score in scored:
            upto += score
            if r <= upto:
                return name
        return scored[-1][0]  # 浮点误差没命中落最后一个兜底


selector = BehaviorSelector()
