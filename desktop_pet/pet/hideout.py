# author: bdth
# email: 2074055628@qq.com
# 桌宠贴边躲藏行为:藏到屏幕边缘后潜伏、探头、张望、再缩回的状态机

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, QRect

from desktop_pet.pet.behaviors.easing import ease_in, ease_out
from desktop_pet.pet.character import BLOB_HALF_H, BLOB_HALF_W

_EDGE_SNAP = 48.0  # 离边 48px 内才触发贴边——拖到差不多就吸过去，不用精准怼到边
_HIDE_SHOW = 14.0  # 藏好后仍露出来的那一丢丢，纯藏会让人以为掉没了
_PEEK_SHOW = 1.45  # 探头露出量按 blob 半身的倍数算，跟着角色大小走

_TUCK_DUR = 0.5
_PEEK_OUT_DUR = 0.42
_PEEK_IN_DUR = 0.6  # 缩回比探头慢一点，依依不舍那感觉
_PEEK_HOLD = (1.0, 2.4)  # 探头后停留时长，随机取免得机械
_LURK_GAP = (3.5, 8.0)  # 两次探头之间的潜伏间隔，也随机
_GLANCE_OPEN = 0.85  # 探头时眼睛朝屏内瞟的幅度，正值朝右
_SCAN_FRAC = 0.6  # 张望/回瞟用的折扣系数——比初次探头收着点

_TUCK, _LURK, _OUT, _HOLD, _IN, _SHOW = "tuck", "lurk", "out", "hold", "in", "show"


