# author: bdth
# email: 2074055628@qq.com
# 桌宠角色BlobPet 状态机推进与形象绘制 绘制细节拆去旁边几个mixin文件

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QFont, QPainter

from desktop_pet.emotion.tags import EXPRESSIONS as _EXPRESSIONS
from desktop_pet.pet import adornments
from desktop_pet.pet.activities import _ACTIVITIES, _ACTIVITY_BODY, _ACTIVITY_GAP, _TRAVEL
from desktop_pet.pet.props.activities import draw_pointer
from desktop_pet.pet.props.registry import COSTUMES, WORN_COSTUMES
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.behaviors import Category, registry
from desktop_pet.pet.behaviors.easing import ease_out
from desktop_pet.pet.blob_defs import (
    _BLINK_DUR,
    _BLOB_BASE,
    _CATNAP_CHANCE,
    _CATNAP_DUR,
    _CATNAP_GAP,
    _DAYDREAM_DUR,
    _DAYDREAM_GAP,
    _DRAG_SINK,
    _DRAG_STRETCH,
    _DRAG_SWAY_DEG,
    _DRAG_SWAY_HZ,
    _DREAM_COLORS,
    _DREAM_GLYPHS,
    _DREAM_LIFE,
    _DREAM_SPAWN,
    _EXPR_HOLD,
    _IDLE_FIDGETS,
    _LOOK_AT_HOLD,
    _SETTLE_DUR,
    _SLEEP_BREATH_HZ,
    _SLEEP_FADE,
    _SLEEP_SINK,
    _THINK_GLANCE_AMT,
    _THINK_GLANCE_GATE,
    _THINK_GLANCE_HZ,
    _THINK_SETTLE,
    _THINK_STEP_POSE,
    _edge_alpha,
)
from desktop_pet.pet.blob_face import FaceMixin
from desktop_pet.pet.blob_fx import ReactFxMixin
from desktop_pet.pet.blob_think import ThinkMixin
from desktop_pet.pet.fx import smooth_font


