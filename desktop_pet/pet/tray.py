# 系统托盘图标与右键菜单 同一份菜单也给宠物右键复用

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from desktop_pet import i18n
from desktop_pet.pet.icon import feixue_icon

# 表演子菜单 名字对应小品或反应
_PERFORM_ITEMS = (
    ("yarn", "act_yarn"), ("fish", "act_fish"), ("coffee", "act_coffee"),
    ("read", "act_read"), ("stars", "act_stars"), ("dance", "act_dance"),
    ("celebrate", "act_celebrate"), ("flip", "act_flip"),
    ("purr", "act_purr"), ("wave", "act_wave"),
)

# 跟控制面板一个皮肤 白卡圆角加紫色悬停
_MENU_QSS = """
QMenu {
    background: #ffffff;
    border: 1px solid #e6e3f1;
    border-radius: 12px;
    padding: 6px 5px;
    font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
}
QMenu::item {
    color: #3b3a4d;
    font-size: 13px;
    padding: 8px 32px 8px 16px;
    margin: 1px 4px;
    border-radius: 8px;
    background: transparent;
    min-width: 130px;
}
QMenu::item:selected { background: #efecff; color: #6a59f5; }
QMenu::item:disabled { color: #b6b4c8; }
QMenu::separator { height: 1px; background: #efedf7; margin: 5px 12px; }
QMenu::right-arrow { width: 8px; height: 8px; }
"""


def _dress(menu: QMenu) -> QMenu:
    """无边框加透明底才能有真圆角 不然四角是方的"""
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    menu.setStyleSheet(_MENU_QSS)
    return menu


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        on_open_panel: Callable[[], None],
        on_quit: Callable[[], None],
        on_talk: Callable[[], None] | None = None,
        on_peek: Callable[[], None] | None = None,
        on_new_topic: Callable[[], None] | None = None,
        on_toggle_show: Callable[[], None] | None = None,
        is_shown: Callable[[], bool] | None = None,
        on_focus: Callable[[], None] | None = None,
        on_ball: Callable[[], None] | None = None,
        on_fishing: Callable[[], None] | None = None,
        on_workshop: Callable[[], None] | None = None,
        on_perform: Callable[[str], None] | None = None,
        on_keepsakes: Callable[[], None] | None = None,
        on_history: Callable[[], None] | None = None,
        on_pet_scale: Callable[[int], None] | None = None,
        get_pet_scale: Callable[[], int] | None = None,
    ) -> None:
        super().__init__(feixue_icon())
        self.setToolTip(i18n.t("tray_tooltip"))
        self._on_open_panel = on_open_panel
        self._is_shown = is_shown
        self._get_pet_scale = get_pet_scale

        menu = _dress(QMenu())
        self._act_talk = self._add(menu, "tray_talk", on_talk)
        self._act_peek = self._add(menu, "tray_peek", on_peek)
        self._act_new_topic = self._add(menu, "tray_new_topic", on_new_topic)
        self._act_focus = self._add(menu, "tray_focus", on_focus)
        self._act_ball = self._add(menu, "tray_ball", on_ball)
        self._act_fishing = self._add(menu, "tray_memory_fishing", on_fishing)
        self._act_workshop = self._add(menu, "tray_workshop", on_workshop)
        self._perform_menu: QMenu | None = None
        self._perform_actions: dict[str, QAction] = {}
        if on_perform is not None:
            self._perform_menu = _dress(menu.addMenu(i18n.t("tray_perform")))
            for name, key in _PERFORM_ITEMS:
                act = QAction(i18n.t(key), self._perform_menu)
                act.triggered.connect(lambda _checked=False, n=name: on_perform(n))
                self._perform_menu.addAction(act)
                self._perform_actions[name] = act
        self._act_history = self._add(menu, "tray_history", on_history)
        self._act_keepsakes = self._add(menu, "tray_keepsakes", on_keepsakes)
        self._scale_menu: QMenu | None = None
        self._scale_actions: dict[int, QAction] = {}
        if on_pet_scale is not None:
            self._scale_menu = _dress(menu.addMenu(i18n.t("tray_pet_size")))
            scale_group = QActionGroup(self._scale_menu)
            scale_group.setExclusive(True)
            for scale in (75, 100, 125, 150):
                act = QAction(f"{scale}%", self._scale_menu)
                act.setCheckable(True)
                act.triggered.connect(lambda _checked=False, value=scale: on_pet_scale(value))
                scale_group.addAction(act)
                self._scale_menu.addAction(act)
                self._scale_actions[scale] = act
        self._act_toggle = self._add(menu, "tray_hide", on_toggle_show)
        # 全没建就不画分隔线
        if any((self._act_talk, self._act_peek, self._act_new_topic, self._act_toggle)):
            menu.addSeparator()
        self._act_open = self._add(menu, "tray_open_panel", on_open_panel)
        menu.addSeparator()
        self._act_quit = self._add(menu, "tray_quit", on_quit)
        menu.aboutToShow.connect(self._sync_menu_state)
        self.setContextMenu(menu)
        self._menu = menu
        self.activated.connect(self._on_activated)

    def context_menu(self) -> QMenu:
        """给宠物右键复用的菜单 取前先刷文案"""
        self._sync_menu_state()
        return self._menu

    def _sync_menu_state(self) -> None:
        self._sync_toggle_label()
        if self._get_pet_scale is None:
            return
        current = self._get_pet_scale()
        for scale, action in self._scale_actions.items():
            action.setChecked(scale == current)

    def _sync_toggle_label(self) -> None:
        # 现查 is_shown 不缓存
        if self._act_toggle is None:
            return
        shown = True if self._is_shown is None else bool(self._is_shown())
        self._act_toggle.setText(i18n.t("tray_hide") if shown else i18n.t("tray_show"))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._on_open_panel()

    def notify(self, title: str, body: str, msecs: int = 8000) -> None:
        """托盘气泡通知 不支持就静默"""
        try:
            if QSystemTrayIcon.supportsMessages():
                self.showMessage(title, body, feixue_icon(), msecs)
        except Exception:
            pass

    def retranslate(self) -> None:
        self.setToolTip(i18n.t("tray_tooltip"))
        for act, key in (
            (self._act_talk, "tray_talk"),
            (self._act_peek, "tray_peek"),
            (self._act_new_topic, "tray_new_topic"),
            (self._act_fishing, "tray_memory_fishing"),
            (self._act_workshop, "tray_workshop"),
            (self._act_keepsakes, "tray_keepsakes"),
            (self._act_history, "tray_history"),
            (self._act_open, "tray_open_panel"),
            (self._act_quit, "tray_quit"),
        ):
            if act is not None:
                act.setText(i18n.t(key))
        if self._scale_menu is not None:
            self._scale_menu.setTitle(i18n.t("tray_pet_size"))
        if self._perform_menu is not None:
            self._perform_menu.setTitle(i18n.t("tray_perform"))
            for name, key in _PERFORM_ITEMS:
                self._perform_actions[name].setText(i18n.t(key))
        self._sync_toggle_label()

    def _add(self, menu: QMenu, key: str, slot: Callable[[], None] | None) -> QAction | None:
        # slot 没给就不建返回 None
        if slot is None:
            return None
        action = QAction(i18n.t(key), menu)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action