class Hideout:
    def __init__(self, edge: str, screen: QRect, drop: QPoint, win_w: int, win_h: int) -> None:
        self.edge = edge
        self._from = QPoint(drop)
        self._hidden, self._peek, self._shown, self._open_dir = self._anchors(edge, screen, drop, win_w, win_h)
        self._out_target = self._peek
        self._phase = _TUCK
        self._t = 0.0
        self._wait = 0.0
        self._hold = 0.0
        self._scanned = False
        self._held_out = False
        self._pending_glance: float | None = None

    @staticmethod
    def edge_for(screen: QRect, geo: QRect) -> str | None:
        """松手位置离哪条边最近就贴哪边，超过 _EDGE_SNAP 返回 None（不贴）。只认左/右/上——底边留给任务栏，不藏。"""
        cx, cy = geo.center().x(), geo.center().y()
        dists = {
            "left": (cx - BLOB_HALF_W) - screen.left(),
            "right": (screen.left() + screen.width()) - (cx + BLOB_HALF_W),
            "top": (cy - BLOB_HALF_H) - screen.top(),
        }
        edge = min(dists, key=dists.get)
        return edge if dists[edge] <= _EDGE_SNAP else None

    @staticmethod
    def _anchors(edge: str, screen: QRect, drop: QPoint, win_w: int, win_h: int):
        """算出三个落点：藏好(hidden)、探头(peek)、整只露出(shown)，外加瞟的方向。
        坐标是窗口左上角——所以处处要从中心减掉 win/2±半身把窗口怼到边上贴齐。"""
        sx0, sy0 = screen.left(), screen.top()
        sx1, sy1 = sx0 + screen.width(), sy0 + screen.height()
        hw, hh = BLOB_HALF_W, BLOB_HALF_H
        if edge in ("left", "right"):
            y = max(sy0, min(sy1 - win_h, drop.y()))  # 夹住别让窗口探出屏外
            if edge == "left":
                hx = sx0 + _HIDE_SHOW - (win_w / 2 + hw)
                px = sx0 + hw * _PEEK_SHOW - (win_w / 2 + hw)
                shx = sx0
                open_dir = _GLANCE_OPEN
            else:
                hx = sx1 - _HIDE_SHOW - (win_w / 2 - hw)
                px = sx1 - hw * _PEEK_SHOW - (win_w / 2 - hw)
                shx = sx1 - win_w
                open_dir = -_GLANCE_OPEN  # 贴右边时朝左瞟，所以取负
            return QPoint(round(hx), y), QPoint(round(px), y), QPoint(round(shx), y), open_dir
        # 到这就是贴顶边：横向夹一下，竖向往下探
        x = max(sx0, min(sx1 - win_w, drop.x()))
        hy = sy0 + _HIDE_SHOW - (win_h / 2 + hh)
        py = sy0 + hh * _PEEK_SHOW - (win_h / 2 + hh)
        shy = sy0
        return QPoint(x, round(hy)), QPoint(x, round(py)), QPoint(x, round(shy)), _GLANCE_OPEN * _SCAN_FRAC

    def poke(self) -> None:
        """戳一下让它探头：只在潜伏/正缩回时响应，正探着/已张望中就不打断。"""
        if self._phase in (_LURK, _IN):
            self._out_target = self._peek
            self._phase = _OUT
            self._t = 0.0
            self._pending_glance = self._open_dir

    def hold_out(self, on: bool) -> None:
        """按住不放——整只露出来停那不动（如鼠标悬停/拖拽时）。松开才缩回。
        on 时目标换成 shown 整露；正在 HOLD 就直接跳 SHOW，省掉重新探一遍。"""
        self._held_out = on
        if on:
            self._out_target = self._shown
            if self._phase in (_TUCK, _LURK, _IN):
                self._phase = _OUT
                self._t = 0.0
                self._pending_glance = self._open_dir
            elif self._phase == _HOLD:
                self._phase = _SHOW
        elif self._phase == _SHOW:  # 松开时只有正 SHOW 着才需要缩，其它相位本来就会自己走完
            self._phase = _IN
            self._t = 0.0

    def advance(self, dt: float) -> tuple[QPoint, float | None]:
        """每帧推一步状态机。相位环 tuck→lurk→out→hold→in→lurk…，hold_out 时改走 out→show，松手再 in。"""
        glance = self._pending_glance  # poke/hold_out 攒下的瞟，本帧消费掉
        self._pending_glance = None
        self._t += dt
        if self._phase == _TUCK:
            pos = self._lerp(self._from, self._hidden, ease_out(min(self._t / _TUCK_DUR, 1.0)))
            if self._t >= _TUCK_DUR:
                self._enter_lurk()
            return pos, glance
        if self._phase == _LURK:
            if self._t >= self._wait:
                self._phase = _OUT
                self._t = 0.0
                glance = self._open_dir
            return QPoint(self._hidden), glance
        if self._phase == _OUT:
            pos = self._lerp(self._hidden, self._out_target, ease_out(min(self._t / _PEEK_OUT_DUR, 1.0)))
            if self._t >= _PEEK_OUT_DUR:
                if self._held_out:
                    self._phase = _SHOW
                else:
                    self._phase = _HOLD
                    self._t = 0.0
                    self._hold = random.uniform(*_PEEK_HOLD)
                    self._scanned = False
            return pos, glance
        if self._phase == _SHOW:
            return QPoint(self._out_target), glance
        if self._phase == _HOLD:
            # 停留过半时往反方向回瞟一眼——左右张望那味儿，每段 hold 只瞟一次
            if not self._scanned and self._t >= self._hold * 0.5:
                self._scanned = True
                glance = -self._open_dir * _SCAN_FRAC
            if self._t >= self._hold:
                self._phase = _IN
                self._t = 0.0
            return QPoint(self._out_target), glance
        pos = self._lerp(self._out_target, self._hidden, ease_in(min(self._t / _PEEK_IN_DUR, 1.0)))
        if self._t >= _PEEK_IN_DUR:
            self._enter_lurk()
        return pos, glance

    def _enter_lurk(self) -> None:
        """回潜伏并重摇下次探头的等待时间——藏好/缩回完都走这。"""
        self._phase = _LURK
        self._t = 0.0
        self._wait = random.uniform(*_LURK_GAP)

    @staticmethod
    def _lerp(a: QPoint, b: QPoint, t: float) -> QPoint:
        return QPoint(round(a.x() + (b.x() - a.x()) * t), round(a.y() + (b.y() - a.y()) * t))
