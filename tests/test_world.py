from __future__ import annotations

from datetime import datetime, timedelta

from desktop_pet import keepsakes
from desktop_pet.world import WorldStore


def _finish(store: WorldStore, name: str, source: str, origin: str = ""):
    item = store.create_reading(name, source)
    return store.complete(item.id, f"summary for {name}", origin)


def test_reading_recovers_as_interrupted_after_restart(tmp_path):
    path = tmp_path / "world.json"
    store = WorldStore(path)
    item = store.create_reading("brief.md", str(tmp_path / "project" / "brief.md"))

    restored = WorldStore(path).get(item.id)

    assert restored is not None
    assert restored.state == "interrupted"
    assert restored.zone == "desk"


def test_carried_book_returns_to_reserved_slot_after_restart(tmp_path):
    path = tmp_path / "world.json"
    store = WorldStore(path)
    book = _finish(store, "brief.md", str(tmp_path / "project" / "brief.md"))
    slot = book.slot
    assert store.carry(book.id) is not None
    _finish(store, "new.md", str(tmp_path / "other" / "new.md"))

    restored = WorldStore(path).get(book.id)

    assert restored is not None and restored.state == "shelved"
    assert restored.zone == "shelf" and restored.slot == slot
    slots = [item.slot for item in WorldStore(path).visible_books()]
    assert len(slots) == len(set(slots))


def test_keepsake_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    book = keepsakes.add("book", "Shelf · notes.md", "summary", source=str(tmp_path / "alpha" / "notes.md"))
    store = WorldStore(tmp_path / "world.json")

    assert store.migrate_keepsakes() == 1
    assert store.migrate_keepsakes() == 0
    visible = store.visible_books()
    assert len(visible) == 1
    assert visible[0].origin_keepsake_id == book["id"]


def test_auto_layout_groups_projects_and_preserves_manual_slots(tmp_path):
    store = WorldStore(tmp_path / "world.json")
    alpha1 = _finish(store, "a1.md", str(tmp_path / "alpha" / "a1.md"))
    beta = _finish(store, "b.md", str(tmp_path / "beta" / "b.md"))
    alpha2 = _finish(store, "a2.md", str(tmp_path / "alpha" / "a2.md"))
    assert alpha1 and beta and alpha2
    alpha_slots = sorted(item.slot for item in store.visible_books() if item.project_key == "alpha")
    assert alpha_slots[1] - alpha_slots[0] == 1

    assert store.move(beta.id, 14)
    _finish(store, "a3.md", str(tmp_path / "alpha" / "a3.md"))

    moved = store.get(beta.id)
    assert moved is not None and moved.slot == 14 and moved.placement == "manual"


def test_sixteenth_auto_book_is_archived(tmp_path):
    store = WorldStore(tmp_path / "world.json")
    for index in range(21):
        _finish(store, f"{index}.md", str(tmp_path / "project" / f"{index}.md"))

    assert len(store.visible_books()) == 20
    assert len(store.archived()) == 1


def test_revisit_prefers_matching_project_and_obeys_limits(tmp_path):
    store = WorldStore(tmp_path / "world.json")
    alpha = _finish(store, "alpha.md", str(tmp_path / "alpha" / "alpha.md"))
    _finish(store, "beta.md", str(tmp_path / "beta" / "beta.md"))
    now = datetime(2026, 6, 22, 12, 0, 0)

    chosen = store.choose_revisit("alpha - Visual Studio Code", now)
    assert chosen is not None and chosen.id == alpha.id
    assert store.record_revisit(chosen.id, used_ai=True, now=now)
    assert store.revisit_allowed(now + timedelta(hours=1)) is False
    assert store.ai_revisit_allowed(now + timedelta(hours=1)) is False
    assert store.revisit_allowed(now + timedelta(hours=7)) is True
    assert store.choose_revisit("alpha", now + timedelta(hours=7)).id != alpha.id
