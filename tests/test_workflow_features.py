import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6.QtCore import QMimeData, QObject, QPointF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDropEvent, QImage
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication([])

from desktop_pet import keepsakes
from desktop_pet.companions.playtime import Playtime
from desktop_pet.companions.workflow import WorkflowCtrl
from desktop_pet.pet.chat import attachment_payload
from desktop_pet.pet.footprints import FootprintLayer
from desktop_pet.pet.keepsake_shelf import KeepsakeShelf
from desktop_pet.pet.window import PetWindow


class _PetStub(QObject):
    offered = Signal(object)

    def __init__(self):
        super().__init__()
        self.item = None

    def wake(self):
        pass

    def react(self, _name):
        pass

    def set_work_item(self, kind, label, stage):
        self.item = (kind, label, stage)

    def clear_work_item(self):
        self.item = None


class _InputStub(QObject):
    submitted = Signal(str, object)


class _FeedingStub:
    def __init__(self):
        self.offers = []

    def offer(self, paths):
        self.offers.append(paths)
        return True


class _WorkshopStub:
    def __init__(self):
        self.begun = []
        self.steps = []
        self.completed = []
        self.stopped = False

    def begin(self, label, source):
        self.begun.append((label, source))
        return "world-id"

    def on_step(self, stage):
        self.steps.append(stage)

    def complete(self, ok, item, world_id=""):
        self.completed.append((ok, item, world_id))

    def stop(self):
        self.stopped = True


class _HostStub:
    def __init__(self):
        self._pet = _PetStub()
        self._input = _InputStub()
        self._keepsake_shelf = None
        self._feeding = _FeedingStub()
        self._workshop = _WorkshopStub()
        self.messages = []

    def _engaged(self):
        return False

    def _feed_pop(self, text):
        self.messages.append(text)


def test_workflow_actions_match_dropped_content():
    assert WorkflowCtrl.actions_for("file") == ("inspect", "summarize", "organize", "remember")
    assert WorkflowCtrl.actions_for("image") == ("inspect", "summarize", "remember")
    assert WorkflowCtrl.actions_for("text") == ("explain", "summarize", "remember")
    assert WorkflowCtrl.actions_for("file", True)[-1] == "feed"


def test_safe_file_can_route_from_workflow_menu_to_feeding(tmp_path):
    path = tmp_path / "cache.tmp"
    path.write_text("discard", encoding="utf-8")
    host = _HostStub()
    workflow = WorkflowCtrl(host)
    offer = workflow._normalize({"kind": "files", "paths": [str(path)]})

    assert offer is not None and offer["feedable"] is True
    workflow._offer = offer
    workflow._start("feed")

    assert host._feeding.offers == [[str(path.resolve())]]
    assert host._pet.item is None


def test_images_documents_and_programs_are_not_offered_as_food(tmp_path):
    host = _HostStub()
    workflow = WorkflowCtrl(host)
    paths = []
    for name in ("photo.png", "notes.md", "setup.exe"):
        path = tmp_path / name
        path.write_bytes(b"data")
        paths.append(path)

    offers = [workflow._normalize({"kind": "files", "paths": [str(path)]}) for path in paths]

    assert all(offer is not None and offer["feedable"] is False for offer in offers)


