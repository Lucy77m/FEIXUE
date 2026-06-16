# author: bdth
# email: 2074055628@qq.com
# qt环境布置 压掉烦人警告 统一浅色调色板

from __future__ import annotations

import sys

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QColor, QPalette


# 半透明无边框窗反复刷新的 UpdateLayeredWindowIndirect、PNG 色彩配置的 iCCP——纯噪声 压掉
# (拆 mixin 时这个常量被漏掉了 导致 _filter 每条 Qt 消息都 NameError 反而更吵)
_SUPPRESSED_QT_WARNINGS = ("UpdateLayeredWindowIndirect", "iCCP")
_prev_qt_handler = None


def _install_qt_message_filter() -> None:
    global _prev_qt_handler

    def _filter(mode, context, message) -> None:
        if any(token in message for token in _SUPPRESSED_QT_WARNINGS):
            return
        if _prev_qt_handler is not None:
            _prev_qt_handler(mode, context, message)
        else:
            sys.stderr.write(message + "\n")

    _prev_qt_handler = qInstallMessageHandler(_filter)


def _light_palette() -> QPalette:
    """qt部件统一浅色"""
    p = QPalette()
    base = QColor("#ffffff")
    text = QColor("#3b3a4d")
    p.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f3fc"))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor("#f5f3fc"))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Highlight, QColor("#efecff"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#6a59f5"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#a8a6bc"))
    return p
