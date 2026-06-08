# author: bdth
# email: 2074055628@qq.com
# 任务清单浮窗：常驻显示当前 plan 的待办清单。

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from desktop_pet.pet.fx import make_floating, place_beside_pet

_ACCENT = "#7c6cff"
_FONT = "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
_MARGIN = 18
_MAXW = 280
_STYLE = f"""
* {{ font-family: {_FONT}; }}
#todoCard {{ background: #ffffff; border-radius: 14px; border: 1px solid #ecebf5; }}
#todoTitle {{ color: {_ACCENT}; font-size: 12px; font-weight: 800; letter-spacing: 1px; background: transparent; }}
#todoBody {{ color: #4a4960; font-size: 13px; background: transparent; }}
"""


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TodoBoard(QWidget):
    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._card = QFrame(objectName="todoCard")
        self._card.setStyleSheet(_STYLE)
        self._card.setMaximumWidth(_MAXW)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(90, 80, 150, 80))
        shadow.setOffset(0, 6)
        self._card.setGraphicsEffect(shadow)

        col = QVBoxLayout(self._card)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(7)
        self._title = QLabel(objectName="todoTitle")
        self._body = QLabel(objectName="todoBody")
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setWordWrap(True)
        col.addWidget(self._title)
        col.addWidget(self._body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        outer.addWidget(self._card)

    def set_markdown(self, markdown: str, pet: QWidget | None = None, screen=None) -> None:
        """用 progress.render_plan 的输出更新清单；空/无步骤则隐藏。"""
        parsed = self._parse(markdown)
        if parsed is None:
            self.hide()
            return
        title, rows = parsed
        self._title.setText(title)
        self._body.setText("<br>".join(rows))
        self._card.adjustSize()
        self.adjustSize()
        self.show()
        self.raise_()
        if pet is not None and screen is not None:
            place_beside_pet(self, pet, screen, prefer="right")

    def dismiss(self) -> None:
        self.hide()

    @staticmethod
    def _parse(markdown: str) -> "tuple[str, list[str]] | None":
        lines = [ln for ln in (markdown or "").split("\n") if ln.strip()]
        if not lines:
            return None
        title = lines[0].replace("*", "").strip() or "当前计划"
        rows: list[str] = []
        for ln in lines[1:]:
            s = ln.strip()
            icon, text = s[0], _esc(s[1:].strip())
            if icon == "●":
                rows.append(f'<span style="color:#bdbcce;">✓ <s>{text}</s></span>')
            elif icon == "→":
                rows.append(f'<span style="color:{_ACCENT}; font-weight:700;">▸ {text}</span>')
            elif icon == "○":
                rows.append(f'<span style="color:#6b6a82;">○ {text}</span>')
            else:
                rows.append(f'<span style="color:#6b6a82;">{_esc(s)}</span>')
        return (title, rows) if rows else None
