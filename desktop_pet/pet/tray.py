# author: bdth
# email: 2074055628@qq.com
# 系统托盘图标与右键菜单（打开面板 / 退出）

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from desktop_pet import i18n
from desktop_pet.pet.icon import mochi_icon


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        on_open_panel: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__(mochi_icon())
        self.setToolTip(i18n.t("tray_tooltip"))
        self._on_open_panel = on_open_panel

        menu = QMenu()
        self._act_open = self._add(menu, i18n.t("tray_open_panel"), on_open_panel)
        menu.addSeparator()
        self._act_quit = self._add(menu, i18n.t("tray_quit"), on_quit)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)  # 左键单击/双击托盘图标 → 打开控制面板

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,      # 单击
            QSystemTrayIcon.ActivationReason.DoubleClick,  # 双击
        ):
            self._on_open_panel()

    def retranslate(self) -> None:
        self.setToolTip(i18n.t("tray_tooltip"))
        self._act_open.setText(i18n.t("tray_open_panel"))
        self._act_quit.setText(i18n.t("tray_quit"))

    @staticmethod
    def _add(menu: QMenu, text: str, slot: Callable[[], None]) -> QAction:
        action = QAction(text, menu)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action
