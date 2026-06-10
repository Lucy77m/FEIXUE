# author: bdth
# email: 2074055628@qq.com
# 定义桌宠情绪标签表及其表情、效价/唤醒度、强度、换装等派生映射

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionTag:
    """一条标签连带它的播放参数，下面那张表是只读的，frozen 顺手锁死别让谁手滑改了。"""
    name: str
    expression: str
    valence: float
    arousal: float
    intensity: float
    costume: str | None = None


# name 是模型吐的标签，expression 是实际要播的表情资源 —— 两者不是一一对应：
# excited 复用 happy 那套表情，靠更高的 arousal/intensity + party 换装拉开差异，省一套美术。
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
TAG_COSTUME: dict[str, str] = {t.name: t.costume for t in TAGS if t.costume}  # 没换装的不进表 —— 查不到就别换，省得清空
PROMPT_TAGS: str = " ".join(f"[{t.name}]" for t in TAGS)  # 喂进 system prompt 让模型只在这几个里挑，形如 [happy] [sad]