def test_document_workshop_route_creates_a_persistent_book(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    path = tmp_path / "brief.md"
    path.write_text("project brief", encoding="utf-8")
    host = _HostStub()
    sent = []
    host._input.submitted.connect(lambda prompt, attachments: sent.append((prompt, attachments)))
    workflow = WorkflowCtrl(host)
    offer = workflow._normalize({"kind": "files", "paths": [str(path)]})

    assert offer is not None and offer["workshopable"] is True
    assert WorkflowCtrl.actions_for("file", workshopable=True)[0] == "workshop"
    workflow._offer = offer
    workflow._start("workshop")
    workflow.on_step("读取文档")
    workflow.on_reply("这是一份项目简报，核心目标是完成纵向原型。")
    item = workflow.complete(True)

    assert host._workshop.begun == [("brief.md", str(path.resolve()))]
    assert host._workshop.steps == ["reading"]
    assert sent and sent[0][1][0]["kind"] == "file"
    assert item is not None and item["kind"] == "book"
    assert host._workshop.completed[-1] == (True, item, "world-id")
    assert keepsakes.get(item["id"])["context"] == "workshop"


def test_workflow_tracks_agent_steps_and_creates_keepsake(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    host = _HostStub()
    sent = []
    host._input.submitted.connect(lambda prompt, attachments: sent.append((prompt, attachments)))
    workflow = WorkflowCtrl(host)
    workflow._offer = {
        "kind": "text", "label": "ValueError at line 4", "source": "ValueError at line 4",
        "paths": [], "text": "ValueError at line 4",
    }

    workflow._start("explain")
    assert sent and "ValueError" in sent[0][0]
    assert host._pet.item == ("text", "ValueError at line 4", "working")
    workflow.on_step("读取日志")
    assert host._pet.item[-1] == "reading"
    workflow.on_reply("原因是输入格式错误，修正第四行即可。")
    item = workflow.complete(True, context="code")

    assert item is not None
    assert keepsakes.count() == 1
    assert "修正第四行" in keepsakes.recent(1)[0]["detail"]
    assert host._pet.item[-1] == "done"


def test_attachment_payload_preserves_images_for_multimodal_input(tmp_path):
    path = tmp_path / "sample.png"
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("#cc3344"))
    assert image.save(str(path))

    payload = attachment_payload([str(path)])

    assert payload[0]["kind"] == "image"
    assert payload[0]["data_url"].startswith("data:image/")


def test_context_classifier_distinguishes_work_modes():
    assert Playtime.classify_context("Code.exe", "main.py - Code") == "code"
    assert Playtime.classify_context("WindowsTerminal.exe", "PowerShell") == "terminal"
    assert Playtime.classify_context("Acrobat.exe", "notes.pdf") == "document"
    assert Playtime.classify_context("chrome.exe", "YouTube") == "media"
    assert Playtime.classify_context("firefox.exe", "Docs") == "browser"


def test_shared_classify_window_directly():
    from desktop_pet.companions.context_classifier import classify_window

    # code detection via process name and title
    assert classify_window("main.py - Code", "Code.exe") == "code"
    assert classify_window("", "pycharm") == "code"
    # terminal detection
    assert classify_window("PowerShell", "WindowsTerminal.exe") == "terminal"
    assert classify_window("bash", "wsl.exe") == "terminal"
    # document detection
    assert classify_window("notes.pdf", "Acrobat.exe") == "document"
    # media detection
    assert classify_window("YouTube", "chrome.exe") == "media"
    # social detection (new category not in playtime)
    assert classify_window("Instagram", "chrome.exe") == "social"
    # browser detection (broad catch-all)
    assert classify_window("Docs", "firefox.exe") == "browser"
    # empty / generic
    assert classify_window("") == "generic"
    assert classify_window("random app") == "generic"


def test_keepsake_shelf_can_resume_selected_item(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    keepsakes.add("file", "总结 · notes.md", "三个关键结论", source="notes.md", context="document")
    shelf = KeepsakeShelf()
    resumed = []
    shelf.resume_requested.connect(resumed.append)

    shelf._resume()

    assert resumed and "notes.md" in resumed[0]


def test_keepsake_shelf_can_select_a_fished_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(keepsakes, "_PATH", tmp_path / "keepsakes.json")
    older = keepsakes.add("text", "Older memory", "first")
    keepsakes.add("text", "Newest memory", "second")
    shelf = KeepsakeShelf()

    shelf.refresh(older["id"])

    selected = shelf._list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert selected["id"] == older["id"]


def test_pet_work_item_renders_with_sprite():
    pet = PetWindow("xiaofeixue")
    pet.set_work_item("url", "example.com", "working")
    image = QImage(pet.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    pet.render(image)

    assert pet._work_item["stage"] == "working"
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(0, image.height(), 4)
        for x in range(0, image.width(), 4)
    )


def test_pet_edge_peek_is_temporary_and_restores_position():
    pet = PetWindow("xiaofeixue")
    pet.show()
    original = pet.frameGeometry().topLeft()

    assert pet.start_edge_peek("right", 1.5)
    assert pet.is_life_busy

    pet._hideout_until = time.perf_counter() - 0.1
    pet._tick()

    assert not pet.is_life_busy
    assert pet.frameGeometry().topLeft() == original


def test_pet_life_trace_uses_short_lived_overlay():
    pet = PetWindow("xiaofeixue")
    pet.show()

    assert pet.leave_life_trace("star", 3)
    assert pet._life_traces is not None
    assert len(pet._life_traces._steps) == 3
    assert all(step[3] == "star" and 4.0 <= step[6] <= 6.0 for step in pet._life_traces._steps)


def test_footprint_layer_supports_star_dot_and_crops():
    layer = FootprintLayer()
    layer.setGeometry(0, 0, 200, 200)
    layer.show()

    for i in range(30):
        layer.add(i, i, 0.0, "star" if i % 2 else "dot", 5.0)

    assert len(layer._steps) == 24
    assert {"star", "dot"} <= {step[3] for step in layer._steps}
    layer.close()


def test_pet_drop_routes_normal_files_to_workflow_and_shift_to_feeding(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    pet = PetWindow("xiaofeixue")
    offered = []
    fed = []
    pet.offered.connect(offered.append)
    pet.fed.connect(fed.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    normal = QDropEvent(
        QPointF(10, 10), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    )
    pet.dropEvent(normal)
    shifted = QDropEvent(
        QPointF(10, 10), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.ShiftModifier,
    )
    pet.dropEvent(shifted)

    assert offered[0]["kind"] == "files"
    assert Path(offered[0]["paths"][0]) == path
    assert Path(fed[0][0]) == path


def test_context_perch_positions_pet_and_records_mode(monkeypatch):
    import desktop_pet.companions.playtime as playtime_mod

    monkeypatch.setattr(playtime_mod.random, "random", lambda: 0.99)
    monkeypatch.setattr(playtime_mod.random, "uniform", lambda _a, _b: 60.0)

    class Host:
        def __init__(self):
            self._app = QApplication.instance()
            self._pet = PetWindow("xiaofeixue")
            self._pet.show()
            self._settings = SimpleNamespace(context_perch_enabled=True, proactive_enabled=True)
            self._meeting_mode = False
            self.messages = []
            self._watchers = SimpleNamespace(_clip_treasures=[])

        def _engaged(self):
            return False

        def _feed_pop(self, message):
            self.messages.append(message)

        def _feed_react(self, name):
            self._pet.react(name)

    host = Host()
    playtime = Playtime(host)

    assert playtime._start_context_perch(123, (100, 320, 1000, 820), "code")
    assert playtime.context_kind == "code"
    assert playtime._perch_hwnd == 123
    assert playtime._perch_until - playtime._perch_started == 60.0
    assert host._pet.frameGeometry().top() < 320
    assert host.messages == []
    playtime._perch_done("settled")
    assert playtime._perch_hwnd == 0
    assert playtime._perch_until == 0.0


def test_classify_window_edge_cases():
    from desktop_pet.companions.context_classifier import classify_window
    assert classify_window("") == "generic"
    assert classify_window("   ") == "generic"
    assert classify_window("random text", "") == "generic"
    assert classify_window("哔哩哔哩 - 动画") == "media"
    assert classify_window("Visual Studio Code - main.py") == "code"
    assert classify_window("", "chrome.exe") == "browser"
