"""Lightweight conversation history viewer combining session and journal data."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from desktop_pet import i18n
from desktop_pet.agent.loopdefs import _SESSION_PATH
from desktop_pet.pet.fx import make_floating, place_beside_pet


_EMOTION_RE = re.compile(r"^\s*\[\w+\]\s*")


def _extract_text(msg: dict) -> str:
    """Pull human-readable text from an OpenAI-format message."""
    content = msg.get("content", "")
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        content = " ".join(parts)
    if not content and msg.get("tool_calls"):
        names = [tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"]]
        return i18n.t("history_tool_call").format(name=", ".join(names))
    if not isinstance(content, str):
        return ""
    return _EMOTION_RE.sub("", content).strip()


def _fmt_time(epoch: float) -> str:
    """Format an epoch timestamp as HH:MM."""
    if epoch <= 0:
        return ""
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def _load_session() -> dict | None:
    """Load session.json if it exists and is fresh."""
    try:
        if not _SESSION_PATH.exists():
            return None
        data = json.loads(_SESSION_PATH.read_text(encoding="utf-8"))
        if time.time() - data.get("saved_at", 0) > 7200:  # 2 hours for display (longer than 25-min restore limit)
            return None
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


class HistoryViewer(QWidget):
    """Merged view of current session conversation and journal events."""

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setFixedSize(520, 420)
        self.setStyleSheet("""
            QWidget { background: #fbfaf7; color: #302f39; font-family: 'Microsoft YaHei UI'; }
            QListWidget { background: white; border: 1px solid #dedbe6; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: #ece8ff; color: #4937a8; }
            QPushButton { background: #6f5bd3; color: white; border: 0; border-radius: 6px; padding: 8px 16px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 17px; font-weight: 600;")
        root.addWidget(self._title)
        self._list = QListWidget()
        self._list.setWordWrap(True)
        root.addWidget(self._list, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton(i18n.t("fishing_close"))  # reuse "关闭"
        close.clicked.connect(self.hide)
        footer.addWidget(close)
        root.addLayout(footer)

    def popup(self, pet, screen) -> None:
        """Refresh data and show positioned near the pet."""
        self.refresh()
        place_beside_pet(self, pet, screen, prefer="left", gap=12)
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        self._list.clear()
        entries: list[str] = []
        # --- Session messages ---
        session = _load_session()
        if session:
            compressed = session.get("compressed", "")
            if compressed:
                entries.append(f"\U0001f4cb {i18n.t('history_session_summary')} {compressed[:120]}")
            ts = session.get("saved_at", 0)
            for msg in session.get("messages", []):
                role = msg.get("role", "")
                if role == "tool":
                    continue
                text = _extract_text(msg)
                if not text:
                    continue
                icon = "\U0001f464" if role == "user" else "\U0001fa77"
                entries.append(f"{_fmt_time(ts)}  {icon} {text[:100]}")
        # --- Journal events ---
        from desktop_pet import journal
        for entry in journal.diary(40):
            entries.append(f"{entry['when']}  \U0001f4dd {entry['text'][:100]}")
        # --- Populate ---
        if not entries:
            self._title.setText(i18n.t("history_title"))
            self._list.addItem(QListWidgetItem(i18n.t("history_empty")))
            return
        self._title.setText(i18n.t("history_title"))
        for text in entries:
            self._list.addItem(QListWidgetItem(text))
