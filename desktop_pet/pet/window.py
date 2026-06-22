# 桌宠主窗口 无边框悬浮窗 渲染 blob 处理拖拽点击悬停 入场动画和贴边躲藏

from __future__ import annotations

import random
import time
from collections import deque

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from desktop_pet import i18n
from desktop_pet.emotion.tags import (
    TAG_COSTUME as _TAG_COSTUME,
    TAG_EXPRESSION as _TAG_EXPRESSION,
    TAG_INTENSITY as _TAG_INTENSITY,
    TAG_VA as _TAG_VA,
)
from desktop_pet.pet.behavior import selector
from desktop_pet.pet.behaviors import Category
from desktop_pet.pet.blob_defs import BLOB_HALF_W
from desktop_pet.pet.character import BlobPet
from desktop_pet.pet.entrance import Entrance
from desktop_pet.pet.fx import make_floating, raise_topmost
from desktop_pet.pet.hideout import Hideout
from desktop_pet.pet.portal_transit import PortalTransit
from desktop_pet.pet.wormhole import Wormhole

_FPS = 60
_SPRITE_FPS = 30
_CLICK_SLOP = 5
_HOVER_COOLDOWN = 4.0

_CLICK_REACTIONS = (
    "perk_up", "nod", "bounce", "peek", "wobble", "pop", "boing", "happy_wiggle",
)
_GRUDGE_REACTIONS = ("shake", "recoil", "droop", "deflate")  # 记仇期间不给好脸
_CLICK_COOLDOWN = 2.5
_COSTUME_CHANCE = 0.25
_TOSS_SPEED = 650.0  # 甩出判定 像素每秒
_TOSS_MAX = 2600.0
_TOSS_GRAVITY = 3200.0
_TOSS_BOUNCE = 0.48
_TOSS_HURT = 1500.0  # 落地冲击超过这个算摔疼
_SPRITE_WANDER_GAP = (16.0, 32.0)
_SPRITE_WANDER_DIST = (48, 120)
_SPRITE_WANDER_SPEED = 72.0
_SPRITE_WANDER_EDGE = 12
_ATTENTION_COOLDOWN = 5.0
_BASE_WINDOW_SIZE = (250, 220)
PET_SCALE_PRESETS = (75, 100, 125, 150)


