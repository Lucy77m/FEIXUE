# author: bdth
# email: 2074055628@qq.com
# 系统托盘图标与右键菜单 同一份菜单也给宠物右键复用

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from desktop_pet import i18n
from desktop_pet.pet.icon import mochi_icon

# 表演子菜单 名字对应小品或反应
_PERFORM_ITEMS = (
    ("yarn", "act_yarn"), ("fish", "act_fish"), ("coffee", "act_coffee"),
    ("read", "act_read"), ("stars", "act_stars"), ("dance", "act_dance"),
    ("celebrate", "act_celebrate"), ("flip", "act_flip"),
    ("purr", "act_purr"), ("wave", "act_wave"),
)


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
        on_perform: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(mochi_icon())
        self.setToolTip(i18n.t("tray_tooltip"))
        self._on_open_panel = on_open_panel
        self._is_shown = is_shown

        menu = QMenu()
        self._act_talk = self._add(menu, "tray_talk", on_talk)
        self._act_peek = self._add(menu, "tray_peek", on_peek)
        self._act_new_topic = self._add(menu, "tray_new_topic", on_new_topic)
        self._act_focus = self._add(menu, "tray_focus", on_focus)
        self._act_ball = self._add(menu, "tray_ball", on_ball)
        if on_perform is not None:
            sub = menu.addMenu(i18n.t("tray_perform"))
            for name, key in _PERFORM_ITEMS:
                act = QAction(i18n.t(key), sub)
                act.triggered.connect(lambda _checked=False, n=name: on_perform(n))
                sub.addAction(act)
        self._act_toggle = self._add(menu, "tray_hide", on_toggle_show)
        # 全没建就不画分隔线
        if any((self._act_talk, self._act_peek, self._act_new_topic, self._act_toggle)):
            menu.addSeparator()
        self._act_open = self._add(menu, "tray_open_panel", on_open_panel)
        menu.addSeparator()
        self._act_quit = self._add(menu, "tray_quit", on_quit)
        menu.aboutToShow.connect(self._sync_toggle_label)
        self.setContextMenu(menu)
        self._menu = menu
        self.activated.connect(self._on_activated)

    def context_menu(self) -> QMenu:
        """给宠物右键复用的菜单 取前先刷文案"""
        self._sync_toggle_label()
        return self._menu

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
                self.showMessage(title, body, mochi_icon(), msecs)
        except Exception:
            pass

    def retranslate(self) -> None:
        self.setToolTip(i18n.t("tray_tooltip"))
        for act, key in (
            (self._act_talk, "tray_talk"),
            (self._act_peek, "tray_peek"),
            (self._act_new_topic, "tray_new_topic"),
            (self._act_open, "tray_open_panel"),
            (self._act_quit, "tray_quit"),
        ):
            if act is not None:
                act.setText(i18n.t(key))
        self._sync_toggle_label()

    def _add(self, menu: QMenu, key: str, slot: Callable[[], None] | None) -> QAction | None:
        # slot 没给就不建返回 None
        if slot is None:
            return None
        action = QAction(i18n.t(key), menu)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action
