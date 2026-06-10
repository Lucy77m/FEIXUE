# author: bdth
# email: 2074055628@qq.com
# 桌宠执行操作前弹出的「执行/不执行」确认小面板组件

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop_pet.pet.fx import make_floating, place_beside_pet

_STYLE = """
* { font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif; }
#card {
    background: rgba(252, 250, 246, 0.975);
    border-radius: 18px; border: 1px solid #ece6dc;
}
#title { color: #9a8cff; font-size: 12px; font-weight: 600; }
#msg { color: #3c3c46; font-size: 14px; }
QPushButton#yes {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c6cff, stop:1 #22d3ee);
    color: white; border: none; border-radius: 11px; padding: 9px 24px; font-size: 14px; font-weight: 600;
}
QPushButton#yes:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8e80ff, stop:1 #4fe3f5); }
QPushButton#no {
    background: #f1ede5; color: #8a8a98; border: none; border-radius: 11px; padding: 9px 22px; font-size: 14px;
}
QPushButton#no:hover { background: #e7e0d6; color: #5a5a66; }
"""


class ConfirmBox(QWidget):
    answered = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        card = QFrame(objectName="card")
        card.setStyleSheet(_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setColor(QColor(124, 108, 255, 95))
        shadow.setOffset(0, 9)
        card.setGraphicsEffect(shadow)

        title = QLabel("要我做这个吗？", objectName="title")
        self._msg = QLabel(objectName="msg")
        self._msg.setWordWrap(True)
        self._msg.setMaximumWidth(300)

        self._yes = QPushButton("执行", objectName="yes")
        self._no = QPushButton("不执行", objectName="no")
        for b in (self._yes, self._no):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yes.clicked.connect(lambda: self._answer(True))
        self._no.clicked.connect(lambda: self._answer(False))

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        row.addWidget(self._no)
        row.addWidget(self._yes)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(12)
        inner.addWidget(title)
        inner.addWidget(self._msg)
        inner.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.addWidget(card)

    def ask(self, action: str, pet: QWidget, screen) -> None:
        """贴宠物右边弹出来问一句，用户点完发 answered 信号。"""
        # 截到 240 字防止一长串塞爆面板；模型偶尔吐空动作 → 兜底文案别让用户对着空白点
        self._msg.setText((action or "").strip()[:240] or "(没说要做什么)")
        self.adjustSize()
        place_beside_pet(self, pet, screen, prefer="right")
        self.show()
        self.raise_()

    def is_open(self) -> bool:
        return self.isVisible()

    def follow(self, pet: QWidget, screen) -> None:
        """宠物被拖走时跟着重新贴边 —— 没显示就别白算位置。"""
        if self.isVisible():
            place_beside_pet(self, pet, screen, prefer="right")

    def close_box(self) -> None:
        self.hide()

    def _answer(self, ok: bool) -> None:
        self.hide()
        self.answered.emit(ok)
