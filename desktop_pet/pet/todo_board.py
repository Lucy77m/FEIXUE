# 任务清单浮窗 常驻显示当前 plan 的待办 卡片进度条和逐项状态

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from desktop_pet.pet.fx import make_floating, place_beside_pet

_ACCENT = "#6f5cf0"
_ACCENT_DK = "#4a3fce"
_FONT = "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
_MARGIN = 18
_CARDW = 324

_ICON_STATUS = {"●": "done", "→": "doing", "○": "todo"}

_STYLE = f"""
* {{ font-family: {_FONT}; }}
#todoCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #f7f5ff);
    border-radius: 16px;
    border: 1px solid #ecebf5;
}}
#todoTitle {{
    color: {_ACCENT}; font-size: 11px; font-weight: 800;
    letter-spacing: 2px; background: transparent;
}}
#todoCount {{
    color: #8b89a6; font-size: 11px; font-weight: 700;
    background: #f1eefe; border-radius: 8px; padding: 1px 8px;
}}
#todoBar {{ background: #ebe8f8; border: none; border-radius: 3px; }}
#todoBar::chunk {{
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8b7cff, stop:1 {_ACCENT});
}}
#rowDoing {{ background: rgba(111,92,240,0.09); border-radius: 9px; }}
#rowPlain {{ background: transparent; }}
QLabel {{ background: transparent; }}
"""


class TodoBoard(QWidget):
    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._card = QFrame(objectName="todoCard")
        self._card.setStyleSheet(_STYLE)
        self._card.setFixedWidth(_CARDW)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setColor(QColor(90, 80, 150, 70))
        shadow.setOffset(0, 8)
        self._card.setGraphicsEffect(shadow)

        col = QVBoxLayout(self._card)
        col.setContentsMargins(16, 13, 16, 14)
        col.setSpacing(9)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._title = QLabel(objectName="todoTitle")
        self._count = QLabel(objectName="todoCount")
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._count)
        col.addLayout(head)

        self._bar = QProgressBar(objectName="todoBar")
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setRange(0, 100)
        col.addWidget(self._bar)

        self._steps = QVBoxLayout()
        self._steps.setContentsMargins(0, 2, 0, 0)
        self._steps.setSpacing(3)
        col.addLayout(self._steps)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        outer.addWidget(self._card)

    def set_markdown(self, markdown: str, pet: QWidget | None = None, screen=None) -> None:
        """按 markdown 更新清单 空则隐藏"""
        parsed = self._parse(markdown)
        if parsed is None:
            self.hide()
            return
        title, items = parsed
        done = sum(1 for status, _ in items if status == "done")
        total = sum(1 for status, _ in items if status in ("done", "doing", "todo"))

        # plain 行不计进度
        self._title.setText(title.upper() if title.isascii() else title)  # 纯英文标题转大写 中文原样
        self._count.setText(f"{done}/{total}" if total else "")
        self._count.setVisible(bool(total))
        self._bar.setVisible(bool(total))
        self._bar.setValue(round(done / total * 100) if total else 0)

        self._clear_steps()
        for status, text in items:
            self._steps.addWidget(self._make_row(status, text))

        self._card.adjustSize()
        self.adjustSize()
        self.show()
        self.raise_()
        if pet is not None and screen is not None:
            place_beside_pet(self, pet, screen, prefer="right")

    def follow(self, pet: QWidget, screen) -> None:
        """宠物移动时跟着贴过去"""
        if self.isVisible():
            place_beside_pet(self, pet, screen, prefer="right")

    def dismiss(self) -> None:
        self.hide()

    def _clear_steps(self) -> None:
        """清掉旧步骤行"""
        while self._steps.count():
            item = self._steps.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()  # 交给 qt 事件循环回收

    def _make_row(self, status: str, text: str) -> QFrame:
        """一行待办 按四态换点和文字样式"""
        row = QFrame(objectName="rowDoing" if status == "doing" else "rowPlain")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(9)

        dot = QLabel()
        dot.setFixedSize(16, 16)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if status == "done":
            dot.setText("✓")
            dot.setStyleSheet(f"background:#e9e6fc; color:{_ACCENT}; border-radius:8px; font-size:10px; font-weight:900;")
        elif status == "doing":
            dot.setStyleSheet(f"background:{_ACCENT}; border-radius:8px;")
        elif status == "todo":
            dot.setStyleSheet("background:transparent; border:2px solid #d7d5ea; border-radius:8px;")
        else:
            dot.setStyleSheet("background:transparent;")
        lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        label = QLabel(text)
        label.setWordWrap(True)
        font = QFont(label.font())
        if status == "done":
            font.setStrikeOut(True)
            label.setStyleSheet("color:#b6b4c8; font-size:13px;")
        elif status == "doing":
            font.setWeight(QFont.Weight.DemiBold)
            label.setStyleSheet(f"color:{_ACCENT_DK}; font-size:13px;")
        else:
            label.setStyleSheet("color:#5f5e74; font-size:13px;")
        label.setFont(font)
        lay.addWidget(label, 1)
        return row

    @staticmethod
    def _parse(markdown: str) -> "tuple[str, list[tuple[str, str]]] | None":
        """首行当标题 其余按行首图标分状态"""
        lines = [ln for ln in (markdown or "").split("\n") if ln.strip()]
        if not lines:
            return None
        title = lines[0].replace("*", "").strip() or "计划"  # 去掉加粗标记 全空时兜底计划
        items: list[tuple[str, str]] = []
        for ln in lines[1:]:
            s = ln.strip()
            status = _ICON_STATUS.get(s[0])  # 只认首字符图标 认不出当普通行
            if status is not None:
                items.append((status, s[1:].strip()))
            else:
                items.append(("plain", s))
        return (title, items) if items else None
