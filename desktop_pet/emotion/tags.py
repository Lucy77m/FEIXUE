# author: bdth
# email: 2074055628@qq.com
# 情绪标签表和派生映射

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionTag:
    """一条情绪标签和播放参数"""
    name: str
    expression: str
    valence: float
    arousal: float
    intensity: float
    costume: str | None = None


# name是模型标签 expression是表情资源 不一一对应
TAGS: tuple[EmotionTag, ...] = (
    EmotionTag("happy",     "happy",      0.7,  0.6,  1.1),
    EmotionTag("excited",   "happy",      0.8,  0.85, 1.25, "party"),
    EmotionTag("sad",       "sad",       -0.6,  0.25, 0.7,  "raincloud"),
    EmotionTag("confused",  "confused",  -0.15, 0.5,  0.9,  "sweat"),
    EmotionTag("surprised", "surprised",  0.1,  0.85, 1.15),
    EmotionTag("thinking",  "thinking",   0.0,  0.35, 0.85),
    EmotionTag("neutral",   "neutral",    0.2,  0.4,  0.95),
)

EXPRESSIONS: frozenset[str] = frozenset(t.expression for t in TAGS)
TAG_EXPRESSION: dict[str, str] = {t.name: t.expression for t in TAGS}
TAG_VA: dict[str, tuple[float, float]] = {t.name: (t.valence, t.arousal) for t in TAGS}
TAG_INTENSITY: dict[str, float] = {t.name: t.intensity for t in TAGS}
TAG_COSTUME: dict[str, str] = {t.name: t.costume for t in TAGS if t.costume}  # 没换装的不进表
PROMPT_TAGS: str = " ".join(f"[{t.name}]" for t in TAGS)  # 拼给system prompt的标签串
