# author: bdth
# email: 2074055628@qq.com
# 桌宠主窗口 无边框悬浮窗 渲染 blob 处理拖拽点击悬停 入场动画和贴边躲藏

from __future__ import annotations

import random
import time

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent, QPainter, QPaintEvent
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
from desktop_pet.pet.character import BLOB_HALF_H, BLOB_HALF_W, BlobPet
from desktop_pet.pet.entrance import Entrance
from desktop_pet.pet.fx import make_floating, raise_topmost
from desktop_pet.pet.hideout import Hideout
from desktop_pet.pet.wormhole import Wormhole

_FPS = 60
_CLICK_SLOP = 5
_HOVER_COOLDOWN = 4.0

_CLICK_REACTIONS = (
    "perk_up", "nod", "bounce", "peek", "wobble", "pop", "boing", "happy_wiggle",
)
_CLICK_COOLDOWN = 2.5
_COSTUME_CHANCE = 0.25


class PetWindow(QWidget):
    clicked = Signal()
    moved = Signal()
    grabbed = Signal()
    hid = Signal()
    wants_travel = Signal()
    context_requested = Signal(QPoint)
    fed = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.resize(250, 220)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._press_pos = QPoint()
        self._drag_offset = QPoint()
        self._is_dragging = False
        self._last_hover = 0.0
        self._last_click = 0.0

        self._blob = BlobPet()
        self._last = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // _FPS)

        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(lambda: raise_topmost(self))
        self._topmost_timer.start(1500)

        self._entrance: Entrance | None = None
        self._entrance_t = 0.0
        self._rest_pos = QPoint()
        self._hideout: Hideout | None = None
        self._wormhole: Wormhole | None = None
        self._wormhole_t = 0.0
        # 上层注入的整段说话查询 藏边时据此整只露出
        self._is_speaking = lambda: False

    def below_blob(self) -> QPoint:
        """blob 正下方的全局坐标"""
        geo = self.frameGeometry()
        return QPoint(geo.center().x(), geo.top() + self.height() // 2 + int(BLOB_HALF_H))

    def head_anchor(self) -> QPoint:
        """头顶偏右的锚点"""
        geo = self.frameGeometry()
        return QPoint(geo.center().x() + int(BLOB_HALF_W * 0.6), geo.center().y() - int(BLOB_HALF_H))

    def head_top(self) -> QPoint:
        geo = self.frameGeometry()
        return QPoint(geo.center().x(), geo.center().y() - int(BLOB_HALF_H))

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
        return self._blob.perform(name)

    def react(self, name: str, intensity: float = 1.0) -> None:
        self._blob.react(name, intensity)

    @property
    def is_reacting(self) -> bool:
        return self._blob.is_reacting

    def clear_pending(self) -> None:
        self._blob.clear_pending()

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
        self._rest_pos = QPoint(rest_pos)
        self._entrance = Entrance(kind, screen, rest_pos, self.width(), self.height())
        self._entrance_t = 0.0
        pos, opacity = self._entrance.window_state(0.0)
        self.move(pos.toPoint())
        self.setWindowOpacity(opacity)

    def start_wormhole(self) -> bool:
        """跳虫洞传送到对侧随机落点 空闲时才启动"""
        if (self._entrance is not None or self._hideout is not None or self._wormhole is not None
                or self._is_dragging or self._blob.in_activity or self._blob.is_reacting):
            return False
        to_pos = self._pick_wander_target()
        if to_pos is None:
            return False
        frm = self.frameGeometry().topLeft()
        self._rest_pos = QPoint(to_pos)
        self._wormhole = Wormhole(QPoint(frm), QPoint(to_pos), self.width(), self.height())
        self._wormhole_t = 0.0
        return True

    def _pick_wander_target(self) -> QPoint | None:
        """挑当前屏幕横向对侧的随机落点"""
        screen = self.screen()
        if screen is None:
            return None
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
        if self._wormhole is not None:
            self._wormhole = None
            self.move(self._rest_pos)

    def _tick(self) -> None:
        """每帧驱动 先推进 blob 再按三种动画接管窗口位置"""
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        self._blob.advance(dt)
        if self._blob.take_travel_request():
            self.wants_travel.emit()
        # 三种位移动画互斥 入场优先级最高藏边最低
        if self._entrance is not None:
            self._advance_entrance(dt)
        elif self._wormhole is not None:
            self._advance_wormhole(dt)
        elif self._hideout is not None:
            # 整段话期间一直露出 说完才缩回
            self._hideout.hold_out(self._is_speaking())
            pos, glance = self._hideout.advance(dt)
            self.move(pos)
            self.moved.emit()
            if glance is not None:
                self._blob.look_at(glance)
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

    def paintEvent(self, event: QPaintEvent) -> None:
        # 虫洞入场各自带道具形变 普通态直接画 blob
        painter = QPainter(self)
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

    def enterEvent(self, event: QEnterEvent) -> None:
        # 鼠标进来逗一下 拖拽睡着藏边时不打扰 带冷却
        if not self._is_dragging and not self._blob.is_asleep and self._hideout is None:
            now = time.perf_counter()
            if now - self._last_hover >= _HOVER_COOLDOWN:
                self._last_hover = now
                self._blob.react("perk_up")
        super().enterEvent(event)

    def dragEnterEvent(self, event) -> None:
        # 拖着文件靠近 张望期待
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
            if self._hideout is None and not self._blob.is_asleep:
                self._blob.react("perk_up")
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.fed.emit(paths)
            return
        event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._is_dragging = False
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            # 超过 _CLICK_SLOP 才算拖拽 进了拖拽就掐掉藏边和传送
            if not self._is_dragging and (pos - self._press_pos).manhattanLength() >= _CLICK_SLOP:
                self._is_dragging = True
                self.grabbed.emit()
                self._blob.set_dragging(True)
                self._end_hide()
                self._end_travel()
            self.move(pos - self._drag_offset)
            self.moved.emit()
            event.accept()
        elif self._hideout is None:
            self._track_cursor(event.globalPosition().toPoint())

    def _track_cursor(self, pos: QPoint) -> None:
        cx = self.frameGeometry().center().x()
        self._blob.look_at((pos.x() - cx) / (BLOB_HALF_W * 1.6))

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
        # 松手三分支 拖完落地弹并试贴边 藏着就戳露头 否则算点击
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                self._is_dragging = False
                self._blob.set_dragging(False)
                self._blob.react("bounce")
                self._maybe_hide()
            elif self._hideout is not None:
                self._hideout.poke()
            elif (event.globalPosition().toPoint() - self._press_pos).manhattanLength() < _CLICK_SLOP:
                now = time.perf_counter()
                # 反应有冷却 睡着不演 clicked 信号照发
                if now - self._last_click >= _CLICK_COOLDOWN and not self._blob.is_asleep:
                    self._last_click = now
                    name = selector.select(Category.REACTION, candidates=_CLICK_REACTIONS)
                    if name:
                        self._blob.react(name)
                self.clicked.emit()
            event.accept()
