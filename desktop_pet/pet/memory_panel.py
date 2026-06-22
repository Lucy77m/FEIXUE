"""Memory visualization panel — browse and manage the pet's long-term memories."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from desktop_pet import i18n
from desktop_pet.pet.fx import make_floating, place_beside_pet


class MemoryPanel(QWidget):
    """Floating panel showing the pet's memories, preferences, and environment."""

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setFixedSize(540, 460)
        self.setStyleSheet("""
            QWidget { background: #fbfaf7; color: #302f39; font-family: 'Microsoft YaHei UI'; }
            QListWidget { background: white; border: 1px solid #dedbe6; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: #ece8ff; color: #4937a8; }
            QPushButton { background: #6f5bd3; color: white; border: 0; border-radius: 6px; padding: 8px 16px; }
            QPushButton:disabled { background: #c9c5d8; }
            QLineEdit { border: 1px solid #dedbe6; border-radius: 6px; padding: 6px 10px; }
            QTabWidget::pane { border: 1px solid #dedbe6; border-radius: 6px; }
            QTabBar::tab { padding: 6px 14px; }
            QTabBar::tab:selected { background: #ece8ff; color: #4937a8; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)

        # Title
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 17px; font-weight: 600;")
        root.addWidget(self._title)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText(i18n.t("memory_search"))
        self._search.returnPressed.connect(self._do_search)
        root.addWidget(self._search)

        # Tabs
        self._tabs = QTabWidget()
        self._core_list = QListWidget()
        self._recent_list = QListWidget()
        self._prefs_list = QListWidget()
        self._env_list = QListWidget()
        self._tabs.addTab(self._core_list, i18n.t("memory_core"))
        self._tabs.addTab(self._recent_list, i18n.t("memory_recent"))
        self._tabs.addTab(self._prefs_list, i18n.t("memory_prefs"))
        self._tabs.addTab(self._env_list, i18n.t("memory_env"))
        root.addWidget(self._tabs, 1)

        # Footer
        footer = QHBoxLayout()
        self._forget_btn = QPushButton(i18n.t("memory_forget"))
        self._forget_btn.clicked.connect(self._forget_selected)
        footer.addWidget(self._forget_btn)
        footer.addStretch(1)
        close = QPushButton(i18n.t("fishing_close"))
        close.clicked.connect(self.hide)
        footer.addWidget(close)
        root.addLayout(footer)

    def popup(self, pet, screen) -> None:
        self.refresh()
        place_beside_pet(self, pet, screen, prefer="left", gap=12)
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        from desktop_pet.memory.store import store
        total = store.count()
        self._title.setText(i18n.t("memory_title").format(n=total))

        # Core memories
        self._core_list.clear()
        core = store.core_memories(10)
        if core:
            for text in core:
                self._add_item(self._core_list, text, "")
        else:
            self._add_item(self._core_list, i18n.t("memory_empty"), "")

        # Recent with metadata
        self._recent_list.clear()
        recent = store.recent_experiences_detail(30)
        if recent:
            for entry in recent:
                sal = entry["salience"]
                src = entry["source"]
                label = f"[{src}] (⭐{sal:.2f}) {entry['content'][:80]}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, entry["content"])
                self._recent_list.addItem(item)
        else:
            self._add_item(self._recent_list, i18n.t("memory_empty"), "")

        # Preferences
        self._prefs_list.clear()
        prefs = store.profile_items()
        if prefs:
            for key, val in prefs:
                self._add_item(self._prefs_list, f"{key}: {val}", "")
        else:
            self._add_item(self._prefs_list, i18n.t("memory_empty"), "")

        # Environment
        self._env_list.clear()
        env = store.env_items()
        if env:
            for key, val in env:
                self._add_item(self._env_list, f"{key} = {val}", "")
        else:
            self._add_item(self._env_list, i18n.t("memory_empty"), "")

    def _add_item(self, list_widget: QListWidget, text: str, data: str) -> None:
        item = QListWidgetItem(text[:200])
        item.setData(Qt.ItemDataRole.UserRole, data or text[:200])
        list_widget.addItem(item)

    def _do_search(self) -> None:
        query = self._search.text().strip()
        if not query:
            self.refresh()
            return
        from desktop_pet.memory.store import store
        results = store.recall_relevant(query, k=20)
        self._recent_list.clear()
        self._tabs.setCurrentWidget(self._recent_list)
        if results:
            for text in results:
                item = QListWidgetItem(text[:120])
                item.setData(Qt.ItemDataRole.UserRole, text[:200])
                self._recent_list.addItem(item)
        else:
            self._add_item(self._recent_list, i18n.t("memory_empty"), "")

    def _forget_selected(self) -> None:
        tab = self._tabs.currentWidget()
        if not isinstance(tab, QListWidget):
            return
        item = tab.currentItem()
        if item is None:
            return
        content = item.data(Qt.ItemDataRole.UserRole) or ""
        if not content:
            return
        from desktop_pet.memory.store import store
        store.forget(content[:40])
        self.refresh()
