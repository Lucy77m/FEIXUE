"""Small persistent shelf for workflow keepsakes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from desktop_pet import i18n, keepsakes


_KIND_MARKS = {"file": "▤", "image": "▣", "url": "◎", "text": "≡", "book": "▥"}


class KeepsakeShelf(QWidget):
    resume_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(i18n.t("shelf_title"))
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(500, 360)
        self.setStyleSheet("""
            QWidget { background: #fbfaf7; color: #302f39; font-family: 'Microsoft YaHei UI'; }
            QListWidget { background: #ffffff; border: 1px solid #dedbe6; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #efedf3; }
            QListWidget::item:selected { background: #ece8ff; color: #4937a8; }
            QLabel#detail { background: #ffffff; border: 1px solid #dedbe6; border-radius: 6px; padding: 12px; }
            QPushButton { background: #6f5bd3; color: white; border: 0; border-radius: 6px; padding: 8px 14px; }
            QPushButton:disabled { background: #c9c5d8; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        self._title = QLabel(i18n.t("shelf_title"))
        self._title.setStyleSheet("font-size: 17px; font-weight: 600;")
        root.addWidget(self._title)
        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.setFixedWidth(220)
        self._list.currentItemChanged.connect(self._select)
        self._detail = QLabel(i18n.t("shelf_empty"), objectName="detail")
        self._detail.setWordWrap(True)
        self._detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.addWidget(self._list)
        body.addWidget(self._detail, 1)
        root.addLayout(body, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self._continue = QPushButton(i18n.t("shelf_continue"))
        self._continue.setEnabled(False)
        self._continue.clicked.connect(self._resume)
        footer.addWidget(self._continue)
        root.addLayout(footer)
        self.refresh()

    def retranslate(self) -> None:
        self.setWindowTitle(i18n.t("shelf_title"))
        self._title.setText(i18n.t("shelf_title"))
        self._continue.setText(i18n.t("shelf_continue"))
        self.refresh()

    def refresh(self, select_id: str = "") -> None:
        self._list.clear()
        selected_row = 0
        for entry in keepsakes.recent(64):
            mark = _KIND_MARKS.get(entry.get("kind", "file"), "◇")
            when = str(entry.get("at", "")).replace("T", " ")
            item = QListWidgetItem(f"{mark}  {entry.get('title', '')}\n{when}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)
            if entry.get("id") == select_id:
                selected_row = self._list.count() - 1
        if self._list.count():
            self._list.setCurrentRow(selected_row)
        else:
            self._detail.setText(i18n.t("shelf_empty"))
            self._continue.setEnabled(False)

    def popup(self, pet, screen, select_id: str = "") -> None:
        self.refresh(select_id)
        geo = pet.frameGeometry()
        x = min(max(screen.left(), geo.center().x() - self.width() // 2), screen.right() - self.width() + 1)
        y = min(max(screen.top(), geo.top() - self.height() - 12), screen.bottom() - self.height() + 1)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _select(self, current, _previous) -> None:
        if current is None:
            self._detail.setText(i18n.t("shelf_empty"))
            self._continue.setEnabled(False)
            return
        entry = current.data(Qt.ItemDataRole.UserRole)
        parts = [entry.get("detail", "")]
        if entry.get("source"):
            parts.append(f"\n\n{i18n.t('shelf_source')}\n{entry['source']}")
        if entry.get("context"):
            context = (i18n.t("workshop_name") if entry["context"] == "workshop"
                       else entry["context"])
            parts.append(f"\n\n{i18n.t('shelf_context')} {context}")
        self._detail.setText("".join(parts))
        self._continue.setEnabled(True)

    def _resume(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        prompt = i18n.t("shelf_resume_prompt").format(
            title=entry.get("title", ""), detail=entry.get("detail", ""), source=entry.get("source", ""),
        )
        self.hide()
        self.resume_requested.emit(prompt)
