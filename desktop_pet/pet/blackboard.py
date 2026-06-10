# author: bdth
# email: 2074055628@qq.com
# 桌宠的"小黑板"浮窗:把 Markdown 渲染成粉笔字黑板,带展开/落灰动画

from __future__ import annotations

import random
import re

from PySide6.QtCore import Qt, QLineF, QRectF, QTimer
from PySide6.QtGui import (
    QAbstractTextDocumentLayout,
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QTextDocument,
    QTextFrameFormat,
    QTextOption,
    QTextTable,
)
from PySide6.QtWidgets import QWidget

from desktop_pet.pet.fx import ease_out_back, make_floating, place_beside_pet

_PAD = 20
_FRAME = 15
_SHADOW = 14
_TRAY_H = 13
_MAX_W = 340
_MAX_H = 560
_FONT_PX = 15
_CHALK = QColor(240, 244, 238)
_CHALK_LINE = QColor(150, 173, 161)

_DOC_CSS = """
h1 { font-size: 20px; font-weight: 700; margin: 2px 0 8px 0; }
h2 { font-size: 17px; font-weight: 700; margin: 6px 0 4px 0; }
h3 { font-size: 15px; font-weight: 700; margin: 5px 0 3px 0; }
p  { margin: 3px 0; }
ul, ol { margin: 2px 0; }
li { margin: 3px 0; }
th { font-weight: 700; }
code, pre { font-family: 'Cascadia Mono','Consolas',monospace; font-size: 13px; }
"""
_WOOD_LIGHT = QColor(154, 116, 74)
_WOOD_DARK = QColor(99, 68, 39)
_WOOD_EDGE = QColor(68, 46, 25)
_BOARD_TOP = QColor(43, 74, 58)
_BOARD_BOT = QColor(26, 49, 38)
# 黑板停留时长：底 2.8s 起，按内容高度线性加，封顶 8s —— 内容越多看的时间越长，但别赖太久。
_LINGER_BASE = 2800
_LINGER_PER_PX = 7.0
_LINGER_MAX = 8000

_FPS_MS = 1000 // 60
_PRESENT_DUR = 0.42
_DISMISS_DUR = 0.28
_REVEAL_PX_PER_S = 520.0
_REVEAL_MIN = 0.32
_REVEAL_MAX = 1.5
_REVEAL_START = 0.45
_DUST_PER_FRAME = 2
_DUST_GRAVITY = 0.05
_DUST_DECAY = 0.024

# 表格分隔行：第二行那条 |---|---| 才是判定锚点，光看首行有 | 会把普通句子里的竖线误当表格。
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}.*\|")
# 列表项首字符：连中文项目符号(•·‣)和"1、"这种全角顿号编号都认，不然中文列表整段当普通文本。
_LIST = re.compile(r"^\s*(?:[-*+•·‣]\s+|\d+[.)]\s+|\d+、\s*)\S")
_IMG = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")


def _fence(line: str) -> str | None:
    """两种围栏不能互闭，原样返回 ``` 或 ~~~ 好让起止配对。"""
    s = line.strip()
    if s.startswith("```"):
        return "```"
    if s.startswith("~~~"):
        return "~~~"
    return None


def parse_segments(text: str) -> list[tuple[str, str]]:
    """代码块/表格/图片/列表上黑板，其余进气泡。返回 (kind, 内容) 段序列。"""
    lines = text.split("\n")
    segments: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush() -> None:
        joined = "\n".join(buf).strip()
        if joined:
            segments.append(("text", joined))
        buf.clear()

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        fence = _fence(line)
        if fence:
            block = [line]
            i += 1
            while i < n and _fence(lines[i]) != fence:
                block.append(lines[i])
                i += 1
            if i < n:
                block.append(lines[i])
                i += 1
            flush()
            segments.append(("board", "\n".join(block)))
        elif "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            block = [line, lines[i + 1]]
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                block.append(lines[i])
                i += 1
            flush()
            segments.append(("board", "\n".join(block)))
        elif _IMG.match(line):
            flush()
            segments.append(("board", line.strip()))
            i += 1
        elif _LIST.match(line):
            block = [line]
            i += 1
            # 缩进续行(两空格起)也并进同一列表块，否则多行列表项会被气泡和黑板拦腰切开。
            while i < n and (_LIST.match(lines[i]) or (lines[i].startswith("  ") and lines[i].strip())):
                block.append(lines[i])
                i += 1
            flush()
            segments.append(("board", "\n".join(block)))
        else:
            buf.append(line)
            i += 1
    flush()
    return segments


