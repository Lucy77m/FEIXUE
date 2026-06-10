# author: bdth
# email: 2074055628@qq.com
# 桌宠情绪引擎：维护情绪(效价/唤醒/亲密度)状态、随时间衰减回基线并持久化

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from desktop_pet.settings import DATA_DIR, atomic_write_text

_STATE_PATH = DATA_DIR / "emotion.json"

_BASELINE_VALENCE = 0.25
_BASELINE_AROUSAL = 0.35
_REACTIVITY = 0.6
_RECOVERY_PER_HOUR = 0.5

_RAPPORT_FLOOR = 0.15
_RAPPORT_DECAY_PER_DAY = 0.03

_APPRAISALS = {
    "interaction": (0.02, 0.05, 0.01),
    "task_done": (0.15, 0.05, 0.02),
    "task_failed": (-0.15, 0.15, 0.0),
    "returned": (0.20, 0.15, 0.0),
    "praised": (0.30, 0.10, 0.05),
    "scolded": (-0.30, 0.10, -0.03),
}

_PRAISE_CUES = (
    "谢谢", "感谢", "棒", "厉害", "真棒", "太棒", "干得好", "做得好", "好样", "聪明",
    "乖", "可爱", "喜欢你", "爱你", "优秀", "给力", "真不错", "帮大忙", "辛苦了", "做得不错",
    "thank", "good job", "great job", "well done", "awesome", "smart", "clever",
    "love you", "good boy", "nice job", "brilliant",
)
_SCOLD_CUES = (
    "笨", "蠢", "垃圾", "废物", "没用", "滚开", "闭嘴", "讨厌", "弱智", "白痴", "智障",
    "差劲", "蠢货", "废柴", "真烦", "烦死", "别废话", "太差", "真没用",
    "stupid", "dumb", "idiot", "useless", "trash", "garbage", "shut up",
    "hate you", "you suck", "worthless",
)


_NEGATORS = ("不", "没", "别", "勿", "甭", "无须", "毫不", "并不",
             "not ", "n't", "no ", "never")
_SELF_REF = ("我", "俺", "咱", "自己", "i'm", "i am", "myself")
_CUE_LOOKBACK = 4


def _cue_hit(low: str, cues: tuple[str, ...]) -> bool:
    """命中夸/骂线索词；被否定的、用户自指的那次不算。"""
    for cue in cues:
        start = low.find(cue)
        while start != -1:
            # 往前看 4 个字符就够：「你不笨」算不上骂、「我真没用」是用户自嘲不该扣分。
            pre = low[max(0, start - _CUE_LOOKBACK):start]
            if not any(n in pre for n in _NEGATORS) and not any(r in pre for r in _SELF_REF):
                return True
            start = low.find(cue, start + 1)
    return False


def appraise_user_message(text: str) -> str | None:
    """从一句话粗判夸/骂，返回对应事件名给 apply 用；判不准就 None。"""
    if not text:
        return None
    low = text.lower()
    scolded = _cue_hit(low, _SCOLD_CUES)
    praised = _cue_hit(low, _PRAISE_CUES)
    # 既夸又骂、或两边都没命中——暧昧就不瞎猜，交回 None。
    if scolded == praised:
        return None
    return "scolded" if scolded else "praised"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _state_name(valence: float, arousal: float) -> str:
    if valence >= 0.15:
        return "excited" if arousal >= 0.5 else "content"
    if valence <= -0.15:
        return "anxious" if arousal >= 0.5 else "down"
    return "content"


@dataclass
class _State:
    valence: float = _BASELINE_VALENCE
    arousal: float = _BASELINE_AROUSAL
    rapport: float = _RAPPORT_FLOOR
    updated_at: str = ""


class EmotionEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = self._load()
        with self._lock:
            self._settle_decay()
            self._save()

    def reset(self) -> None:
        with self._lock:
            self._state = _State(updated_at=self._now())
            self._save()

    def apply(self, event: str) -> None:
        """按 _APPRAISALS 把一次事件叠进情绪；未知事件名 → 全 0 即无变化。"""
        dv, da, dr = _APPRAISALS.get(event, (0.0, 0.0, 0.0))
        with self._lock:
            self._settle_decay()  # 先把上次到现在的衰减结清，再叠新增量，否则旧值会被双算
            state = self._state
            state.valence = _clamp(state.valence + dv * _REACTIVITY, -1.0, 1.0)
            state.arousal = _clamp(state.arousal + da * _REACTIVITY, 0.0, 1.0)
            # 亲密度涨幅随当前值递减（越熟越难再涨）；掉的时候是硬扣，不打折。
            gain = dr * (1.0 - state.rapport) if dr > 0 else dr
            state.rapport = _clamp(state.rapport + gain, _RAPPORT_FLOOR, 1.0)
            state.updated_at = self._now()
            self._save()

    def snapshot(self) -> tuple[float, float, float]:
        with self._lock:
            s = self._decayed()
            return s.valence, s.arousal, s.rapport

    def animation_state(self) -> str:
        valence, arousal, _ = self.snapshot()
        return _state_name(valence, arousal)

    def tone_hint(self) -> str:
        # 延迟 import：prompts 那边会回头引情绪，模块级 import 会循环依赖。
        from desktop_pet.agent.prompts import tone_hint as _tone_hint

        valence, arousal, rapport = self.snapshot()
        return _tone_hint(_state_name(valence, arousal), rapport)

    def _decayed(self) -> _State:
        """算到此刻的衰减值，返回副本——不动存储里的原状态。"""
        s = _State(self._state.valence, self._state.arousal, self._state.rapport, self._state.updated_at)
        if not s.updated_at:
            return s
        try:
            last = datetime.fromisoformat(s.updated_at)
        except ValueError:
            return s
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)  # 老存档没带时区，按 UTC 当裸时间补上
        hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        if hours <= 0:  # 时钟回拨/跨时区导致负值，别往反方向衰减，原样返回
            return s
        fraction = min(1.0, _RECOVERY_PER_HOUR * hours)  # 封顶到 1，停机几天也只是恰好回到基线不过冲
        s.valence += (_BASELINE_VALENCE - s.valence) * fraction
        s.arousal += (_BASELINE_AROUSAL - s.arousal) * fraction
        days = hours / 24.0
        s.rapport += (_RAPPORT_FLOOR - s.rapport) * min(1.0, _RAPPORT_DECAY_PER_DAY * days)
        return s

    def _settle_decay(self) -> None:
        """衰减结清、updated_at 归零到此刻——叠新增量前先调，否则旧值会被重复衰减。"""
        self._state = self._decayed()
        self._state.updated_at = self._now()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _load(self) -> _State:
        """读盘还原状态；文件缺失/损坏/字段对不上一律退回默认 _State，不让坏档崩掉启动。"""
        if not _STATE_PATH.exists():
            return _State()
        try:
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError):
            return _State()
        if not isinstance(data, dict):
            return _State()
        fields = _State.__dataclass_fields__
        try:
            # 只挑认识的键灌进去：旧版本多出来的字段直接丢，免得 _State() 报未知参数。
            return _State(**{k: v for k, v in data.items() if k in fields})
        except (TypeError, ValueError):
            return _State()

    def _save(self) -> None:
        atomic_write_text(_STATE_PATH, json.dumps(asdict(self._state), ensure_ascii=False, indent=2))


emotion = EmotionEngine()
