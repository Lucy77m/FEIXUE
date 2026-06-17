# author: bdth
# email: 2074055628@qq.com
# 操作提示浮层 agent借用鼠标键盘操作电脑时弹出 让用户清楚现在是它在动手 全权但透明

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from desktop_pet.pet.fx import make_floating, raise_topmost

_STYLE = """
* { font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif; }
#card {
    background: rgba(38, 34, 52, 0.94);
    border-radius: 16px; border: 1px solid rgba(124, 108, 255, 0.55);
}
#icon { font-size: 17px; }
#msg { color: #f3f0ff; font-size: 13px; font-weight: 600; }
#sub { color: #b9b2d8; font-size: 11px; }
"""


class ControlHint(QWidget):
    """顶部居中的小徽标 agent操作鼠标键盘期间显示 点击穿透 不抢焦点 对截图隐形"""

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        # 点击穿透 绝不挡住agent或用户要点的东西
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # 不抢焦点 尤其agent正在敲键盘时 浮层弹出不能截走输入焦点
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        card = QFrame(objectName="card")
        card.setStyleSheet(_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(124, 108, 255, 120))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        icon = QLabel("✋", objectName="icon")
        self._msg = QLabel("我正在帮你操作（鼠标 / 键盘）", objectName="msg")
        self._sub = QLabel("", objectName="sub")
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(self._msg)
        col.addWidget(self._sub)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 10, 18, 10)
        row.setSpacing(11)
        row.addWidget(icon)
        row.addLayout(col)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(card)

    def show_hint(self, detail: str, screen) -> None:
        """顶部居中弹出 detail 是当前动作 空则只显主文案"""
        detail = (detail or "").strip()[:60]
        self._sub.setText(detail)
        self._sub.setVisible(bool(detail))
        self.adjustSize()
        x = screen.left() + (screen.width() - self.width()) // 2
        y = screen.top() + 24
        self.move(int(x), int(y))
        if not self.isVisible():
            self.show()
        raise_topmost(self)

    def hide_hint(self) -> None:
        self.hide()
