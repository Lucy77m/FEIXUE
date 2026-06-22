# 情绪引擎 维护情绪状态 随时间衰减回基线并持久化

from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
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
    "fed": (0.18, 0.10, 0.015),
    "hurt": (-0.25, 0.30, -0.01),
    "played": (0.12, 0.12, 0.01),
}

_BOND_STAGES = (
    (0.60, "intimate"),
    (0.45, "in_sync"),
    (0.30, "familiar"),
    (0.00, "new"),
)
_BOND_EVENT_KEEP = 12

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
# 按标点切小句 否定只在同一小句内才管得着线索词
_CLAUSE_SPLIT = re.compile(r"[。！？!?.,，、；;:：\n]+")


def _cue_hit(low: str, cues: tuple[str, ...]) -> bool:
    """命中夸骂线索词 否定按整小句前缀扫 自指只看紧邻几字"""
    for clause in _CLAUSE_SPLIT.split(low):
        for cue in cues:
            start = clause.find(cue)
            while start != -1:
                pre = clause[:start]                                # 同小句里线索词之前的全部
                near = clause[max(0, start - _CUE_LOOKBACK):start]  # 紧邻几字
                negated = any(n in pre for n in _NEGATORS)
                selfref = any(r in near for r in _SELF_REF)
                if not negated and not selfref:
                    return True
                start = clause.find(cue, start + 1)
    return False


def appraise_user_message(text: str) -> str | None:
    """粗判夸骂返回事件名 判不准返回None"""
    if not text:
        return None
    low = text.lower()
    scolded = _cue_hit(low, _SCOLD_CUES)
    praised = _cue_hit(low, _PRAISE_CUES)
    # 都中或都没中就不猜
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


def _bond_stage(value: float) -> str:
    for threshold, name in _BOND_STAGES:
        if value >= threshold:
            return name
    return "new"


@dataclass
class _State:
    valence: float = _BASELINE_VALENCE
    arousal: float = _BASELINE_AROUSAL
    rapport: float = _RAPPORT_FLOOR
    peak_rapport: float = _RAPPORT_FLOOR
    bond_events: list[dict] = field(default_factory=list)
    updated_at: str = ""


class EmotionEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = self._load()
        self._events: deque = deque(maxlen=16)  # 最近动情绪的事件 存单调时刻和事件名 只在内存
        self._stage_callback = None
        with self._lock:
            self._settle_decay()
            self._state.peak_rapport = max(self._state.peak_rapport, self._state.rapport)
            self._save()

    def reset(self) -> None:
        with self._lock:
            self._state = _State(updated_at=self._now())
            self._save()

    def set_stage_callback(self, callback) -> None:
        self._stage_callback = callback

    def apply(self, event: str) -> None:
        """按事件表叠情绪增量 未知事件无变化"""
        dv, da, dr = _APPRAISALS.get(event, (0.0, 0.0, 0.0))
        unlocked = ""
        with self._lock:
            self._settle_decay()  # 先结清衰减再叠增量
            state = self._state
            old_stage = _bond_stage(state.peak_rapport)
            state.valence = _clamp(state.valence + dv * _REACTIVITY, -1.0, 1.0)
            state.arousal = _clamp(state.arousal + da * _REACTIVITY, 0.0, 1.0)
            # 涨幅随当前值递减 扣分不打折
            gain = dr * (1.0 - state.rapport) if dr > 0 else dr
            state.rapport = _clamp(state.rapport + gain, _RAPPORT_FLOOR, 1.0)
            state.peak_rapport = max(state.peak_rapport, state.rapport)
            state.updated_at = self._now()
            # 留痕是为了能说出为什么这心情 但interaction每条消息都来 太碎 不记
            if event in _APPRAISALS and event != "interaction":
                self._events.append((time.monotonic(), event))
                if dr != 0:
                    state.bond_events.append({"event": event, "at": state.updated_at})
                    state.bond_events = state.bond_events[-_BOND_EVENT_KEEP:]
            new_stage = _bond_stage(state.peak_rapport)
            if new_stage != old_stage:
                unlocked = new_stage
            self._save()
        if unlocked and self._stage_callback is not None:
            try:
                self._stage_callback(unlocked)
            except Exception:
                pass

    def snapshot(self) -> tuple[float, float, float]:
        with self._lock:
            s = self._decayed()
            return s.valence, s.arousal, s.rapport

    def unlocked_rapport(self) -> float:
        with self._lock:
            return max(self._state.peak_rapport, self._state.rapport)

    def bond_snapshot(self) -> dict:
        with self._lock:
            current = self._decayed().rapport
            peak = max(self._state.peak_rapport, current)
            stage = _bond_stage(peak)
            ordered = [name for _threshold, name in reversed(_BOND_STAGES)]
            index = ordered.index(stage)
            next_stage = ordered[index + 1] if index + 1 < len(ordered) else ""
            recent = [str(item.get("event", "")) for item in self._state.bond_events[-4:]
                      if item.get("event")]
        return {
            "rapport": current,
            "peak_rapport": peak,
            "stage": stage,
            "next_stage": next_stage,
            "recent_events": list(reversed(recent)),
        }

    def animation_state(self) -> str:
        valence, arousal, _ = self.snapshot()
        return _state_name(valence, arousal)

    def tone_hint(self) -> str:
        # 延迟import避免循环依赖
        from desktop_pet.agent.prompts import tone_hint as _tone_hint

        valence, arousal, rapport = self.snapshot()
        return _tone_hint(_state_name(valence, arousal), rapport)

    def mood_note(self) -> str:
        """心情明显偏离基线时给一句为什么 最近一小时哪些事动了它 平淡就返回空串"""
        valence, arousal, _ = self.snapshot()
        if abs(valence - _BASELINE_VALENCE) < 0.18 and arousal < 0.55:
            return ""  # 心情平淡 不必解释
        now = time.monotonic()
        with self._lock:
            recent = [ev for ts, ev in self._events if now - ts <= 3600]
        if not recent:
            return ""
        label = {
            "praised": "they praised you", "scolded": "they scolded / criticized you",
            "task_done": "a task went well", "task_failed": "a task failed",
            "returned": "they came back after being away", "fed": "they fed you",
            "hurt": "they were rough with you (flung you around)",
        }
        parts = []
        for ev, c in Counter(recent).items():
            name = label.get(ev)
            if name:
                parts.append(name + (f" ×{c}" if c > 1 else ""))
        if not parts:
            return ""
        return ("[Why you feel this way — real things from the last hour that moved your mood; "
                "if they ask what's up, you can be honest about these]: " + "; ".join(parts))

    def _decayed(self) -> _State:
        """算衰减后的状态副本"""
        s = _State(
            valence=self._state.valence,
            arousal=self._state.arousal,
            rapport=self._state.rapport,
            peak_rapport=self._state.peak_rapport,
            bond_events=list(self._state.bond_events),
            updated_at=self._state.updated_at,
        )
        if not s.updated_at:
            return s
        try:
            last = datetime.fromisoformat(s.updated_at)
        except ValueError:
            return s
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)  # 没时区按utc补
        hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        if hours <= 0:  # 时钟回拨不衰减
            return s
        fraction = min(1.0, _RECOVERY_PER_HOUR * hours)
        s.valence += (_BASELINE_VALENCE - s.valence) * fraction
        s.arousal += (_BASELINE_AROUSAL - s.arousal) * fraction
        days = hours / 24.0
        s.rapport += (_RAPPORT_FLOOR - s.rapport) * min(1.0, _RAPPORT_DECAY_PER_DAY * days)
        return s

    def _settle_decay(self) -> None:
        """结清衰减并刷新updated_at"""
        self._state = self._decayed()
        self._state.updated_at = self._now()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _load(self) -> _State:
        """读盘还原状态 坏档退默认"""
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
            # 只取认识的键
            state = _State(**{k: v for k, v in data.items() if k in fields})
            state.rapport = float(state.rapport)
            state.peak_rapport = max(float(state.peak_rapport), state.rapport)
            if not isinstance(state.bond_events, list):
                state.bond_events = []
            state.bond_events = [item for item in state.bond_events
                                 if isinstance(item, dict) and item.get("event")][-_BOND_EVENT_KEEP:]
            return state
        except (TypeError, ValueError):
            return _State()

    def _save(self) -> None:
        atomic_write_text(_STATE_PATH, json.dumps(asdict(self._state), ensure_ascii=False, indent=2))


emotion = EmotionEngine()
