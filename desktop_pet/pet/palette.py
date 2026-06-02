# author: bdth
# email: 2074055628@qq.com
# 桌宠绘制用的调色板：定义墨色、肤色、描边及做梦时的彩色序列

from __future__ import annotations

from PySide6.QtGui import QColor

INK = QColor(30, 30, 34)
SKIN = QColor(250, 250, 252)
OUTLINE = QColor(46, 46, 54)


DREAM_COLORS = (
    QColor(236, 120, 150), QColor(120, 170, 235), QColor(240, 195, 90),
    QColor(140, 200, 150), QColor(180, 150, 220),
)
