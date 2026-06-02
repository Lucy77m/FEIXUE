# author: bdth
# email: 2074055628@qq.com
# 桌宠行为选择器：按情绪(效价/唤醒)、亲密度、稀有度和近期去重，加权随机挑选行为动作

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
        dv = valence - spec.valence
        da = arousal - spec.arousal
        affinity = math.exp(-(dv * dv + da * da) / (2 * _VA_SIGMA * _VA_SIGMA))
        rarity = _RARITY_WEIGHT[min(spec.rarity, len(_RARITY_WEIGHT) - 1)]
        recency = _RECENCY_PENALTY if name in self._recent else 1.0
        intimacy = 1.0 - spec.intimacy * _INTIMACY_DAMP * (1.0 - self._rapport)
        return spec.weight * rarity * affinity * recency * intimacy

    @staticmethod
    def _weighted_pick(scored: list[tuple[str, float]]) -> str:
        total = sum(score for _, score in scored)
        if total <= 0.0:
            return random.choice([name for name, _ in scored])
        r = random.uniform(0.0, total)
        upto = 0.0
        for name, score in scored:
            upto += score
            if r <= upto:
                return name
        return scored[-1][0]


selector = BehaviorSelector()