def has_board(text: str) -> bool:
    """有没有该上黑板的东西。没有就只走气泡，省得空黑板乱晃。"""
    return any(kind == "board" for kind, _ in parse_segments(text))


class BlackBoard(QWidget):
    """粉笔字黑板浮窗。鼠标穿透、贴宠物摆，背景和粉笔字分两张 pixmap → 逐帧放大+擦显+落灰。"""

    def __init__(self) -> None:
        super().__init__()
        make_floating(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._font = QFont("Microsoft YaHei UI")
        self._font.setPixelSize(_FONT_PX)
        self._backdrop: QPixmap | None = None
        self._chalk: QPixmap | None = None
        self._ink_rect = QRectF()
        self._scale = 0.0
        self._target = 0.0
        self._reveal = 1.0
        self._reveal_dur = _REVEAL_MIN
        self._dust: list[list[float]] = []
        self._content_h = 0.0
        self._doc_scale = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def present(self, markdown: str, pet: QWidget, screen, animate: bool = True) -> None:
        """渲染并弹出。animate=False 直接定格，切内容时用，免得每段都重播一遍弹出动画。"""
        was_visible = self.isVisible()
        self._render(markdown)
        self.setFixedSize(self._backdrop.width(), self._backdrop.height())
        self._place(pet, screen)
        self._target = 1.0
        self._dust.clear()
        if animate:
            # 已经在显示就接着当前 scale 续放，别从 0 重弹 —— 连发两条时不会突兀地缩回去再长出来。
            self._scale = self._scale if was_visible else 0.0
            self._reveal = 0.0
            self._reveal_dur = min(_REVEAL_MAX, max(_REVEAL_MIN, self._content_h / _REVEAL_PX_PER_S))
        else:
            self._scale = 1.0
            self._reveal = 1.0
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start(_FPS_MS)
        self.update()

    def dismiss(self) -> None:
        self._target = 0.0
        if not self._timer.isActive():
            self._timer.start(_FPS_MS)

    def suggested_linger_ms(self) -> int:
        """自动收起前留多久，给外面调度用。跟内容高度挂钩，长文多留一会。"""
        return int(min(_LINGER_MAX, _LINGER_BASE + self._content_h * _LINGER_PER_PX))

    def _tick(self) -> None:
        """每帧推进动画。放大→擦字→落灰三件事按这顺序耦合，别拆。"""
        dt = _FPS_MS / 1000.0
        if self._target > 0.0:
            if self._scale < 1.0:
                self._scale = min(1.0, self._scale + dt / _PRESENT_DUR)
            # 等黑板长到差不多大(0.45)再擦字，太早写会跟着缩放一起变形、看着糊。
            if self._scale >= _REVEAL_START and self._reveal < 1.0:
                self._reveal = min(1.0, self._reveal + dt / self._reveal_dur)
                if self._reveal < 1.0:
                    self._shed_dust()
        else:
            self._scale = max(0.0, self._scale - dt / _DISMISS_DUR)
        self._step_dust()

        # 两个停表口：收起到看不见就 hide；或完全展开且灰落尽 —— 后者别漏判 dust，不然最后几粒灰会被冻住。
        if self._target == 0.0 and self._scale <= 0.001:
            self._timer.stop()
            self._dust.clear()
            self.hide()
        elif self._target > 0.0 and self._scale >= 1.0 and self._reveal >= 1.0 and not self._dust:
            self._timer.stop()
        self.update()

    def _shed_dust(self) -> None:
        """在擦字推进的那条横线(front)上撒几粒粉笔灰。每粒是 [x, y, vy, life, r]，纯列表省得建对象。"""
        front = self._ink_rect.top() + self._reveal * self._ink_rect.height()
        for _ in range(_DUST_PER_FRAME):
            x = self._ink_rect.left() + random.random() * self._ink_rect.width()
            self._dust.append([x, front, 0.3 + random.random() * 0.8, 1.0, 1.1 + random.random() * 1.7])

    def _step_dust(self) -> None:
        for speck in self._dust:
            speck[1] += speck[2]
            speck[2] += _DUST_GRAVITY
            speck[3] -= _DUST_DECAY
        self._dust = [s for s in self._dust if s[3] > 0.0]

    def follow(self, pet: QWidget, screen) -> None:
        if self.isVisible():
            self._place(pet, screen)

    def _place(self, pet: QWidget, screen) -> None:
        place_beside_pet(self, pet, screen, prefer="left")

    def _render(self, markdown: str) -> None:
        """markdown 排成两张 pixmap(木框背景 + 粉笔字)，顺手把尺寸/缩放/墨迹区都算好缓起来。"""
        doc = QTextDocument()
        doc.setDefaultFont(self._font)
        doc.setDefaultStyleSheet(_DOC_CSS)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(option)
        doc.setMarkdown(markdown)
        self._style_tables(doc)
        # 两遍量宽：先用 _MAX_W 排一遍拿 idealWidth(短内容的真实宽度)，再按它收窄，省得短句也撑满整块。
        doc.setTextWidth(_MAX_W)
        ideal = max(1.0, doc.idealWidth())
        doc.setTextWidth(ideal)
        size = doc.size()
        nat_w = max(1.0, size.width())
        nat_h = max(1.0, size.height())
        # 只按宽度约束缩放，绝不为"塞进固定高度"而把整块连字一起缩小（否则内容一长字就看不清）。
        # 内容更长就让黑板长高，封顶在屏幕可用高度的一定比例；再超出的由 _render_chalk 的 clip 裁掉。
        self._doc_scale = min(1.0, _MAX_W / nat_w)
        cw = nat_w * self._doc_scale
        screen = QGuiApplication.primaryScreen()
        avail_h = screen.availableGeometry().height() if screen is not None else 900
        max_h = max(_MAX_H, avail_h * 0.82 - (2 * _SHADOW + 2 * _FRAME + 2 * _PAD + _TRAY_H + 24))
        ch = min(nat_h * self._doc_scale, max_h)
        self._content_h = ch

        inner_w, inner_h = cw + 2 * _PAD, ch + 2 * _PAD
        frame_w, frame_h = inner_w + 2 * _FRAME, inner_h + 2 * _FRAME
        total_w = int(frame_w + 2 * _SHADOW)
        total_h = int(frame_h + 2 * _SHADOW + _TRAY_H)
        ox, oy = float(_SHADOW), float(_SHADOW)
        board = QRectF(ox + _FRAME, oy + _FRAME, inner_w, inner_h)
        self._ink_rect = QRectF(board.left() + _PAD, board.top() + _PAD, cw, ch)

        self._backdrop = self._render_backdrop(total_w, total_h, ox, oy, frame_w, frame_h, board, inner_w, inner_h)
        self._chalk = self._render_chalk(total_w, total_h, doc, cw, ch)

    def _render_backdrop(self, total_w, total_h, ox, oy, frame_w, frame_h, board, inner_w, inner_h) -> QPixmap:
        """不动的那层(投影/木框/石板/擦痕)，只在 _render 画一次，逐帧不重画。"""
        pixmap = QPixmap(total_w, total_h)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame_rect = QRectF(ox, oy, frame_w, frame_h)

        painter.setPen(Qt.PenStyle.NoPen)
        # 叠三层越来越淡的黑圆角当软投影 —— 比真高斯模糊便宜，肉眼也够。
        for dy, alpha in ((5, 46), (10, 28), (17, 14)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(frame_rect.translated(0, dy), 14, 14)

        tray = QRectF(ox + frame_w * 0.1, oy + frame_h - 6, frame_w * 0.8, _TRAY_H + 8)
        tray_grad = QLinearGradient(0, tray.top(), 0, tray.bottom())
        tray_grad.setColorAt(0.0, _WOOD_LIGHT)
        tray_grad.setColorAt(1.0, _WOOD_DARK)
        painter.setPen(QPen(_WOOD_EDGE, 1.5))
        painter.setBrush(tray_grad)
        painter.drawRoundedRect(tray, 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        chalk_y = tray.top() + tray.height() * 0.32
        painter.setBrush(QColor(244, 246, 240))
        painter.drawRoundedRect(QRectF(tray.left() + tray.width() * 0.16, chalk_y, tray.width() * 0.22, _TRAY_H * 0.42), 2, 2)
        painter.setBrush(QColor(66, 78, 92))
        painter.drawRoundedRect(QRectF(tray.right() - tray.width() * 0.32, chalk_y - 1, tray.width() * 0.18, _TRAY_H * 0.55), 2, 2)

        wood = QLinearGradient(0, oy, 0, oy + frame_h)
        wood.setColorAt(0.0, _WOOD_LIGHT.lighter(113))
        wood.setColorAt(0.12, _WOOD_LIGHT)
        wood.setColorAt(0.55, _WOOD_DARK.lighter(110))
        wood.setColorAt(1.0, _WOOD_DARK)
        painter.setPen(QPen(_WOOD_EDGE, 2))
        painter.setBrush(wood)
        painter.drawRoundedRect(frame_rect, 13, 13)
        painter.setPen(QPen(QColor(255, 238, 214, 55), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame_rect.adjusted(1.5, 1.5, -1.5, -1.5), 12, 12)

        slate = QLinearGradient(0, board.top(), 0, board.bottom())
        slate.setColorAt(0.0, _BOARD_TOP)
        slate.setColorAt(1.0, _BOARD_BOT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(slate)
        painter.drawRoundedRect(board, 6, 6)

        painter.save()
        painter.setClipRect(board.adjusted(2, 2, -2, -2))
        painter.setPen(QPen(QColor(232, 240, 234, 11), 9))
        painter.drawLine(QLineF(board.left() + inner_w * 0.10, board.top() + inner_h * 0.30,
                                board.left() + inner_w * 0.62, board.top() + inner_h * 0.24))
        painter.setPen(QPen(QColor(226, 236, 230, 9), 7))
        painter.drawLine(QLineF(board.left() + inner_w * 0.45, board.top() + inner_h * 0.66,
                                board.left() + inner_w * 0.92, board.top() + inner_h * 0.72))
        painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 226, 218, 13))
        painter.drawRoundedRect(QRectF(board.left() + 3, board.top() + 3, inner_w - 6, inner_h * 0.22), 5, 5)
        painter.setBrush(QColor(225, 232, 224, 16))
        painter.drawRoundedRect(QRectF(board.left() + 4, board.bottom() - inner_h * 0.18, inner_w - 8, inner_h * 0.15), 5, 5)
        painter.end()
        return pixmap

    def _render_chalk(self, total_w, total_h, doc: QTextDocument, cw, ch) -> QPixmap:
        """粉笔字单独一层，跟背景分开。逐行擦显靠 paintEvent 给这张图设 clip，背景始终全显。"""
        pixmap = QPixmap(total_w, total_h)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._ink_rect.left(), self._ink_rect.top())
        # 先 clip 到墨迹区再缩放画文档：超出可用高度的内容直接裁掉，不会糊到木框上。
        painter.setClipRect(QRectF(0, 0, cw, ch))
        painter.scale(self._doc_scale, self._doc_scale)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.ColorRole.Text, _CHALK)
        doc.documentLayout().draw(painter, ctx)
        painter.end()
        return pixmap

    @staticmethod
    def _style_tables(doc: QTextDocument) -> None:
        """给表格补粉笔色细边框。setMarkdown 默认不画线，不补就糊成一团。"""
        for child in doc.rootFrame().childFrames():
            if isinstance(child, QTextTable):
                fmt = child.format()
                fmt.setBorder(1)
                fmt.setBorderBrush(QBrush(_CHALK_LINE))
                fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                fmt.setBorderCollapse(True)
                fmt.setCellPadding(6)
                fmt.setCellSpacing(0)
                child.setFormat(fmt)

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._backdrop is None or self._scale <= 0.001:
            return
        # 进场用 ease_out_back 带点回弹(更俏皮)，收起用平方曲线干脆缩没 —— 弹出活泼、消失利落。
        display = self._scale * self._scale if self._target == 0.0 else ease_out_back(self._scale)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        painter.translate(w / 2, h / 2)
        painter.scale(display, display)
        painter.translate(-w / 2, -h / 2)

        painter.drawPixmap(0, 0, self._backdrop)

        # 粉笔字只露出 reveal 比例那条横线以上 —— 自上而下擦显的本体就这一刀 clip。
        painter.save()
        reveal_h = self._ink_rect.top() + self._reveal * self._ink_rect.height()
        painter.setClipRect(QRectF(0, 0, w, reveal_h))
        painter.drawPixmap(0, 0, self._chalk)
        painter.restore()

        if self._dust:
            painter.setPen(Qt.PenStyle.NoPen)
            for x, y, _vy, life, r in self._dust:
                painter.setBrush(QColor(244, 246, 240, int(150 * life)))
                painter.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