class BlobPet(ThinkMixin, ReactFxMixin, FaceMixin):
    """桌宠形象本体 状态机加绘制"""

    def __init__(self) -> None:
        self._t = 0.0
        self._expr = "neutral"
        self._costume: str | None = None
        self._talking = False
        self._blinking = False
        self._blink_e = 0.0
        self._next_blink = random.uniform(1.0, 3.0)
        self._react: tuple[str, float, float] | None = None
        self._react_intensity = 1.0
        self._shy = False
        self._shy_e = 0.0
        self._hot = False
        self._hot_e = 0.0
        self._squeeze = False
        self._squeeze_e = 0.0
        self._lowbatt = False
        self._lowbatt_e = 0.0
        self._blanket = False
        self._blanket_e = 0.0
        self._cake = False
        self._cake_e = 0.0
        self._cake_lit = True
        self._cake_smoke = 0.0
        self.on_activity_done = None  # 小品演完的回调 上层挂
        self._weather = ""  # rain snow melt
        self._weather_e = 0.0
        self._calm_e = 1.0  # 非演出的渐变量 装饰让位演出
        self._settle = 0.0
        self._hold = 0.0
        self._busy = False
        self._lecturing = False
        self._turn = 0.0
        self._turn_target = 0.0
        self._look_timer = random.uniform(2.0, 4.0)
        self._look_hold = 0.0
        self._fidget_timer = random.uniform(14.0, 28.0)
        self._daydream_timer = random.uniform(*_DAYDREAM_GAP)
        self._daydream_left = 0.0
        self._dream_spawn = 0.0
        self._dream_bubbles: list[list] = []
        self._win_h = 220.0
        self._fx_origin_y = 110.0
        self._activity: str | None = None
        self._act_sticky = False  # 点名要求的演出 说话思考不打断
        self._pending_perform: str | None = None
        self._wants_travel = False
        self._activity_timer = random.uniform(*_ACTIVITY_GAP)
        self._activity_age = 0.0  # 小品已演时长 卡死兜底用
        self._stage_i = 0
        self._stage_left = 0.0
        self._stage_dur = 1.0
        self._stage_p = 0.0
        self._activity_bubble = 0.0
        self._think_e = 0.0
        self._think_pose = 0
        self._think_pose_prev = 0
        self._think_xfade = 1.0
        self._think_dwell_left = 0.0
        self._think_held = 0.0
        self._think_cue_pose: int | None = None
        self._think_cue_age = 0.0
        self._think_energy = 0.5
        self._asleep = False
        self._falling_asleep = False
        self._sleep_e = 0.0
        self._dragging = False
        self._hidden = False
        self._catnap_timer = random.uniform(*_CATNAP_GAP)
        self._catnap_left = 0.0


    def set_shy(self, on: bool) -> None:
        """看到密码框捂眼回避"""
        self._shy = bool(on)

    def set_hot(self, on: bool) -> None:
        """cpu烧起来了 冒汗扇扇子"""
        self._hot = bool(on)

    def set_squeeze(self, on: bool) -> None:
        """内存满了被挤扁"""
        self._squeeze = bool(on)

    def set_low_batt(self, on: bool) -> None:
        """电量告急 焦躁"""
        self._lowbatt = bool(on)

    def set_blanket(self, on: bool) -> None:
        """深夜盖小被子"""
        self._blanket = bool(on)

    def set_cake(self, on: bool) -> None:
        """端出纪念日蛋糕"""
        self._cake = bool(on)
        if on:
            self._cake_lit = True
            self._cake_smoke = 0.0

    def blow_cake(self) -> bool:
        """吹蜡烛 蜡烛亮着才有效"""
        if not self._cake or not self._cake_lit:
            return False
        self._cake_lit = False
        self._cake_smoke = 2.2
        return True

    def set_weather(self, kind: str) -> None:
        """天气拟态 rain打伞 snow堆雪人 melt热化"""
        if kind in ("rain", "snow", "melt"):
            self._weather = kind
        else:
            self._weather = ""

    def set_expression(self, name: str) -> None:
        if name in _EXPRESSIONS:
            self._expr = name
            self._hold = 0.0 if name == "neutral" else _EXPR_HOLD

    def set_costume(self, name: str | None) -> None:
        if self._activity is not None and self._act_sticky:
            return  # 点名演出进行中 道具属于小品 别被回复气泡的随机戏服(常是 None)覆盖掉
        self._costume = name if name in COSTUMES else None
        if self._costume:
            self._hold = max(self._hold, _EXPR_HOLD)

    def set_talking(self, on: bool) -> None:
        self._talking = on

    @property
    def is_talking(self) -> bool:
        return self._talking

    def set_busy(self, busy: bool) -> None:
        # busy时强制思考脸并清掉发呆反应
        self._busy = busy
        if busy:
            self._expr = "thinking"
            self._hold = 0.0
            self._react = None
            self._settle = 0.0
            self._dream_bubbles = []
            self._daydream_left = 0.0
            if self._activity is None:
                # 清掉上一条回复留下的临时戏服:_hold 被清零后衰减清除路径就不再跑 否则戏服会一直挂着
                # (活动道具由 _activity 管 不在这清)
                self._costume = None
        elif self._expr == "thinking":
            self.set_expression("neutral")

    def set_lecturing(self, on: bool) -> None:
        self._lecturing = on

    @property
    def _pondering(self) -> bool:
        return self._busy or self._expr == "thinking"

    @property
    def _performing(self) -> bool:
        """正在说话思考演反应或小品 环境装饰要让位"""
        return (self._talking or self._busy or self._lecturing or self._dragging
                or self._hidden or self._react is not None or self._activity is not None
                or self._expr == "thinking")

    @property
    def _worn_costume(self) -> bool:
        return self._costume in WORN_COSTUMES

    def set_think_energy(self, arousal: float) -> None:
        self._think_energy = max(0.0, min(1.0, arousal))

    def on_think_step(self, kind: str) -> None:
        """agent每出一步给个暗示pose"""
        pose = _THINK_STEP_POSE.get(kind)
        if pose is not None:
            self._think_cue_pose = pose
            self._think_cue_age = 0.0

    def fall_asleep(self) -> None:
        if self._asleep or self._falling_asleep:
            return
        if (self._busy or self._pondering or self._talking or self._lecturing
                or self._activity or self._dragging):
            return                      # 非空闲不睡
        self._falling_asleep = True
        self.react("yawn")

    def wake(self) -> None:
        if self._asleep or self._falling_asleep:
            self._asleep = False
            self._falling_asleep = False
            self.react("stretch")

    @property
    def is_asleep(self) -> bool:
        return self._asleep or self._falling_asleep

    @property
    def is_catnapping(self) -> bool:
        return self._catnap_left > 0.0

    def set_dragging(self, on: bool) -> None:
        self._dragging = on

    def set_hidden(self, on: bool) -> None:
        self._hidden = on

    def look_at(self, turn: float) -> None:
        if self._asleep or self._dragging:
            return
        self._turn_target = max(-1.0, min(1.0, turn))
        self._look_hold = _LOOK_AT_HOLD

    def celebrate(self) -> None:
        self.set_expression("happy")
        self.set_costume("party")
        self.react("celebrate")

    def slump(self) -> None:
        self.set_expression("sad")
        self.set_costume("raincloud")
        self.react("slump")

    def react(self, name: str, intensity: float = 1.0) -> None:
        if self._activity is not None and self._act_sticky:
            return  # 点名演出进行中 身体反应让位 表情不受影响
        spec = registry.get(name)
        if spec is not None and spec.category == Category.REACTION:
            self._react = (name, 0.0, spec.duration)
            self._react_intensity = intensity

    def start_activity(self, name: str) -> bool:
        if name not in _ACTIVITIES:
            return False
        self.wake()
        self._react = None
        self._activity = name
        self._activity_age = 0.0
        self._act_sticky = True  # 点名演出 自己的回复气泡不许掐它
        self._costume = _ACTIVITIES[name][0]
        self._stage_i = 0
        self._enter_stage(_ACTIVITIES[name][3][0])
        self._activity_timer = random.uniform(*_ACTIVITY_GAP)
        return True

    @property
    def is_reacting(self) -> bool:
        return self._react is not None

    @property
    def in_activity(self) -> bool:
        return self._activity is not None

    def take_travel_request(self) -> bool:
        """取走一次穿越请求"""
        if self._wants_travel:
            self._wants_travel = False
            return True
        return False

    def clear_pending(self) -> None:
        self._pending_perform = None

    def yield_performance(self) -> None:
        """用户来新消息 点名演出退掉粘性 让位给思考姿势"""
        self._act_sticky = False

    def perform(self, name: str) -> bool:
        """点名小品或反应 入队等空闲再播"""
        if name in _ACTIVITIES or (
            (spec := registry.get(name)) is not None and spec.category == Category.REACTION
        ):
            self._pending_perform = name
            self.wake()
            return True
        return False

    def _do_perform(self, name: str) -> None:
        if name in _ACTIVITIES:
            self.start_activity(name)
        else:
            self.react(name)


    def advance(self, dt: float) -> None:
        """每帧推进一次状态机"""
        self._t += dt
        if self._pending_perform is not None and not (
            self._busy or self._pondering or self._talking or self._asleep
            or self._dragging or self._hidden or self._react or self._activity
        ):
            name, self._pending_perform = self._pending_perform, None
            self._do_perform(name)
        if self._pondering:
            if self._think_e <= 0.0:
                self._enter_think()
            self._think_e = min(1.0, self._think_e + dt)
            self._advance_think(dt)
        else:
            self._think_e = max(0.0, self._think_e - dt * 2.0)
        if self._asleep:
            self._sleep_e = min(1.0, self._sleep_e + dt / _SLEEP_FADE)
        else:
            self._sleep_e = max(0.0, self._sleep_e - dt / _SLEEP_FADE * 1.5)
        if self._shy:
            self._shy_e = min(1.0, self._shy_e + dt * 3.5)
        else:
            self._shy_e = max(0.0, self._shy_e - dt * 2.5)
        for flag, attr in (("_hot", "_hot_e"), ("_squeeze", "_squeeze_e"),
                           ("_lowbatt", "_lowbatt_e"), ("_cake", "_cake_e")):
            e = getattr(self, attr)
            if getattr(self, flag):
                setattr(self, attr, min(1.0, e + dt * 1.6))
            else:
                setattr(self, attr, max(0.0, e - dt * 1.2))
        # 被子只有真睡着才盖 醒了就掀
        if self._blanket and self._asleep:
            self._blanket_e = min(1.0, self._blanket_e + dt * 1.6)
        else:
            self._blanket_e = max(0.0, self._blanket_e - dt * 2.0)
        # 只有真正演出时环境装饰才平滑退场 小品 反应 拖拽 藏起这几种算
        # 说话和思考不算 否则伞之类的持续装饰会随每句话一闪一闪
        if self._dragging or self._hidden or self._react is not None or self._activity is not None:
            self._calm_e = max(0.0, self._calm_e - dt * 3.5)
        else:
            self._calm_e = min(1.0, self._calm_e + dt * 2.0)
        if self._cake_smoke > 0.0:
            self._cake_smoke = max(0.0, self._cake_smoke - dt)
        if self._weather:
            self._weather_e = min(1.0, self._weather_e + dt * 1.2)
        else:
            self._weather_e = max(0.0, self._weather_e - dt * 1.0)
        if self._hold > 0.0 and not self._busy and self._activity is None:
            self._hold -= dt
            if self._hold <= 0.0:
                self._expr = "neutral"
                self._costume = None
        self._advance_blink(dt)
        self._advance_look(dt)
        self._advance_daydream(dt)
        self._advance_activity(dt)
        self._advance_catnap(dt)
        if self._react:
            name, elapsed, dur = self._react
            elapsed += dt
            if elapsed >= dur:
                self._react = None
                self._settle = _SETTLE_DUR
                self._fidget_timer = max(self._fidget_timer, random.uniform(9.0, 16.0))
                if self._falling_asleep:        # 哈欠放完才正式睡着
                    self._asleep = True
                    self._falling_asleep = False
            else:
                self._react = (name, elapsed, dur)
            return                              # 播反应时独占
        if self._settle > 0:
            self._settle = max(0.0, self._settle - dt)
        self._fidget_timer -= dt
        if self._fidget_timer <= 0:
            if not (self._pondering or self._asleep or self._dragging or self._hidden or self._talking
                    or self._lecturing or self._busy) and self._activity is None:
                fidget = selector.select(Category.REACTION, candidates=_IDLE_FIDGETS)
                if fidget:
                    self.react(fidget)
            self._fidget_timer = random.uniform(14.0, 28.0)

    def _advance_catnap(self, dt: float) -> None:
        # 自发打盹 有事立刻打断并重置计时
        if self._catnap_left > 0.0:
            if (self._busy or self._pondering or self._talking or self._lecturing
                    or self._dragging or self._activity):
                self._catnap_left = 0.0
                self._catnap_timer = random.uniform(*_CATNAP_GAP)
                self.wake()
                return
            self._catnap_left -= dt
            if self._catnap_left <= 0.0:
                self._catnap_left = 0.0
                self.wake()
            return
        if (self._pondering or self._asleep or self._falling_asleep or self._dragging
                or self._hidden or self._react or self._activity or self._talking
                or self._lecturing or self._busy):
            self._catnap_timer = random.uniform(*_CATNAP_GAP)
            return
        self._catnap_timer -= dt
        if self._catnap_timer <= 0.0:
            self._catnap_timer = random.uniform(*_CATNAP_GAP)
            if random.random() < _CATNAP_CHANCE:
                self._catnap_left = random.uniform(*_CATNAP_DUR)
                self.fall_asleep()

    def _advance_daydream(self, dt: float) -> None:
        idle = not (self._pondering or self._asleep or self._dragging or self._hidden or self._react or self._activity
                    or self._talking or self._lecturing or self._busy)
        if self._daydream_left > 0.0:
            self._daydream_left -= dt
            if not idle:
                self._daydream_left = 0.0
            else:
                self._dream_spawn -= dt
                if self._dream_spawn <= 0.0:
                    self._spawn_dream()
                    self._dream_spawn = random.uniform(*_DREAM_SPAWN)
        else:
            self._daydream_timer -= dt
            if self._daydream_timer <= 0.0:
                if idle:
                    self._daydream_left = random.uniform(*_DAYDREAM_DUR)
                    self._dream_spawn = 0.0
                self._daydream_timer = random.uniform(*_DAYDREAM_GAP)
        for bubble in self._dream_bubbles:
            bubble[2] += dt                     # age超寿命就剔掉
        self._dream_bubbles = [b for b in self._dream_bubbles if b[2] < b[3]]

    def _advance_activity(self, dt: float) -> None:
        # 小品逐阶段推进 走完最后一阶播收尾反应
        # 说话思考忙这类软打断只掐自发小品 点名的演完 拖拽藏起睡着这类硬打断谁都掐
        hard = self._asleep or self._dragging or self._hidden or self._react
        soft = self._pondering or self._talking or self._lecturing or self._busy
        idle = not (hard or soft)
        if self._activity is not None:
            self._activity_age += dt
            stages = _ACTIVITIES[self._activity][3]
            # 卡死兜底:演太久才强制收场 防 blob 缩没卡住。阈值取"自身阶段总时长 + 5s 余量"
            # 不能用固定 25s——sprout 自身就 26s 会被误杀 收尾动作和回调永远播不到
            if self._activity_age > sum(s[1] for s in stages) + 5.0:
                self._end_activity()
                return
            if hard or (soft and not self._act_sticky):
                self._end_activity()
                return
            self._stage_left -= dt
            self._stage_dur = max(0.1, stages[self._stage_i][1])
            self._stage_p = 1.0 - max(0.0, self._stage_left) / self._stage_dur

            glyph = stages[self._stage_i][2]
            self._activity_bubble -= dt
            if glyph and self._activity_bubble <= 0.0:
                self._spawn_dream(glyph)
                self._activity_bubble = random.uniform(1.0, 2.2)
            if self._stage_left <= 0.0:
                self._stage_i += 1
                if self._stage_i >= len(stages):
                    done_name = self._activity
                    finish = _ACTIVITIES[self._activity][2]
                    self._end_activity()
                    self.react(finish)
                    if self.on_activity_done is not None:
                        try:
                            self.on_activity_done(done_name)
                        except Exception:
                            pass
                else:
                    self._enter_stage(stages[self._stage_i])
        else:
            self._activity_timer -= dt
            if self._activity_timer <= 0.0:
                self._activity_timer = random.uniform(*_ACTIVITY_GAP)
                if idle:
                    name = random.choice(list(_ACTIVITIES) + [_TRAVEL])  # 穿越混进抽签池
                    if name == _TRAVEL:
                        self._wants_travel = True
                    else:
                        self._activity = name
                        self._activity_age = 0.0
                        self._act_sticky = False  # 自发小品 软打断(说话/思考)就让位
                        self._costume = _ACTIVITIES[name][0]
                        self._stage_i = 0
                        self._enter_stage(_ACTIVITIES[name][3][0])

    def _enter_stage(self, stage: tuple) -> None:
        self._stage_dur = max(0.1, stage[1])
        self._stage_left = self._stage_dur
        self._stage_p = 0.0
        self._activity_bubble = 0.0

    def _end_activity(self) -> None:
        self._activity = None
        self._act_sticky = False
        self._costume = None
        self._stage_i = 0
        self._stage_p = 0.0

    @property
    def _stage(self) -> str:
        if self._activity is None:
            return ""
        return _ACTIVITIES[self._activity][3][self._stage_i][0]

    def _activity_body_transform(self, bw: float, bh: float):
        """小品期间的身体位姿增量"""
        curve = _ACTIVITY_BODY.get(self._activity)
        if curve is None:
            return 0.0, 0.0, 0.0, 1.0, 1.0
        return curve(self._stage, self._stage_p, self._t, bw, bh)

    def _spawn_dream(self, glyph: str | None = None) -> None:
        self._dream_bubbles.append([
            glyph or random.choice(_DREAM_GLYPHS), random.uniform(-0.15, 0.55),
            0.0, random.uniform(*_DREAM_LIFE), random.choice(_DREAM_COLORS),
        ])

    def _draw_dream(self, painter: QPainter, cx: float, head_y: float, bw: float, bh: float) -> None:
        font = smooth_font(QFont("Microsoft YaHei UI"))
        font.setPixelSize(max(11, int(bw * 0.26)))
        painter.setFont(font)
        for glyph, x_frac, age, life, color in self._dream_bubbles:
            frac = age / life                   # 前段淡入后段淡出 一边升一边飘
            if frac < 0.18:
                alpha = frac / 0.18
            elif frac > 0.6:
                alpha = max(0.0, (1.0 - frac) / 0.4)
            else:
                alpha = 1.0
            rise = ease_out(min(frac, 1.0)) * bh * 0.8
            x = cx + x_frac * bw + math.sin((age + x_frac) * 3.0) * bw * 0.05
            y = head_y - bh * 0.9 - rise
            alpha *= _edge_alpha(y, self._win_h)
            painter.setPen(QColor(color.red(), color.green(), color.blue(), int(225 * alpha)))
            painter.drawText(QPointF(x, y), glyph)

    def _advance_blink(self, dt: float) -> None:
        if self._blinking:
            self._blink_e += dt
            if self._blink_e >= _BLINK_DUR:
                self._blinking = False
                self._next_blink = random.uniform(2.5, 5.5)
        else:
            self._next_blink -= dt
            if self._next_blink <= 0:
                self._blinking = True
                self._blink_e = 0.0

    def _advance_look(self, dt: float) -> None:
        # 视线目标按优先级定
        if self._look_hold > 0.0:
            self._look_hold -= dt
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 6.0)
            return
        if self._activity is not None:
            self._turn_target = _ACTIVITIES[self._activity][1]
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 4.0)
            return
        if self._react is not None:
            self._turn_target = 0.0
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 5.0)
            return
        if self._pondering:
            wander = math.sin(self._t * _THINK_GLANCE_HZ)
            if abs(wander) > _THINK_GLANCE_GATE:    # 过门限才偏头看一眼
                reach = (abs(wander) - _THINK_GLANCE_GATE) / (1.0 - _THINK_GLANCE_GATE)
                self._turn_target = math.copysign(reach, wander) * _THINK_GLANCE_AMT
            else:
                self._turn_target = 0.0
            self._turn += (self._turn_target - self._turn) * min(1.0, dt * 3.0)
            return
        self._look_timer -= dt
        if self._look_timer <= 0:
            self._turn_target = random.choice([0.0, 0.0, 0.0, -0.8, 0.8, -0.5, 0.5])
            self._look_timer = random.uniform(1.5, 4.0)
        self._turn += (self._turn_target - self._turn) * min(1.0, dt * 4.0)


    def paint(self, painter: QPainter, w: int, h: int) -> None:
        """画一帧 各状态叠位姿增量后一次性变换出图"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._win_h = float(h)
        bw, bh = _BLOB_BASE * 0.62, _BLOB_BASE * 0.44
        cx, cy = w / 2, h / 2

        breath = math.sin(self._t * 2.0)       # 永远在呼吸
        ox = 0.0
        oy = breath * (bh * 0.032)
        rot = math.sin(self._t * 0.8) * 1.5
        sxm, sym = 1 - 0.06 * breath, 1 + 0.06 * breath

        if self._talking:
            oy += math.sin(self._t * 16) * (bh * 0.02)
        if self._expr == "confused":
            rot += math.sin(self._t * 2.4) * 4
        if self._lecturing:
            rot += math.sin(self._t * 1.6) * 2
        if self._dragging:
            rot += math.sin(self._t * _DRAG_SWAY_HZ) * _DRAG_SWAY_DEG
            oy += _DRAG_SINK * bh
            sxm *= 1 - _DRAG_STRETCH * 0.5
            sym *= 1 + _DRAG_STRETCH


        think_gate = ease_out(min(self._think_e / _THINK_SETTLE, 1.0))
        # 穿戏服时不叠思考姿势也不画思考手
        if think_gate > 0.0 and not self._react and not self._worn_costume:
            d_ox, d_oy, d_rot, d_sx, d_sy = self._think_transform(bw, bh, think_gate)
            ox += d_ox
            oy += d_oy
            rot += d_rot
            sxm *= d_sx
            sym *= d_sy

        if self._react:
            name, elapsed, dur = self._react
            d_ox, d_oy, d_rot, mx, my = self._react_transform(name, min(elapsed / dur, 1.0), bw, bh)
            k = self._react_intensity
            ox += d_ox * k
            oy += d_oy * k
            rot += d_rot * k
            sxm *= 1 + (mx - 1) * k
            sym *= 1 + (my - 1) * k
        elif self._settle > 0:
            te = _SETTLE_DUR - self._settle
            damp = math.exp(-te * 9) * math.sin(te * 38)    # 反应收尾衰减正弦回弹
            sym *= 1 + 0.09 * damp
            sxm *= 1 - 0.09 * damp

        if self._sleep_e > 0.0:
            slow = math.sin(self._t * _SLEEP_BREATH_HZ)
            oy += self._sleep_e * (_SLEEP_SINK * bh + slow * bh * 0.025)
            sxm *= 1 - 0.05 * self._sleep_e * slow
            sym *= 1 + 0.05 * self._sleep_e * slow

        if self._activity is not None:
            a_ox, a_oy, a_rot, a_sx, a_sy = self._activity_body_transform(bw, bh)
            ox += a_ox
            oy += a_oy
            rot += a_rot
            sxm *= a_sx
            sym *= a_sy

        if self._shy_e > 0.0:
            # 害羞侧身缩一点
            rot += self._shy_e * 7
            sxm *= 1 - 0.04 * self._shy_e
            oy += self._shy_e * bh * 0.02
        calm = self._calm_e  # 演出期间环境拟态全部让位
        if self._squeeze_e > 0.0 and calm > 0.0:
            # 被内存挤扁
            k = self._squeeze_e * calm
            sym *= 1 - 0.22 * k
            sxm *= 1 + 0.16 * k
            oy += bh * 0.1 * k
        if self._hot_e > 0.0 and calm > 0.0:
            # 热得发蔫 缓慢晃
            k = self._hot_e * calm
            oy += bh * 0.02 * k
            rot += math.sin(self._t * 1.1) * 2.0 * k
        if self._lowbatt_e > 0.0 and calm > 0.0:
            # 没电焦躁 高频小颤
            ox += math.sin(self._t * 23) * bw * 0.008 * self._lowbatt_e * calm
        if self._weather == "melt" and self._weather_e > 0.0 and calm > 0.0:
            # 热到化了 摊下去
            k = self._weather_e * calm
            sym *= 1 - 0.14 * k
            sxm *= 1 + 0.10 * k
            oy += bh * 0.07 * k

        head_y = cy + oy
        painter.save()
        painter.translate(cx + ox, head_y)
        painter.rotate(rot)
        painter.scale(sxm, sym)
        self._draw_body(painter, bw, bh)
        self._draw_eyes(painter, bw, bh)
        self._draw_mouth(painter, bw, bh)
        self._draw_costume_worn(painter, bw, bh)
        if self._shy_e > 0.01:
            adornments.draw_shy_hands(painter, bw, bh, self._shy_e, self._t)
        if self._squeeze_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_squeeze_marks(painter, bw, bh, self._squeeze_e * self._calm_e, self._t)
        if self._hot_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_hot(painter, bw, bh, self._hot_e * self._calm_e, self._t)
        if self._blanket_e > 0.01:
            adornments.draw_blanket(painter, bw, bh, self._blanket_e, self._t)
        if self._lowbatt_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_lowbatt(painter, bw, bh, self._lowbatt_e * self._calm_e, self._t)
        if self._weather_e > 0.01 and self._calm_e > 0.05:
            adornments.draw_weather(painter, bw, bh, self._weather, self._weather_e * self._calm_e, self._t)
        if think_gate > 0.01 and not self._react and not self._worn_costume and self._shy_e < 0.3:
            self._draw_think_hand(painter, bw, bh, think_gate)
        if self._lecturing:
            draw_pointer(painter, bw, bh, self._t)
        painter.restore()

        self._draw_costume_ambient(painter, cx, head_y, bw, bh)
        if self._cake_e > 0.01 or self._cake_smoke > 0.0:
            adornments.draw_cake(
                painter, cx, head_y, bw, bh,
                self._cake_e, self._cake_lit, self._cake_smoke, self._t,
            )
        if self._sleep_e > 0.01:
            self._draw_zzz(painter, cx, head_y, bw, bh, self._sleep_e)


        if self._expr == "confused":
            self._draw_question(painter, cx, head_y, bw, bh)
        if self._dream_bubbles:
            self._draw_dream(painter, cx, head_y, bw, bh)
        if self._react:
            rname, relapsed, rdur = self._react
            self._draw_react_fx(painter, rname, min(relapsed / rdur, 1.0), cx, head_y, bw, bh)
