from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet.pet.workshop import WorkshopWindow
from desktop_pet.world import WorldStore


def _book(store, title="brief.md"):
    item = store.create_reading(title, str(store._path.parent / "project" / title))
    return store.complete(item.id, "summary", "keepsake-id")


def test_workshop_scene_renders_generated_room_and_books(tmp_path):
    store = WorldStore(tmp_path / "world.json")
    _book(store)
    window = WorkshopWindow(store)
    window.set_stage("reading", "brief.md")
    image = QImage(window.size(), QImage.Format.Format_ARGB32)
    image.fill(0)

    window.render(image)

    assert window._background.isNull() is False
    assert len(window._book_rects) == 1
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(0, image.height(), 12)
        for x in range(0, image.width(), 12)
    )


def test_workshop_selects_book_by_runtime_hitbox(tmp_path):
    store = WorldStore(tmp_path / "world.json")
    book = _book(store, "notes.pdf")
    window = WorkshopWindow(store)
    image = QImage(window.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    window.render(image)

    assert window._book_rects[0][1] == book.id


def test_hidden_workshop_stops_animation_timer(tmp_path):
    window = WorkshopWindow(WorldStore(tmp_path / "world.json"))
    window.show()
    window.set_stage("reading", "brief.md")
    assert window._timer.isActive()

    window.hide()

    assert window._timer.isActive() is False