class PetWindow(QWidget):
    clicked = Signal()
    moved = Signal()
    grabbed = Signal()
    hid = Signal()
    wants_travel = Signal()
    context_requested = Signal(QPoint)
    fed = Signal(list)
    offered = Signal(object)
    tossed = Signal(float)
    tickled = Signal()
    scale_changed = Signal(int)

    def __init__(self, pet_skin: str = "blob", pet_scale: int = 100) -> None:
        super().__init__()
        make_floating(self)
        self._pet_scale = self._normalize_scale(pet_scale)
        self.resize(*self._scaled_window_size(self._pet_scale))
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._press_pos = QPoint()
        self._drag_offset = QPoint()
        self._is_dragging = False
        self._last_hover = 0.0
        self._last_click = 0.0
        self._click_times: list[float] = []  # 连点窗口 挠痒判定
        self._long_fired = False
        self._long_timer = QTimer(self)
        self._long_timer.setSingleShot(True)
        self._long_timer.timeout.connect(self._on_long_press)
        self._drag_hist: deque[tuple[float, QPoint]] = deque(maxlen=6)  # 甩出去的速度采样
        self._toss_timer = QTimer(self)
        self._toss_timer.timeout.connect(self._tick_toss)
        self._toss_vx = 0.0
        self._toss_vy = 0.0
        self._toss_impacted = False
        self._grudge_until = 0.0
        self._sprite_wander_left = random.uniform(*_SPRITE_WANDER_GAP)
        self._sprite_walk_target: QPoint | None = None
        self._sprite_walk_dir = 0
        self._last_attention = 0.0
        self._work_item: dict | None = None

        self._blob = BlobPet(pet_skin)
        self._last = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        fps = _SPRITE_FPS if self._blob.has_sprite_skin else _FPS
        self._timer.start(1000 // fps)

        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(lambda: self.isVisible() and raise_topmost(self))
        self._topmost_timer.start(1500)

        self._entrance: Entrance | None = None
        self._entrance_t = 0.0
        self._rest_pos = QPoint()
        self._hideout: Hideout | None = None
        self._wormhole: Wormhole | None = None
        self._wormhole_t = 0.0
        self._portal: PortalTransit | None = None
        self._portal_t = 0.0
        self._portal_midpoint_called = False
        self._portal_midpoint = None
        self._portal_finished = None
        self._portal_serial = 0
        # 上层注入的整段说话查询 藏边时据此整只露出
        self._is_speaking = lambda: False

    def set_work_item(self, kind: str, label: str, stage: str) -> None:
        self._work_item = {"kind": kind, "label": label, "stage": stage}
        self.update()

    def clear_work_item(self) -> None:
        if self._work_item is not None:
            self._work_item = None
            self.update()

    @staticmethod
    def _normalize_scale(scale: int) -> int:
        try:
            value = int(scale)
        except (TypeError, ValueError):
            return 100
        return value if value in PET_SCALE_PRESETS else 100

    @staticmethod
    def _scaled_window_size(scale: int) -> tuple[int, int]:
        factor = scale / 100.0
        return tuple(round(value * factor) for value in _BASE_WINDOW_SIZE)

    @property
    def pet_scale(self) -> int:
        return self._pet_scale

    def set_pet_scale(self, scale: int) -> bool:
        scale = self._normalize_scale(scale)
        if scale == self._pet_scale:
            return False
        foot = self.below_blob()
        self._cancel_sprite_walk()
        self._end_toss()
        self._end_hide()
        self._end_travel()
        self._pet_scale = scale
        self.resize(*self._scaled_window_size(scale))
        new_foot = self._blob.visual_anchors(self.width(), self.height())["foot"].toPoint()
        self.move(foot - new_foot)
        self.update()
        self.moved.emit()
        self.scale_changed.emit(scale)
        return True

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            direction = 1 if event.angleDelta().y() > 0 else -1
            index = PET_SCALE_PRESETS.index(self._pet_scale)
            target = max(0, min(index + direction, len(PET_SCALE_PRESETS) - 1))
            self.set_pet_scale(PET_SCALE_PRESETS[target])
            event.accept()
            return
        super().wheelEvent(event)

    def below_blob(self) -> QPoint:
        """blob 正下方的全局坐标"""
        geo = self.frameGeometry()
        anchor = self._blob.visual_anchors(self.width(), self.height())["foot"].toPoint()
        return geo.topLeft() + anchor

    def head_anchor(self) -> QPoint:
        """头顶偏右的锚点"""
        geo = self.frameGeometry()
        anchor = self._blob.visual_anchors(self.width(), self.height())["head"].toPoint()
        return geo.topLeft() + anchor

    def head_top(self) -> QPoint:
        geo = self.frameGeometry()
        anchor = self._blob.visual_anchors(self.width(), self.height())["head_top"].toPoint()
        return geo.topLeft() + anchor

    def bind_speaking(self, fn) -> None:
        """注入是否正在说话的查询函数"""
        self._is_speaking = fn

    def set_state(self, state: str) -> None:
        if state == "speaking":
            self._blob.set_talking(True)
        elif state == "rest":
            self._blob.set_talking(False)

    def set_busy(self, busy: bool) -> None:
        self._blob.set_busy(busy)

    def set_lecturing(self, on: bool) -> None:
        self._blob.set_lecturing(on)

    def note_think_step(self, label: str) -> None:
        """从思考步骤标签反推类型喂给 blob"""
        if label == i18n.thinking_label():
            kind = "new_turn"
        elif " · " in label or i18n.is_noarg_tool_label(label):  # 带间隔点的是工具标签 无参工具另走 i18n 判定
            kind = "tool"
        else:
            kind = "inner"
        self._blob.on_think_step(kind)

    def set_think_energy(self, arousal: float) -> None:
        self._blob.set_think_energy(arousal)

    def fall_asleep(self) -> None:
        self._blob.fall_asleep()

    def wake(self) -> None:
        self._blob.wake()

    @property
    def is_asleep(self) -> bool:
        return self._blob.is_asleep

    @property
    def is_catnapping(self) -> bool:
        return self._blob.is_catnapping

    def summon_front(self) -> None:
        """召回眼前 掐掉动画再叫醒置顶"""
        self._end_hide()
        self._end_travel()
        self._blob.wake()
        raise_topmost(self)

    def celebrate(self) -> None:
        self._blob.celebrate()

    def slump(self) -> None:
        self._blob.slump()

    def perform(self, name: str) -> bool:
        self._cancel_sprite_walk()
        return self._blob.perform(name)

    def react(self, name: str, intensity: float = 1.0) -> None:
        self._blob.react(name, intensity)

    def set_expression(self, name: str) -> None:
        self._blob.set_expression(name)

    def set_shy(self, on: bool) -> None:
        self._blob.set_shy(on)

    def set_hot(self, on: bool) -> None:
        self._blob.set_hot(on)

    def set_squeeze(self, on: bool) -> None:
        self._blob.set_squeeze(on)

    def set_low_batt(self, on: bool) -> None:
        self._blob.set_low_batt(on)

    def set_blanket(self, on: bool) -> None:
        self._blob.set_blanket(on)

    def set_cake(self, on: bool) -> None:
        self._blob.set_cake(on)

    def blow_cake(self) -> bool:
        return self._blob.blow_cake()

    def bind_activity_done(self, callback) -> None:
        self._blob.on_activity_done = callback

    def set_weather(self, kind: str) -> None:
        self._blob.set_weather(kind)

    @property
    def is_reacting(self) -> bool:
        return self._blob.is_reacting

    def clear_pending(self) -> None:
        self._blob.clear_pending()

    def yield_performance(self) -> None:
        self._blob.yield_performance()

    def express(self, tag: str) -> None:
        """情绪 tag 落成表情 反应小品和偶尔换装"""
        self._blob.set_expression(_TAG_EXPRESSION.get(tag, "neutral"))
        name = selector.select(Category.REACTION, mood=_TAG_VA.get(tag))
        if name:
            self._blob.react(name, _TAG_INTENSITY.get(tag, 1.0))
        costume = _TAG_COSTUME.get(tag)
        # 换装按概率触发 没抽中清掉旧装
        self._blob.set_costume(
            costume if costume and random.random() < _COSTUME_CHANCE else None
        )

    def play_entrance(self, kind: str, rest_pos: QPoint, screen) -> None:
        self._cancel_sprite_walk()
        self._wormhole = None  # 入场前清掉可能在跑的虫洞 别让两个动画同占导致 blob 卡在缩 0
        self._rest_pos = QPoint(rest_pos)
        self._entrance = Entrance(kind, screen, rest_pos, self.width(), self.height())
        self._entrance_t = 0.0
        pos, opacity = self._entrance.window_state(0.0)
        self.move(pos.toPoint())
        self.setWindowOpacity(opacity)

    def start_wormhole(self) -> bool:
        """跳虫洞传送到对侧随机落点 空闲时才启动"""
        if (self._entrance is not None or self._hideout is not None or self._wormhole is not None
                or self._portal is not None
                or self._is_dragging or self._blob.in_activity or self._blob.is_reacting):
            return False
        to_pos = self._pick_wander_target()
        if to_pos is None:
            return False
        self._cancel_sprite_walk()
        frm = self.frameGeometry().topLeft()
        self._rest_pos = QPoint(to_pos)
        self._wormhole = Wormhole(QPoint(frm), QPoint(to_pos), self.width(), self.height())
        self._wormhole_t = 0.0
        return True

    def begin_portal_departure(self, payload: dict, midpoint=None, finished=None) -> bool:
        return self._begin_portal("departure", payload, midpoint, finished)

    def begin_portal_arrival(self, payload: dict, finished=None) -> bool:
        return self._begin_portal("arrival", payload, None, finished)

    def _begin_portal(self, direction: str, payload: dict, midpoint, finished) -> bool:
        if (self._entrance is not None or self._hideout is not None or self._wormhole is not None
                or self._portal is not None or self._is_dragging or self._toss_timer.isActive()
                or self._blob.in_activity or self._blob.is_reacting):
            return False
        self._cancel_sprite_walk()
        self._portal_serial += 1
        self._portal = PortalTransit(direction)
        self._portal_t = 0.0
        self._portal_midpoint_called = False
        self._portal_midpoint = midpoint
        self._portal_finished = finished
        self.set_work_item(
            str(payload.get("kind", "file")), str(payload.get("label", "")),
            str(payload.get("stage", "received")),
        )
        if direction == "arrival":
            self.show()
            self.raise_()
        self.update()
        return True

    def cancel_portal(self, clear_payload: bool = False) -> None:
        self._portal_serial += 1
        self._portal = None
        self._portal_t = 0.0
        self._portal_midpoint = None
        self._portal_finished = None
        self._portal_midpoint_called = False
        if clear_payload:
            self.clear_work_item()
        self.update()

    def _pick_wander_target(self) -> QPoint | None:
        """挑落点 多屏时偶尔窜去隔壁屏"""
        screen = self.screen()
        if screen is None:
            return None
        from PySide6.QtWidgets import QApplication
        others = [s for s in QApplication.screens() if s is not screen]
        if others and random.random() < 0.3:
            t = random.choice(others).availableGeometry()
            w, h = self.width(), self.height()
            if t.width() > w and t.height() > h:
                return QPoint(random.randint(t.left(), t.right() - w),
                              random.randint(t.top(), t.bottom() - h))
        avail = screen.availableGeometry()
        w, h = self.width(), self.height()
        if avail.width() <= w or avail.height() <= h:
            return None
        mid = avail.center().x()
        left_hi = avail.left() + avail.width() // 2 - w
        right_lo = avail.left() + avail.width() // 2
        if self.frameGeometry().center().x() >= mid:
            x = random.randint(avail.left(), max(avail.left(), left_hi))
        else:
            x = random.randint(min(right_lo, avail.right() - w), avail.right() - w)
        y = random.randint(avail.top(), avail.bottom() - h)
        return QPoint(x, y)

    def _end_travel(self) -> None:
        self.cancel_portal()
        if self._wormhole is not None:
            self._wormhole = None
            self.move(self._rest_pos)

    def _reset_sprite_wander(self) -> None:
        self._sprite_wander_left = random.uniform(*_SPRITE_WANDER_GAP)

    def _cancel_sprite_walk(self) -> None:
        self._sprite_walk_target = None
        self._sprite_walk_dir = 0
        self._blob.set_sprite_walking(False)
        self._reset_sprite_wander()

    def _sprite_wander_allowed(self) -> bool:
        return (
            self._blob.has_sprite_skin
            and self._blob.can_sprite_wander
            and self.isVisible()
            and self._entrance is None
            and self._hideout is None
            and self._wormhole is None
            and self._portal is None
            and not self._is_dragging
            and not self._toss_timer.isActive()
            and not self._is_speaking()
            and self.windowOpacity() >= 1.0
        )

    def _advance_sprite_wander(self, dt: float) -> bool:
        if not self._blob.has_sprite_skin:
            return False
        if self._sprite_walk_target is not None:
            if not self._sprite_wander_allowed():
                self._cancel_sprite_walk()
                return True
            pos = self.frameGeometry().topLeft()
            dx = self._sprite_walk_target.x() - pos.x()
            if dx == 0:
                self.move(self._sprite_walk_target)
                self._sprite_walk_target = None
                self._sprite_walk_dir = 0
                self._blob.set_sprite_walking(False)
                self._reset_sprite_wander()
                self.moved.emit()
                return True
            step = max(1, int(_SPRITE_WANDER_SPEED * dt))
            move_x = min(step, abs(dx)) * (1 if dx > 0 else -1)
            self.move(pos + QPoint(move_x, 0))
            self.moved.emit()
            return True
        if not self._sprite_wander_allowed():
            self._reset_sprite_wander()
            return False
        self._sprite_wander_left -= dt
        if self._sprite_wander_left <= 0.0:
            return self._start_sprite_wander()
        return False

    def _start_sprite_wander(self) -> bool:
        screen = self.screen()
        if screen is None:
            self._reset_sprite_wander()
            return False
        avail = screen.availableGeometry()
        pos = self.frameGeometry().topLeft()
        min_dist, max_dist = _SPRITE_WANDER_DIST
        min_x = avail.left() + _SPRITE_WANDER_EDGE
        max_x = avail.right() - self.width() - _SPRITE_WANDER_EDGE
        left_space = pos.x() - min_x
        right_space = max_x - pos.x()
        directions = []
        if left_space >= min_dist:
            directions.append(-1)
        if right_space >= min_dist:
            directions.append(1)
        if not directions:
            self._reset_sprite_wander()
            return False
        direction = random.choice(directions)
        space = left_space if direction < 0 else right_space
        dist = random.randint(min_dist, min(max_dist, int(space)))
        self._sprite_walk_dir = direction
        self._sprite_walk_target = QPoint(pos.x() + direction * dist, pos.y())
        self._blob.set_sprite_walking(True, direction)
        return True

    def _tick(self) -> None:
        """每帧驱动 先推进 blob 再按三种动画接管窗口位置"""
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        repaint_needed = self._blob.advance(dt)
        if self._blob.take_travel_request():
            self.wants_travel.emit()
        # 三种位移动画互斥 入场优先级最高藏边最低
        if self._entrance is not None:
            self._advance_entrance(dt)
            repaint_needed = True
        elif self._portal is not None:
            self._advance_portal(dt)
            repaint_needed = True
        elif self._wormhole is not None:
            self._advance_wormhole(dt)
            repaint_needed = True
        elif self._hideout is not None:
            # 整段话期间一直露出 说完才缩回
            self._hideout.hold_out(self._is_speaking())
            pos, glance = self._hideout.advance(dt)
            self.move(pos)
            self.moved.emit()
            repaint_needed = True
            if glance is not None:
                self._blob.look_at(glance)
        elif self.windowOpacity() < 1.0:
            # 自愈 没有入场或虫洞在跑 窗口就该满不透明
            # 防动画被打断留下 opacity 小于1 让桌宠凭空消失
            self.setWindowOpacity(1.0)
            repaint_needed = True
        if self._advance_sprite_wander(dt):
            repaint_needed = True
        if repaint_needed:
            self.update()

    def _advance_entrance(self, dt: float) -> None:
        """推进入场动画 到点收尾归位"""
        self._entrance_t += dt
        if self._entrance_t >= self._entrance.duration:
            self._entrance = None
            self.setWindowOpacity(1.0)
            self.move(self._rest_pos)
            return
        pos, opacity = self._entrance.window_state(self._entrance_t / self._entrance.duration)
        self.move(pos.toPoint())
        self.setWindowOpacity(opacity)
        self.moved.emit()

    def _advance_wormhole(self, dt: float) -> None:
        """推进虫洞传送 到点硬拍到落点"""
        self._wormhole_t += dt
        if self._wormhole_t >= self._wormhole.duration:
            self._wormhole = None
            self.move(self._rest_pos)
            self.moved.emit()
            return
        p = self._wormhole_t / self._wormhole.duration
        self.move(self._wormhole.window_state(p).toPoint())
        self.moved.emit()

    def _advance_portal(self, dt: float) -> None:
        portal = self._portal
        if portal is None:
            return
        self._portal_t += dt
        progress = min(1.0, self._portal_t / portal.duration)
        if not self._portal_midpoint_called and progress >= portal.midpoint:
            self._portal_midpoint_called = True
            callback = self._portal_midpoint
            if callback is not None:
                try:
                    callback()
                except Exception:
                    pass
        if progress < 1.0:
            return
        callback = self._portal_finished
        self._portal = None
        self._portal_midpoint = None
        self._portal_finished = None
        self._portal_midpoint_called = False
        if callback is not None:
            try:
                callback()
            except Exception:
                pass

    def paintEvent(self, event: QPaintEvent) -> None:
        # 虫洞入场各自带道具形变 普通态直接画 blob
        painter = QPainter(self)
        if self._portal is not None:
            w, h = self.width(), self.height()
            progress = min(self._portal_t / self._portal.duration, 1.0)
            anchors = self._blob.visual_anchors(w, h)
            self._portal.draw(painter, anchors["foot"], progress, self._pet_scale / 100.0)
            sx, sy, oy, opacity = self._portal.transform(progress)
            if sx > 0.001 and sy > 0.001:
                center = anchors["foot"]
                painter.save()
                painter.setOpacity(opacity)
                painter.translate(center.x(), center.y() + oy)
                painter.scale(sx, sy)
                painter.translate(-center.x(), -center.y())
                self._blob.paint(painter, w, h)
                self._paint_work_item(painter)
                painter.restore()
            return
        if self._wormhole is not None:
            w, h = self.width(), self.height()
            p = min(self._wormhole_t / self._wormhole.duration, 1.0)
            self._wormhole.draw_props(painter, w, h, p)
            sx, sy, oy, rot = self._wormhole.blob_transform(p)
            if sx > 0.001 and sy > 0.001:  # 缩到接近 0 不画
                painter.save()
                painter.translate(w / 2, h / 2 + oy)
                painter.rotate(rot)
                painter.scale(sx, sy)
                painter.translate(-w / 2, -h / 2)
                self._blob.paint(painter, w, h)
                painter.restore()
            return
        if self._entrance is None:
            self._blob.paint(painter, self.width(), self.height())
            self._paint_work_item(painter)
            return
        w, h = self.width(), self.height()
        p = min(self._entrance_t / self._entrance.duration, 1.0)
        self._entrance.draw_props(painter, w, h, p)
        sx, sy, oy, rot = self._entrance.blob_transform(p)
        if sx > 0.001 and sy > 0.001:  # 同上 缩没了不画
            painter.save()
            painter.translate(w / 2, h / 2 + oy)
            painter.rotate(rot)
            painter.scale(sx, sy)
            painter.translate(-w / 2, -h / 2)
            self._blob.paint(painter, w, h)
            painter.restore()
        self._entrance.draw_overlay(painter, w, h, p)
        self._paint_work_item(painter)

    def _paint_work_item(self, painter: QPainter) -> None:
        if self._work_item is None:
            return
        scale = self._pet_scale / 100.0
        anchor = self._blob.visual_anchors(self.width(), self.height())["head"]
        size = max(22.0, 30.0 * scale)
        rect = QRectF(
            max(4.0, anchor.x() - size * 1.65),
            min(self.height() - size - 8.0, anchor.y() + size * 0.15),
            size,
            size * 0.82,
        )
        stage = self._work_item.get("stage", "working")
        stage_colors = {
            "received": QColor("#f2b84b"), "reading": QColor("#55a6d9"),
            "acting": QColor("#de765b"), "working": QColor("#8468d7"),
            "done": QColor("#45a96b"), "failed": QColor("#c85353"),
        }
        accent = stage_colors.get(stage, stage_colors["working"])
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(accent.darker(125), max(1.0, 1.4 * scale)))
        painter.setBrush(QColor(255, 253, 248, 242))
        painter.drawRoundedRect(rect, 3.0 * scale, 3.0 * scale)

        kind = self._work_item.get("kind", "file")
        inner = rect.adjusted(size * 0.20, size * 0.17, -size * 0.20, -size * 0.17)
        painter.setPen(QPen(accent, max(1.0, 1.8 * scale)))
        if kind == "image":
            painter.drawRect(inner)
            painter.drawLine(inner.bottomLeft(), inner.center())
            painter.drawLine(inner.center(), inner.bottomRight())
        elif kind == "url":
            radius = inner.height() * 0.28
            painter.drawEllipse(inner.center() - QPoint(int(radius), 0), radius, radius)
            painter.drawEllipse(inner.center() + QPoint(int(radius), 0), radius, radius)
            painter.drawLine(inner.center().x() - radius, inner.center().y(),
                             inner.center().x() + radius, inner.center().y())
        else:
            for fraction in (0.28, 0.52, 0.76):
                y = inner.top() + inner.height() * fraction
                painter.drawLine(inner.left(), y, inner.right(), y)
        dot = max(3.0, 4.5 * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(rect.right() - dot * 1.4, rect.top() - dot * 0.3, dot, dot))
        painter.restore()

    def enterEvent(self, event: QEnterEvent) -> None:
        # 鼠标进来逗一下 拖拽睡着藏边时不打扰 带冷却
        # 演小品时也不打扰 perk_up 是硬打断 一晃鼠标会把非点名小品整段掐掉
        if (not self._is_dragging and not self._blob.is_asleep and self._hideout is None
                and not self._blob.in_activity):
            now = time.perf_counter()
            if now - self._last_hover >= _HOVER_COOLDOWN:
                self._last_hover = now
                self._blob.react("perk_up")
        super().enterEvent(event)

    def dragEnterEvent(self, event) -> None:
        # 文件、链接和文字都可以交给它；Shift+文件保留旧的投喂入口。
        md = event.mimeData()
        if md.hasUrls() or md.hasText():
            event.acceptProposedAction()
            if self._hideout is None and not self._blob.is_asleep:
                self._blob.react("perk_up")
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.fed.emit(paths)
            else:
                self.offered.emit({"kind": "files", "paths": paths})
            return
        urls = [u.toString() for u in md.urls() if not u.isLocalFile()]
        if urls:
            event.acceptProposedAction()
            self.offered.emit({"kind": "url", "text": "\n".join(urls)})
            return
        if md.hasText() and md.text().strip():
            event.acceptProposedAction()
            text = md.text().strip()
            kind = "url" if text.startswith(("http://", "https://")) else "text"
            self.offered.emit({"kind": kind, "text": text})
            return
        event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._cancel_sprite_walk()
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._is_dragging = False
            self._long_fired = False
            self._end_toss()
            if self._hideout is None and not self._blob.is_asleep:
                self._long_timer.start(850)  # 长按抚摸判定
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
            event.accept()

    def _on_long_press(self) -> None:
        """按住不动够久 是在摸它"""
        if self._is_dragging or self._hideout is not None or self._blob.is_asleep:
            return
        self._long_fired = True
        self._blob.react("purr")
        from desktop_pet import somatic
        from desktop_pet.agent import prompts
        somatic.note(prompts.SOMA_PETTED)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            # 超过 _CLICK_SLOP 才算拖拽 进了拖拽就掐掉藏边和传送
            if not self._is_dragging and (pos - self._press_pos).manhattanLength() >= _CLICK_SLOP:
                self._is_dragging = True
                self._long_timer.stop()
                self.grabbed.emit()
                self._blob.set_dragging(True)
                self._end_hide()
                self._end_travel()
            self.move(pos - self._drag_offset)
            self._drag_hist.append((time.perf_counter(), pos))
            self.moved.emit()
            event.accept()
        elif self._hideout is None:
            self._track_cursor(event.globalPosition().toPoint())

    def _track_cursor(self, pos: QPoint) -> None:
        cx = self.frameGeometry().center().x()
        self._blob.look_at((pos.x() - cx) / (BLOB_HALF_W * 1.6))
        now = time.perf_counter()
        if now - self._last_attention >= _ATTENTION_COOLDOWN and self._blob.notice_attention():
            self._last_attention = now

    def _maybe_hide(self) -> None:
        """松手后贴边就缩进去躲起来"""
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        edge = Hideout.edge_for(avail, self.frameGeometry())
        if edge is not None:
            self._hideout = Hideout(edge, avail, self.frameGeometry().topLeft(), self.width(), self.height())
            self._blob.set_hidden(True)
            self.hid.emit()

    def _end_hide(self) -> None:
        if self._hideout is not None:
            self._hideout = None
            self._blob.set_hidden(False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # 松手四分支 甩出去抛飞 拖完落地弹并试贴边 藏着就戳露头 否则算点击
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_timer.stop()
            if self._is_dragging:
                self._is_dragging = False
                self._blob.set_dragging(False)
                vx, vy = self._release_velocity()
                self._drag_hist.clear()
                if (vx * vx + vy * vy) ** 0.5 >= _TOSS_SPEED:
                    self._start_toss(vx, vy)
                else:
                    self._blob.react("bounce")
                    self._maybe_hide()
            elif self._hideout is not None:
                self._hideout.poke()
            elif self._long_fired:
                pass  # 摸完了 不算点击
            elif (event.globalPosition().toPoint() - self._press_pos).manhattanLength() < _CLICK_SLOP:
                now = time.perf_counter()
                # 两秒内连点三下是挠痒 优先于普通点击反应
                self._click_times = [t for t in self._click_times if now - t < 2.0]
                self._click_times.append(now)
                if len(self._click_times) >= 3 and not self._blob.is_asleep:
                    self._click_times.clear()
                    self._last_click = now
                    self._blob.react("giggle")
                    self.tickled.emit()
                elif now - self._last_click >= _CLICK_COOLDOWN and not self._blob.is_asleep:
                    self._last_click = now
                    pool = _GRUDGE_REACTIONS if time.time() < self._grudge_until else _CLICK_REACTIONS
                    name = selector.select(Category.REACTION, candidates=pool)
                    if name:
                        self._blob.react(name)
                self.clicked.emit()
            event.accept()

    def _release_velocity(self) -> tuple[float, float]:
        """从最近拖动采样算松手速度 像素每秒"""
        if len(self._drag_hist) < 2:
            return 0.0, 0.0
        t0, p0 = self._drag_hist[0]
        t1, p1 = self._drag_hist[-1]
        dt = t1 - t0
        if dt < 0.005:
            return 0.0, 0.0
        return (p1.x() - p0.x()) / dt, (p1.y() - p0.y()) / dt

    def _start_toss(self, vx: float, vy: float) -> None:
        """被甩出去 抛体飞行"""
        self._cancel_sprite_walk()
        cap = _TOSS_MAX
        self._toss_vx = max(-cap, min(vx, cap))
        self._toss_vy = max(-cap, min(vy, cap))
        self._toss_impacted = False
        self._blob.set_dragging(True)  # 飞行中保持被拎的慌张样
        self._end_hide()
        self._end_travel()
        self._toss_timer.start(16)

    def _end_toss(self) -> None:
        if self._toss_timer.isActive():
            self._toss_timer.stop()
            self._blob.set_dragging(False)

    def _tick_toss(self) -> None:
        dt = 0.016
        scr = self.screen()
        if scr is None:
            self._end_toss()
            return
        avail = scr.availableGeometry()
        self._toss_vy += _TOSS_GRAVITY * dt
        self._toss_vx *= 0.998
        x = self.x() + self._toss_vx * dt
        y = self.y() + self._toss_vy * dt
        floor = avail.bottom() - self.height()
        impact = 0.0
        # 左右墙弹
        if x < avail.left():
            x = avail.left()
            self._toss_vx = abs(self._toss_vx) * _TOSS_BOUNCE
        elif x > avail.right() - self.width():
            x = avail.right() - self.width()
            self._toss_vx = -abs(self._toss_vx) * _TOSS_BOUNCE
        if y < avail.top():
            y = avail.top()
            self._toss_vy = abs(self._toss_vy) * _TOSS_BOUNCE
        elif y >= floor:
            y = floor
            impact = abs(self._toss_vy)
            self._toss_vy = -impact * _TOSS_BOUNCE
            self._toss_vx *= 0.7
            if not self._toss_impacted and impact >= _TOSS_HURT:
                # 摔疼了 记仇半小时
                self._toss_impacted = True
                self._grudge_until = time.time() + 1800
                self._toss_timer.stop()
                self.move(int(x), int(y))
                self._blob.set_dragging(False)
                self._blob.react("splat")
                self.tossed.emit(impact)
                self.moved.emit()
                return
            if impact < 320:  # 弹不动了 收
                self._toss_timer.stop()
                self._blob.set_dragging(False)
                self._blob.react("boing")
                self.moved.emit()
                return
        self.move(int(x), int(y))
        self.moved.emit()
