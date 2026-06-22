from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet.pet.memory_panel import MemoryPanel


class StoreStub:
    def __init__(self):
        self.forgotten = []

    def count(self):
        return 1

    def core_memories(self, _n):
        return ["core memory"]

    def recent_experiences_detail(self, _n):
        return [{"content": "finished a release", "salience": 0.8, "source": "test"}]

    def profile_items(self):
        return [("language", "Chinese")]

    def env_items(self):
        return [("editor", "Code")]

    def recall_relevant(self, query, k):
        assert (query, k) == ("release", 20)
        return ["matching release memory"]

    def forget(self, query):
        self.forgotten.append(query)


def test_memory_panel_populates_all_tabs(monkeypatch):
    store = StoreStub()
    monkeypatch.setattr("desktop_pet.memory.store.store", store)
    panel = MemoryPanel()

    panel.refresh()

    assert panel._tabs.count() == 4
    assert panel._core_list.item(0).text() == "core memory"
    assert "finished a release" in panel._recent_list.item(0).text()
    assert panel._prefs_list.item(0).text() == "language: Chinese"
    assert panel._env_list.item(0).text() == "editor = Code"


def test_memory_panel_search_and_forget(monkeypatch):
    store = StoreStub()
    monkeypatch.setattr("desktop_pet.memory.store.store", store)
    panel = MemoryPanel()
    panel.refresh()
    panel._search.setText("release")

    panel._do_search()

    assert panel._tabs.currentWidget() is panel._recent_list
    assert panel._recent_list.item(0).text() == "matching release memory"
    panel._recent_list.setCurrentRow(0)
    panel._forget_selected()
    assert store.forgotten == ["matching release memory"]


def test_memory_panel_empty_state(monkeypatch):
    store = StoreStub()
    store.count = lambda: 0
    store.core_memories = lambda _n: []
    store.recent_experiences_detail = lambda _n: []
    store.profile_items = lambda: []
    store.env_items = lambda: []
    monkeypatch.setattr("desktop_pet.memory.store.store", store)
    panel = MemoryPanel()

    panel.refresh()

    for widget in (panel._core_list, panel._recent_list, panel._prefs_list, panel._env_list):
        assert widget.count() == 1
        assert widget.item(0).data(Qt.ItemDataRole.UserRole)
