# author: bdth
# email: 2074055628@qq.com
# 设置面板对话框 左侧导航右侧内容区 无边框可拖拽

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_pet import __version__, i18n, updater
from desktop_pet.docs import docs
from desktop_pet.eyes import detect
from desktop_pet.i18n import UI_LANGUAGES
from desktop_pet.pet.icon import mochi_icon
from desktop_pet.settings import Settings, THINK_PRESETS

_ACCENT = "#7c6cff"
_ACCENT_DEEP = "#6a59f5"
_FONT = "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
_STYLE = f"""
* {{ font-family: {_FONT}; }}
#card {{ background: #ffffff; border-radius: 18px; border: 1px solid #ecebf5; }}
#sidebar {{
    background: #f5f3fc;
    border-top-left-radius: 18px; border-bottom-left-radius: 18px;
    border-right: 1px solid #eeebf8;
}}
#brand {{ color: #3b3a4d; font-size: 16px; font-weight: 800; }}
#brandSub {{ color: #a8a6bc; font-size: 11px; letter-spacing: 3px; }}
QPushButton#nav {{
    text-align: left; background: transparent; color: #6b6a82; border: none;
    border-radius: 10px; padding: 9px 14px; font-size: 14px;
}}
QPushButton#nav:hover {{ background: #ece8f9; color: #3b3a4d; }}
QPushButton#nav[active="true"] {{ background: #efecff; color: {_ACCENT_DEEP}; font-weight: 700; }}
#close {{ color: #b6b4c8; font-size: 16px; font-weight: 600; border: none; background: transparent; border-radius: 8px; }}
#close:hover {{ background: #ef5d72; color: white; }}
QLabel {{ color: #4a4960; font-size: 13px; background: transparent; }}
#pageHint {{ color: #9b99ad; font-size: 12px; }}
#fieldLabel {{ color: #3b3a4d; font-size: 13px; font-weight: 600; }}
#help {{ color: #a8a6bc; font-size: 11px; }}
#scroll, #scrollBody {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px 0; }}
QScrollBar::handle:vertical {{ background: #dcd8ee; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QCheckBox {{ color: #4a4960; font-size: 13px; spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1.5px solid #cfcce0; border-radius: 6px; background: #ffffff; }}
QCheckBox::indicator:hover {{ border-color: {_ACCENT}; }}
QCheckBox::indicator:checked {{ background: {_ACCENT}; border-color: {_ACCENT}; image: none; }}
QLineEdit {{
    background: #f7f6fc; border: 1px solid #e6e3f1; border-radius: 10px;
    padding: 9px 12px; color: #3b3a4d; font-size: 13px; min-width: 240px;
    selection-background-color: {_ACCENT}; selection-color: white;
}}
QLineEdit:hover {{ border-color: #cdc7ea; }}
QLineEdit:focus {{ border: 1.5px solid {_ACCENT}; background: #ffffff; }}
QComboBox {{
    background: #f7f6fc; border: 1px solid #e6e3f1; border-radius: 10px;
    padding: 8px 12px; color: #3b3a4d; font-size: 13px; min-width: 150px;
}}
QComboBox:hover {{ border-color: #cdc7ea; }}
QComboBox:focus {{ border: 1.5px solid {_ACCENT}; background: #ffffff; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: #ffffff; border: 1px solid #e6e3f1; border-radius: 10px; padding: 4px;
    outline: none; selection-background-color: {_ACCENT}; selection-color: white;
}}
QComboBox QAbstractItemView::item {{ padding: 6px 10px; min-height: 22px; }}
QSlider::groove:horizontal {{ height: 4px; background: #e6e3f1; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ height: 4px; background: {_ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -7px 0; border-radius: 8px; background: {_ACCENT}; border: 3px solid #ffffff; }}
QSlider::handle:horizontal:hover {{ background: {_ACCENT_DEEP}; }}
#statusCard {{ background: #faf9fe; border: 1px solid #ecebf5; border-radius: 14px; }}
#stBig {{ color: #3b3a4d; font-size: 16px; font-weight: 700; }}
#aboutName {{ color: #3b3a4d; font-size: 32px; font-weight: 800; }}
#aboutGloss {{ color: #a8a6bc; font-size: 12px; letter-spacing: 2px; }}
#aboutRule {{ background: {_ACCENT}; border-radius: 2px; }}
#aboutSep {{ background: #ecebf5; border: none; }}
#aboutSub {{ color: #6b6a82; font-size: 13px; }}
#aboutDesc {{ color: #6b6a82; font-size: 13px; }}
#aboutChips {{ color: {_ACCENT}; font-size: 13px; font-weight: 600; }}
#aboutAuthor {{ color: #9b99ad; font-size: 12px; }}
#aboutMeta {{ color: #b6b4c8; font-size: 12px; }}
QPushButton#save {{ background: {_ACCENT}; color: white; border: none; border-radius: 10px; padding: 9px 26px; font-size: 14px; font-weight: 600; }}
QPushButton#save:hover {{ background: {_ACCENT_DEEP}; }}
QPushButton#cancel {{ background: transparent; color: #7a7990; border: 1px solid #e0ddee; border-radius: 10px; padding: 9px 20px; font-size: 14px; }}
QPushButton#cancel:hover {{ background: #f2f0fa; border-color: #cdc7ea; }}
QPushButton#reset {{ background: transparent; color: #ec5d72; border: 1px solid #f3cdd5; border-radius: 10px; padding: 7px 16px; font-size: 13px; }}
QPushButton#reset:hover {{ background: #fdeef0; border-color: #ec5d72; }}
QPushButton#reset[armed="true"] {{ background: #ec5d72; color: white; border-color: #ec5d72; font-weight: 600; }}
"""


_TOGGLE_ON_QSS = (
    f"QPushButton {{ background: {_ACCENT}; color: white; border: none; border-radius: 12px;"
    " padding: 13px; font-size: 15px; font-weight: 700; }"
    f" QPushButton:hover {{ background: {_ACCENT_DEEP}; }}"
)
_TOGGLE_OFF_QSS = (
    "QPushButton { background: #ffffff; color: #ec5d72; border: 1.5px solid #f3cdd5;"
    " border-radius: 12px; padding: 13px; font-size: 15px; font-weight: 700; }"
    " QPushButton:hover { background: #fdeef0; }"
)


_SEG_ON = (
    f"QPushButton {{ background: {_ACCENT}; color: white; border: 1px solid {_ACCENT};"
    " border-radius: 9px; padding: 7px 8px; font-size: 13px; font-weight: 700; }"
)
_SEG_OFF = (
    "QPushButton { background: #f3f1fa; color: #6b6a82; border: 1px solid #e6e3f1;"
    " border-radius: 9px; padding: 7px 8px; font-size: 13px; }"
    " QPushButton:hover { background: #ece8f9; color: #3b3a4d; }"
)


class _Segmented(QWidget):
    """一排互斥按钮的分段选择器"""

    def __init__(self, items: list[tuple[str, str]], on_change: "Callable[[str], None] | None" = None) -> None:
        super().__init__()
        self._items = items
        self._on_change = on_change
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._btns: list[QPushButton] = []
        for i, (_data, label) in enumerate(items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(_SEG_OFF)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn, i)
            row.addWidget(btn, 1)
            self._btns.append(btn)
        self._group.buttonToggled.connect(lambda btn, on: btn.setStyleSheet(_SEG_ON if on else _SEG_OFF))
        self._group.buttonClicked.connect(self._on_clicked)
        if self._btns:
            self._btns[0].setChecked(True)

    def _on_clicked(self, _btn: QPushButton) -> None:
        if self._on_change is not None:
            self._on_change(self.currentData())

    def setCurrentData(self, data: str) -> None:
        for i, (d, _label) in enumerate(self._items):
            if d == data:
                self._btns[i].setChecked(True)
                return

    def currentData(self) -> str | None:
        i = self._group.checkedId()
        return self._items[i][0] if 0 <= i < len(self._items) else None


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageHint")
    label.setWordWrap(True)
    return label


class ControlPanel(QDialog):
    _update_checked = Signal(object)
    _gui_model_done = Signal(str)
    _gui_progress = Signal(int)

    def __init__(self, settings: Settings, on_reset: Callable[[], None] | None = None,
                 on_apply: Callable[[], None] | None = None,
                 status_provider: Callable[[], dict] | None = None,
                 on_toggle_active: Callable[[], None] | None = None,
                 bond_provider: Callable[[], dict] | None = None,
                 on_set_language: Callable[[str], None] | None = None,
                 hotkey_status_provider: Callable[[], dict] | None = None,
                 on_new_topic: Callable[[], None] | None = None,
                 intro: "tuple | None" = None) -> None:
        """设置面板 交互全靠注入的回调和provider"""
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._settings = settings
        self._on_reset = on_reset
        self._on_new_topic = on_new_topic
        self._on_apply = on_apply
        self._status_provider = status_provider
        self._on_toggle_active = on_toggle_active
        self._has_home = status_provider is not None
        self._bond_provider = bond_provider
        self._has_bond = bond_provider is not None
        self._on_set_language = on_set_language
        self._hotkey_status_provider = hotkey_status_provider
        self._drag_offset = QPoint()
        self._lang = settings.ui_language if settings.ui_language in UI_LANGUAGES else "中文"
        self.setWindowTitle(self._t("panel_title"))
        self.setWindowIcon(mochi_icon())

        card = QFrame(objectName="card")
        card.setStyleSheet(_STYLE)
        card.setFixedSize(800, 600)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(52)
        shadow.setColor(QColor(90, 80, 150, 90))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        self._build_fields(settings)

        page_specs: list[tuple[str, object]] = []
        if self._has_home:
            page_specs.append(("tab_home", self._build_home_page))
        if self._has_bond:
            page_specs.append(("tab_bond", self._build_bond_page))
        page_specs += [
            ("tab_docs", self._build_docs_page),
            ("tab_connect", self._build_connect_page),
            ("tab_chat", self._build_chat_page),
            ("tab_interact", self._build_interact_page),
            ("tab_perm", self._build_perm_page),
            ("tab_about", self._build_about_page),
        ]
        self._page_keys = [k for k, _ in page_specs]

        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(170)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 22, 14, 16)
        side.setSpacing(4)
        avatar = QLabel()
        avatar.setPixmap(mochi_icon().pixmap(QSize(46, 46)))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QLabel("Mochi", objectName="brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_sub = QLabel("もち · 麻薯", objectName="brandSub")
        brand_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(avatar)
        side.addWidget(brand)
        side.addWidget(brand_sub)
        side.addSpacing(18)

        self._tabs: list[QPushButton] = []
        self._stack = QStackedWidget()
        self._footerless: set[int] = set()
        for index, (key, builder) in enumerate(page_specs):
            btn = QPushButton(self._t(key), objectName="nav")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, i=index: self._switch(i))
            side.addWidget(btn)
            self._tabs.append(btn)
            self._stack.addWidget(builder())
            if key in ("tab_home", "tab_bond", "tab_about", "tab_docs"):
                self._footerless.add(index)  # 没表单的页藏掉底部按钮条
        side.addStretch(1)
        _lang_short = {"中文": "中", "English": "EN", "日本語": "日"}
        side.addWidget(QLabel(self._t("lbl_ui_lang"), objectName="help"))
        self._ui_language = _Segmented(
            [(lang, _lang_short.get(lang, lang)) for lang in UI_LANGUAGES],
            on_change=self._on_lang_clicked,
        )
        self._ui_language.setCurrentData(self._lang)
        side.addWidget(self._ui_language)

        close = QPushButton("×", objectName="close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFixedSize(26, 26)
        close.clicked.connect(self.reject)
        topbar = QHBoxLayout()
        topbar.addStretch(1)
        topbar.addWidget(close, alignment=Qt.AlignmentFlag.AlignTop)

        self._save_btn = QPushButton(self._t("save"), objectName="save")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        cancel = QPushButton(self._t("cancel"), objectName="cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        self._footer = QWidget()
        footer_row = QHBoxLayout(self._footer)
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.addStretch(1)
        footer_row.addWidget(cancel)
        footer_row.addWidget(self._save_btn)

        content = QWidget()
        content_col = QVBoxLayout(content)
        content_col.setContentsMargins(22, 14, 22, 18)
        content_col.setSpacing(12)
        content_col.addLayout(topbar)
        content_col.addWidget(self._stack)
        content_col.addWidget(self._footer)

        body = QHBoxLayout(card)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(sidebar)
        body.addWidget(content, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addWidget(card)

        self._switch(0)
        if self._has_home:
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._refresh_status)
            self._status_timer.start(1500)
            self._refresh_status()

        self._intro_overlay: QLabel | None = None
        self._intro_started = False
        if intro is not None:
            # 上一帧截图盖最上面占位 showEvent里再淡出
            pixmap, geom = intro
            self.setGeometry(geom)
            self._intro_overlay = QLabel(self)
            self._intro_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._intro_overlay.setPixmap(pixmap)
            self._intro_overlay.setGeometry(self.rect())
            self._intro_effect = QGraphicsOpacityEffect(self._intro_overlay)
            self._intro_effect.setOpacity(1.0)
            self._intro_overlay.setGraphicsEffect(self._intro_effect)
            self._intro_overlay.raise_()

    def showEvent(self, event) -> None:
        # 真正显示出来才启动淡出 只跑一次
        super().showEvent(event)
        if self._intro_overlay is None or self._intro_started:
            return
        self._intro_started = True
        self._intro_overlay.setGeometry(self.rect())
        self._intro_overlay.raise_()
        anim = QPropertyAnimation(self._intro_effect, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self._intro_overlay.deleteLater)
        self._intro_anim = anim
        anim.start()

    def snapshot_for_transition(self) -> "tuple":
        return (self.grab(), self.geometry())

    def _t(self, key: str) -> str:
        return i18n.t(key, self._lang)

    @staticmethod
    def _fmt_tok(n: int) -> str:
        """token数压成短样"""
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)

    def _refresh_usage(self) -> None:
        try:
            from desktop_pet.usage import meter  # 延迟import
            _session, today = meter.snapshot()
            self._usage_label.setText(self._t("usage_fmt").format(
                i=self._fmt_tok(today["input"]), o=self._fmt_tok(today["output"]),
                c=self._fmt_tok(today["cached"]), n=today["calls"],
            ))
        except Exception:
            self._usage_label.setText("")

    def _build_fields(self, settings: Settings) -> None:
        """一次性建好所有输入控件"""
        self._api_key = QLineEdit(settings.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._base_url = QLineEdit(settings.base_url)
        self._model = QLineEdit(settings.model)
        self._embed_model = QLineEdit(settings.embed_model)
        self._proxy = QLineEdit(settings.proxy)
        self._proxy.setPlaceholderText("http://127.0.0.1:7897")
        self._history_tokens = QLineEdit(str(settings.history_tokens))
        self._history_tokens.setPlaceholderText(self._t("ph_ctx"))
        self._subagent_model = QLineEdit(settings.subagent_model)
        self._subagent_model.setPlaceholderText(self._t("ph_submodel"))
        self._usage_label = QLabel("")
        self._usage_label.setWordWrap(True)
        self._usage_label.setObjectName("hint")
        self._refresh_usage()
        self._language = QLineEdit(settings.language)
        self._language.setPlaceholderText(self._t("ph_reply_lang"))
        self._allow_web = QCheckBox(self._t("cb_web"))
        self._allow_control = QCheckBox(self._t("cb_control"))
        self._allow_shell = QCheckBox(self._t("cb_shell"))
        self._allow_web.setChecked(settings.allow_web)
        self._allow_control.setChecked(settings.allow_control)
        self._allow_shell.setChecked(settings.allow_shell)
        self._watch = QCheckBox(self._t("cb_watch"))
        self._watch.setChecked(settings.watch_screen)
        self._clip_sampler = QCheckBox(self._t("cb_clip_sampler"))
        self._clip_sampler.setChecked(settings.clip_sampler)
        self._clip_sampler.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clip_alchemy = QCheckBox(self._t("cb_clip_alchemy"))
        self._clip_alchemy.setChecked(settings.clip_alchemy)
        self._clip_alchemy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._temperature = QSlider(Qt.Orientation.Horizontal)
        self._temperature.setRange(0, 200)
        self._temperature.setValue(int(round(settings.temperature * 100)))
        self._temp_label = QLabel(f"{settings.temperature:.2f}")
        self._temperature.valueChanged.connect(
            lambda v: self._temp_label.setText(f"{v / 100:.2f}")
        )
        self._autonomy = _Segmented([(value, self._t(label_key)) for value, label_key in i18n.AUTONOMY_LABEL_KEYS])
        self._autonomy.setCurrentData(settings.autonomy)
        self._think_level = _Segmented([(value, self._t(label_key)) for value, label_key in i18n.THINK_LEVEL_KEYS])
        self._think_level.setCurrentData(settings.think_level)
        self._proactive_enabled = QCheckBox(self._t("cb_proactive"))
        self._proactive_enabled.setChecked(settings.proactive_enabled)
        self._proactive_enabled.setCursor(Qt.CursorShape.PointingHandCursor)
        self._weather_cb = QCheckBox(self._t("cb_weather"))
        self._weather_cb.setChecked(settings.weather_enabled)
        self._weather_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        # 听觉 按住说话和唤醒词 模型按需下载
        self._hear_cb = QCheckBox(self._t("cb_hear"))
        self._hear_cb.setChecked(settings.hear_enabled)
        self._hear_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_cb = QCheckBox(self._t("cb_wake"))
        self._wake_cb.setChecked(settings.wake_enabled)
        self._wake_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hear_dl_label = QLabel("")
        self._hear_dl_btn = QPushButton(self._t("btn_hear_dl"), objectName="cancel")
        self._hear_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hear_dl_btn.clicked.connect(self._on_hear_download)
        self._hear_dl_timer = QTimer(self)
        self._hear_dl_timer.timeout.connect(self._refresh_hear_status)
        self._hear_dl_timer.start(600)
        self._refresh_hear_status()
        self._proactive_level = _Segmented([(value, self._t(label_key)) for value, label_key in i18n.PROACTIVE_LABEL_KEYS])
        self._proactive_level.setCurrentData(settings.proactive_level)
        self._hk_summon = QKeySequenceEdit(QKeySequence(settings.hotkey_summon))
        self._hk_ask = QKeySequenceEdit(QKeySequence(settings.hotkey_ask))
        self._hk_quick = QKeySequenceEdit(QKeySequence(settings.hotkey_quick))
        self._hk_talk = QKeySequenceEdit(QKeySequence(settings.hotkey_talk))
        self._hk_status_labels: dict = {}

    def _scroll_page(self, hint_text: str) -> tuple[QWidget, QVBoxLayout]:
        """造提示行加滚动内容区的页面壳"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(2, 0, 2, 0)
        col.setSpacing(10)
        col.addWidget(_hint(hint_text))
        body = QWidget(objectName="scrollBody")
        fields = QVBoxLayout(body)
        fields.setContentsMargins(0, 6, 12, 8)
        fields.setSpacing(18)
        scroll = QScrollArea(objectName="scroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(452)  # 写死高度卡住卡片内沿
        scroll.viewport().setObjectName("scrollViewport")
        scroll.viewport().setStyleSheet("#scrollViewport { background: transparent; }")  # 带选择器 不然会级联盖掉子控件背景
        col.addWidget(scroll)
        return page, fields

    def _field(self, label_key: str, control, help_key: str) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(QLabel(self._t(label_key), objectName="fieldLabel"))
        if isinstance(control, QWidget):
            v.addWidget(control)
        else:
            v.addLayout(control)
        tip = QLabel(self._t(help_key), objectName="help")
        tip.setWordWrap(True)
        v.addWidget(tip)
        return box

    def _check_field(self, checkbox: QCheckBox, help_key: str) -> QWidget:
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(checkbox)
        tip = QLabel(self._t(help_key), objectName="help")
        tip.setWordWrap(True)
        tip.setContentsMargins(27, 0, 0, 0)  # 左缩27px让说明跟勾选文字对齐
        v.addWidget(tip)
        return box

    def _status_row(self, title: str, value: QLabel) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        cap = QLabel(title, objectName="help")
        v.addWidget(cap)
        value.setWordWrap(True)
        v.addWidget(value)
        return box

    def _build_home_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_home"))
        status_card = QFrame(objectName="statusCard")
        cl = QVBoxLayout(status_card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)
        self._home_state = QLabel("—", objectName="stBig")
        self._home_mood = QLabel("—")
        self._home_mem = QLabel("—")
        self._home_proactive = QLabel("—")
        self._home_interface = QLabel("—")
        cl.addWidget(self._home_state)
        cl.addWidget(self._status_row(self._t("home_mood"), self._home_mood))
        cl.addWidget(self._status_row(self._t("home_memory"), self._home_mem))
        cl.addWidget(self._status_row(self._t("home_proactive"), self._home_proactive))
        cl.addWidget(self._status_row(self._t("home_interface"), self._home_interface))
        body.addWidget(status_card)

        self._toggle_btn = QPushButton("—")
        self._toggle_btn.setStyleSheet(_TOGGLE_ON_QSS)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setMinimumHeight(48)
        self._toggle_btn.clicked.connect(self._toggle_clicked)
        body.addSpacing(10)
        body.addWidget(self._toggle_btn)

        if self._on_new_topic is not None:
            self._new_topic_btn = QPushButton(self._t("new_topic_btn"), objectName="cancel")
            self._new_topic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._new_topic_btn.setMinimumHeight(40)
            self._new_topic_btn.clicked.connect(self._on_new_topic_clicked)
            topic_help = QLabel(self._t("help_new_topic"), objectName="help")
            topic_help.setWordWrap(True)
            body.addSpacing(8)
            body.addWidget(self._new_topic_btn)
            body.addWidget(topic_help)
        body.addStretch(1)
        return page

    def _refresh_status(self) -> None:
        """定时拉宠物现状刷到主页"""
        if not self._status_provider:
            return
        try:
            s = self._status_provider()
        except Exception:
            return
        self._home_state.setText(self._t("st_" + str(s.get("state", "idle"))))
        mood = self._t("mood_" + str(s.get("mood", "content")))
        rap = int(round(float(s.get("rapport", 0.0)) * 100))
        self._home_mood.setText(f"{mood} · {self._t('home_intimacy')} {rap}%")
        self._home_mem.setText(self._t("home_mem_fmt").format(
            exp=s.get("experiences", 0), docs=s.get("docs", 0),
            jr=s.get("journal", 0), sk=s.get("skills", 0)))
        self._home_proactive.setText(self._t("home_proactive_fmt").format(
            n=s.get("proactive_today", 0), cap=s.get("proactive_cap", 0)))
        model = s.get("model") or "—"
        cfg = self._t("home_configured") if s.get("configured") else self._t("home_unconfigured")
        self._home_interface.setText(f"{cfg} · {model}")
        shown = bool(s.get("shown", False))
        self._toggle_btn.setText(self._t("home_power_off") if shown else self._t("home_power_on"))
        self._toggle_btn.setStyleSheet(_TOGGLE_OFF_QSS if shown else _TOGGLE_ON_QSS)

    def _toggle_clicked(self) -> None:
        if self._on_toggle_active is not None:
            self._on_toggle_active()
        self._refresh_status()

    def _on_lang_clicked(self, lang: str) -> None:
        if self._on_set_language is not None:
            self._on_set_language(lang)

    def _on_hear_download(self) -> None:
        from desktop_pet import hearing
        hearing.start_download(self._settings.proxy)
        self._refresh_hear_status()

    def _refresh_hear_status(self) -> None:
        """轮询听觉模型状态 更新标签和按钮"""
        from desktop_pet import hearing
        st = hearing.download_status()
        if st["state"] == "ready":
            self._hear_dl_label.setText(self._t("hear_dl_ready"))
            self._hear_dl_btn.hide()
        elif st["state"] == "downloading":
            self._hear_dl_label.setText(self._t("hear_dl_ing").format(pct=int(st["pct"] * 100)))
            self._hear_dl_btn.setEnabled(False)
        elif st["state"] == "error":
            self._hear_dl_label.setText(self._t("hear_dl_err").format(msg=st["msg"]))
            self._hear_dl_btn.setEnabled(True)
            self._hear_dl_btn.setText(self._t("btn_hear_retry"))
            self._hear_dl_btn.show()
        else:
            self._hear_dl_label.setText(self._t("hear_dl_none"))
            self._hear_dl_btn.setEnabled(True)
            self._hear_dl_btn.show()

    def _section_block(self, title: str, value: QLabel) -> QFrame:
        card = QFrame(objectName="statusCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(6)
        v.addWidget(QLabel(title, objectName="fieldLabel"))
        value.setWordWrap(True)
        v.addWidget(value)
        return card

    def _build_bond_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_bond"))
        self._bond_stat = QLabel("—", objectName="stBig")
        self._bond_stat.setWordWrap(True)
        body.addWidget(self._bond_stat)
        self._bond_persona = QLabel("—")
        body.addWidget(self._section_block(self._t("bond_persona"), self._bond_persona))
        self._bond_prefs = QLabel("—")
        body.addWidget(self._section_block(self._t("bond_prefs"), self._bond_prefs))
        self._bond_exp = QLabel("—")
        body.addWidget(self._section_block(self._t("bond_exp"), self._bond_exp))
        self._bond_diary = QLabel("—")
        self._bond_diary.setWordWrap(True)
        body.addWidget(self._section_block(self._t("bond_diary"), self._bond_diary))
        body.addStretch(1)

        if self._on_reset is not None:
            self._reset_btn = QPushButton(self._t("reset_btn"), objectName="reset")
            self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._reset_armed = False
            self._reset_btn.clicked.connect(self._on_reset_clicked)
            reset_help = QLabel(self._t("help_reset"), objectName="help")
            reset_help.setWordWrap(True)
            body.addWidget(self._reset_btn)
            body.addWidget(reset_help)
        return page

    def _refresh_bond(self) -> None:
        if not self._bond_provider:
            return
        try:
            s = self._bond_provider()
        except Exception:
            return
        rap = int(round(float(s.get("rapport", 0.0)) * 100))
        eaten = ""
        if s.get("files_eaten"):
            eaten = self._t("bond_eaten_fmt").format(n=s.get("files_eaten", 0), size=s.get("eaten_human", "0B"))
        self._bond_stat.setText(self._t("bond_stat_fmt").format(
            days=s.get("days", 0), n=s.get("interactions", 0), rap=rap, sk=s.get("skills", 0), eaten=eaten))
        portrait = (s.get("persona") or "").strip()
        self._bond_persona.setText(portrait or self._t("bond_persona_empty"))
        prefs = s.get("preferences") or []
        env = s.get("env") or []
        pref_lines = [f"· {k}：{v}" for k, v in prefs] + [f"· {k} = {v}" for k, v in env]
        self._bond_prefs.setText("\n".join(pref_lines) if pref_lines else self._t("bond_empty"))
        exps = s.get("experiences") or []
        self._bond_exp.setText("\n".join(f"· {e}" for e in exps) if exps else self._t("bond_empty"))
        diary = s.get("journal") or []
        if diary:
            entries = [f"{(d.get('when') or '').strip()}　{(d.get('text') or '').strip()}".strip() for d in diary]
            self._bond_diary.setText("\n\n".join(e for e in entries if e))
        else:
            self._bond_diary.setText(self._t("bond_diary_empty"))

    def _build_docs_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_docs"))
        add = QPushButton(self._t("docs_add"), objectName="nav")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self._add_docs)
        body.addWidget(add)
        self._docs_box = QVBoxLayout()
        self._docs_box.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self._docs_box)
        body.addWidget(holder)
        body.addStretch(1)
        return page

    def _refresh_docs(self) -> None:
        while self._docs_box.count():
            item = self._docs_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        try:
            items = docs.sources()
        except Exception:
            items = []
        if not items:
            self._docs_box.addWidget(QLabel(self._t("docs_empty"), objectName="help"))
            return
        for source, name, chunks in items:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            h.addWidget(QLabel(f"{name}　·　{self._t('docs_chunks_fmt').format(n=chunks)}"), 1)
            dele = QPushButton(self._t("docs_del"), objectName="reset")
            dele.setCursor(Qt.CursorShape.PointingHandCursor)
            dele.clicked.connect(lambda _c=False, s=source, b=dele: self._del_doc(s, b))
            h.addWidget(dele)
            self._docs_box.addWidget(row)

    def _del_doc(self, source: str, btn: QPushButton) -> None:
        """删知识库点两下 第一下armed第二下真删"""
        if not btn.property("armed"):
            btn.setProperty("armed", "true")
            btn.setText(self._t("docs_del_arm"))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            return
        try:
            docs.forget_exact(source)
        except Exception:
            pass
        self._refresh_docs()

    def _add_docs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, self._t("docs_add"), "",
            "Docs (*.txt *.md *.rst *.pdf *.py *.js *.ts *.json *.yaml *.csv *.html *.java *.go *.rs *.c *.cpp *.sql *.vue);;All files (*.*)",
        )
        if not paths:
            return
        def work() -> None:
            for p in paths:
                try:
                    docs.ingest(p)
                except Exception:
                    pass
        try:
            threading.Thread(target=work, daemon=True, name="panel-ingest").start()
        except RuntimeError:
            return
        QTimer.singleShot(3500, self._refresh_docs)  # 后台入库 延时后再刷列表

    def _build_connect_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_connect"))
        body.addWidget(self._field("lbl_api_key", self._api_key, "help_api_key"))
        body.addWidget(self._field("lbl_base_url", self._base_url, "help_base_url"))
        body.addWidget(self._field("lbl_model", self._model, "help_model"))
        body.addWidget(self._field("lbl_submodel", self._subagent_model, "help_submodel"))
        body.addWidget(self._field("lbl_ctx", self._history_tokens, "help_ctx"))
        body.addWidget(self._field("lbl_embed", self._embed_model, "help_embed"))
        body.addWidget(self._field("lbl_proxy", self._proxy, "help_proxy"))
        body.addWidget(self._usage_label)
        body.addStretch(1)
        return page

    def _build_chat_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_chat"))
        body.addWidget(self._field("lbl_reply_lang", self._language, "help_reply_lang"))
        temp_row = QHBoxLayout()
        temp_row.setSpacing(10)
        temp_row.addWidget(self._temperature, 1)
        temp_row.addWidget(self._temp_label)
        body.addWidget(self._field("lbl_temp", temp_row, "help_temp"))
        body.addWidget(self._field("lbl_autonomy", self._autonomy, "help_autonomy"))
        body.addWidget(self._field("lbl_think_level", self._think_level, "help_think_level"))
        body.addWidget(self._check_field(self._proactive_enabled, "help_proactive"))
        body.addWidget(self._field("lbl_proactive_freq", self._proactive_level, "help_proactive_freq"))
        body.addWidget(self._check_field(self._weather_cb, "help_weather"))
        body.addStretch(1)
        return page

    def _build_interact_page(self) -> QWidget:
        """召唤和语音这类输入方式 跟性格表现分开放"""
        page, body = self._scroll_page(self._t("hint_interact"))
        body.addWidget(self._build_hotkeys_block())
        body.addWidget(self._check_field(self._hear_cb, "help_hear"))
        body.addWidget(self._check_field(self._wake_cb, "help_wake"))
        hear_row = QHBoxLayout()
        hear_row.setSpacing(8)
        hear_row.addWidget(self._hear_dl_label, 1)
        hear_row.addWidget(self._hear_dl_btn)
        body.addWidget(self._field("lbl_hear_model", hear_row, "help_hear_model"))
        body.addStretch(1)
        return page

    def _build_hotkeys_block(self) -> QWidget:
        card = QFrame(objectName="statusCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)
        v.addWidget(QLabel(self._t("sec_hotkeys"), objectName="fieldLabel"))
        v.addWidget(self._hotkey_row("lbl_hk_summon", self._hk_summon, "summon"))
        v.addWidget(self._hotkey_row("lbl_hk_ask", self._hk_ask, "ask"))
        v.addWidget(self._hotkey_row("lbl_hk_quick", self._hk_quick, "quick"))
        v.addWidget(self._hotkey_row("lbl_hk_talk", self._hk_talk, "talk"))
        help_l = QLabel(self._t("help_hotkeys"), objectName="help")
        help_l.setWordWrap(True)
        v.addWidget(help_l)
        return card

    def _hotkey_row(self, label_key: str, edit: QKeySequenceEdit, action: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        name = QLabel(self._t(label_key))
        name.setFixedWidth(92)
        h.addWidget(name)
        edit.setMaximumWidth(180)
        h.addWidget(edit, 1)
        st = QLabel("—", objectName="help")
        st.setFixedWidth(70)
        self._hk_status_labels[action] = st
        h.addWidget(st)
        return row

    def _refresh_hotkey_status(self) -> None:
        if not self._hotkey_status_provider:
            return
        try:
            status = self._hotkey_status_provider() or {}
        except Exception:
            return
        for action, label in self._hk_status_labels.items():
            if action not in status:
                label.setText("—")
            else:
                label.setText(self._t("hk_ok") if status[action] else self._t("hk_taken"))

    def _build_perm_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_perm"))
        body.addWidget(self._check_field(self._allow_web, "help_web"))
        body.addWidget(self._check_field(self._allow_control, "help_control"))
        body.addWidget(self._check_field(self._allow_shell, "help_shell"))
        body.addWidget(self._check_field(self._watch, "help_watch"))
        body.addWidget(self._check_field(self._clip_sampler, "help_clip_sampler"))
        body.addWidget(self._check_field(self._clip_alchemy, "help_clip_alchemy"))
        body.addWidget(self._build_gui_model_block())
        body.addStretch(1)
        return page

    def _build_gui_model_block(self) -> QWidget:
        """视觉元素检测器的下载状态卡"""
        card = QFrame(objectName="statusCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)
        v.addWidget(QLabel(self._t("gui_model_title"), objectName="fieldLabel"))
        hint = QLabel(self._t("gui_model_hint"), objectName="help")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self._gui_btn = QPushButton(self._t("gui_model_btn"), objectName="cancel")
        self._gui_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gui_btn.clicked.connect(self._on_gui_model)
        v.addWidget(self._gui_btn)
        self._gui_status = QLabel("", objectName="help")
        self._gui_status.setWordWrap(True)
        v.addWidget(self._gui_status)
        self._gui_downloading = False
        self._gui_cancel = threading.Event()  # 取消靠这个event通知下载线程
        self._gui_model_done.connect(self._render_gui_model)
        self._gui_progress.connect(self._on_gui_progress)
        if detect.available():
            self._gui_status.setText(self._gui_on_text())
            self._gui_btn.setEnabled(False)
        return card

    def _on_gui_progress(self, p: int) -> None:
        # 已点取消就不再刷进度
        if self._gui_cancel.is_set():
            return
        self._gui_status.setText(self._t("gui_model_downloading") + f" {p}%")

    def _gui_on_text(self) -> str:
        """已装好的状态文案 拼上实际provider"""
        labels = {
            "DmlExecutionProvider": "GPU · DirectML",
            "CUDAExecutionProvider": "GPU · CUDA",
            "CPUExecutionProvider": "CPU",
        }
        tag = labels.get(detect.active_provider(), "")
        base = self._t("gui_model_on")
        return f"{base} · {tag}" if tag else base

    def _build_about_page(self) -> QWidget:
        def label(text: str, name: str, wrap: bool = False) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(wrap)
            return lbl

        def rule(name: str, w: int, h: int) -> QHBoxLayout:
            bar = QFrame(objectName=name)
            bar.setFixedSize(w, h)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(bar)
            row.addStretch(1)
            return row

        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(22, 10, 22, 8)
        col.setSpacing(7)
        col.addStretch(1)
        col.addWidget(label("Mochi", "aboutName"))
        col.addWidget(label("もち · 麻薯", "aboutGloss"))
        col.addWidget(label(f"v{__version__}", "aboutMeta"))
        col.addSpacing(6)
        col.addLayout(rule("aboutRule", 56, 3))
        col.addSpacing(10)
        col.addWidget(label(self._t("about_sub"), "aboutSub"))
        col.addSpacing(4)
        col.addWidget(label(self._t("about_desc"), "aboutDesc", wrap=True))
        col.addSpacing(8)
        col.addWidget(label(self._t("about_chips"), "aboutChips"))
        col.addStretch(1)

        col.addLayout(rule("aboutSep", 220, 1))
        col.addSpacing(8)
        col.addWidget(label(self._t("about_made_by"), "aboutAuthor"))
        col.addWidget(label(self._t("about_meta"), "aboutMeta"))
        gh = QLabel(f'<a href="https://github.com/dulaiduwang003/MOCHI" style="color: {_ACCENT}; text-decoration: none;">GitHub · dulaiduwang003/MOCHI</a>')
        gh.setObjectName("aboutMeta")
        gh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gh.setOpenExternalLinks(True)
        gh.setCursor(Qt.CursorShape.PointingHandCursor)
        col.addSpacing(3)
        col.addWidget(gh)

        col.addSpacing(8)
        self._check_btn = QPushButton(self._t("btn_check_update"), objectName="cancel")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self._on_check_update)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self._check_btn)
        btn_row.addStretch(1)
        col.addLayout(btn_row)
        self._update_status = QLabel("", objectName="aboutMeta")
        self._update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_status.setWordWrap(True)
        self._update_status.setOpenExternalLinks(True)
        col.addWidget(self._update_status)
        self._update_checked.connect(self._render_update)

        scroll = QScrollArea(objectName="scroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("scrollViewport")
        scroll.viewport().setStyleSheet("#scrollViewport { background: transparent; }")  # 带选择器 不然会级联盖掉子控件背景
        return scroll

    def _on_gui_model(self) -> None:
        """按钮三态 已装好置灰 下载中变取消 没装开下"""
        if detect.available():
            self._gui_status.setText(self._t("gui_model_on"))
            self._gui_btn.setEnabled(False)
            return
        if self._gui_downloading:
            self._gui_cancel.set()
            self._gui_btn.setEnabled(False)
            self._gui_status.setText(self._t("gui_model_cancelling"))
            return
        self._gui_downloading = True
        self._gui_cancel.clear()
        self._gui_btn.setText(self._t("gui_model_cancel"))
        self._gui_status.setText(self._t("gui_model_downloading"))

        def work() -> None:
            res = detect.download(
                self._settings.proxy,
                on_progress=lambda d, t: self._gui_progress.emit(int(d * 100 / t) if t else 0),
                should_cancel=self._gui_cancel.is_set,
            )
            self._gui_model_done.emit(res)

        threading.Thread(target=work, daemon=True, name="mochi-gui-model").start()

    def _render_gui_model(self, res: str) -> None:
        self._gui_downloading = False
        self._gui_btn.setText(self._t("gui_model_btn"))
        if res == "ok" and detect.available():
            self._gui_status.setText(self._gui_on_text())
            self._gui_btn.setEnabled(False)
        elif res == "cancelled":
            self._gui_btn.setEnabled(True)
            self._gui_status.setText(self._t("gui_model_cancelled"))
        else:
            self._gui_btn.setEnabled(True)
            self._gui_status.setText(self._t("gui_model_failed") + ("" if res == "ok" else f"  {res}"))

    def _on_check_update(self) -> None:
        self._check_btn.setEnabled(False)
        self._update_status.setText(self._t("update_checking"))

        def work() -> None:
            try:
                result = updater.check_latest(self._settings.proxy)
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
            self._update_checked.emit(result)

        threading.Thread(target=work, daemon=True, name="mochi-update-check-panel").start()

    def _render_update(self, result: object) -> None:
        self._check_btn.setEnabled(True)
        status = result.get("status") if isinstance(result, dict) else "error"
        if status == "newer":
            v = str(result.get("latest", ""))
            url = result.get("url", updater.RELEASES_PAGE)
            txt = self._t("update_newer").replace("{v}", v)
            link = self._t("update_download")
            self._update_status.setText(
                f'{txt} · <a href="{url}" style="color: {_ACCENT}; text-decoration: none;">{link}</a>'
            )
        elif status == "latest":
            self._update_status.setText(self._t("update_latest"))
        else:
            self._update_status.setText(self._t("update_failed"))

    def _on_new_topic_clicked(self) -> None:
        if self._on_new_topic is not None:
            self._on_new_topic()
        self._new_topic_btn.setText(self._t("new_topic_done"))
        self._new_topic_btn.setEnabled(False)

    def _on_reset_clicked(self) -> None:
        """重置羁绊按两下确认"""
        if not self._reset_armed:
            self._reset_armed = True
            self._reset_btn.setText(self._t("reset_arm"))
            self._reset_btn.setProperty("armed", "true")
            self._reset_btn.style().unpolish(self._reset_btn)
            self._reset_btn.style().polish(self._reset_btn)
            return
        if self._on_reset is not None:
            self._on_reset()
        self._reset_btn.setText(self._t("reset_done"))
        self._reset_btn.setEnabled(False)
        self._reset_armed = False
        # 数据清了 但上面那些显示是开面板时建的 不刷就还显示旧记忆/日记/知识库
        for refresh in (self._refresh_bond, self._refresh_docs, self._refresh_status):
            try:
                refresh()
            except Exception:
                pass

    def _switch(self, index: int) -> None:
        """切页 换栈高亮导航并刷对应页数据"""
        prev = self._stack.currentIndex()
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tabs):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._footer.setVisible(index not in self._footerless)
        key = self._page_keys[index] if 0 <= index < len(self._page_keys) else ""  # 页顺序会浮动 认key别认index
        if key == "tab_home":
            self._refresh_status()
        elif key == "tab_bond":
            self._refresh_bond()
        elif key == "tab_docs":
            self._refresh_docs()
        elif key == "tab_chat":
            self._refresh_hotkey_status()
        elif key == "tab_connect":
            self._refresh_usage()
        if index != prev:
            self._animate_page(self._stack.currentWidget())

    def _animate_page(self, page: QWidget) -> None:
        end = page.pos()
        page.move(end.x(), end.y() + 16)
        anim = QPropertyAnimation(page, b"pos", self)
        anim.setDuration(180)
        anim.setStartValue(QPoint(end.x(), end.y() + 16))
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_anim = anim
        anim.start()

    def _on_save(self) -> None:
        """控件值收回settings落盘 再回调on_apply热更"""
        s = self._settings
        s.api_key = self._api_key.text().strip()
        s.base_url = self._base_url.text().strip()
        s.model = self._model.text().strip()
        s.subagent_model = self._subagent_model.text().strip()
        s.embed_model = self._embed_model.text().strip()
        s.proxy = self._proxy.text().strip()
        try:
            # 上下文8k下限 非法值退回24k默认
            s.history_tokens = max(8_000, int(self._history_tokens.text().strip() or "24000"))
        except ValueError:
            s.history_tokens = 24_000
        s.language = self._language.text().strip()
        s.temperature = round(self._temperature.value() / 100, 2)
        s.autonomy = self._autonomy.currentData() or "正常"
        s.think_level = self._think_level.currentData() or "medium"
        s.enable_thinking, s.max_tokens = THINK_PRESETS[s.think_level]
        s.proactive_enabled = self._proactive_enabled.isChecked()
        s.proactive_level = self._proactive_level.currentData() or "正常"
        s.weather_enabled = self._weather_cb.isChecked()
        s.allow_web = self._allow_web.isChecked()
        s.allow_control = self._allow_control.isChecked()
        s.allow_shell = self._allow_shell.isChecked()
        s.watch_screen = self._watch.isChecked()
        s.clip_sampler = self._clip_sampler.isChecked()
        s.clip_alchemy = self._clip_alchemy.isChecked()
        # 多段只取第一段当热键 录空保留原值
        s.hotkey_summon = self._hk_summon.keySequence().toString().split(",")[0].strip() or s.hotkey_summon
        s.hotkey_ask = self._hk_ask.keySequence().toString().split(",")[0].strip() or s.hotkey_ask
        s.hotkey_quick = self._hk_quick.keySequence().toString().split(",")[0].strip() or s.hotkey_quick
        s.hotkey_talk = self._hk_talk.keySequence().toString().split(",")[0].strip() or s.hotkey_talk
        s.hear_enabled = self._hear_cb.isChecked()
        s.wake_enabled = self._wake_cb.isChecked()
        try:
            s.save()
        except Exception:
            self._flash_error()
            return
        if self._on_apply is not None:
            self._on_apply()
        if self._has_home:
            self._refresh_status()
        self._flash_saved()
        QTimer.singleShot(900, self._refresh_hotkey_status)

    def _flash_saved(self) -> None:
        self._save_btn.setText(self._t("saved_ok"))
        self._save_btn.setEnabled(False)
        QTimer.singleShot(1500, self._restore_save_btn)

    def _flash_error(self) -> None:
        self._save_btn.setText(self._t("save_failed"))
        QTimer.singleShot(2200, self._restore_save_btn)

    def _restore_save_btn(self) -> None:
        self._save_btn.setText(self._t("save"))
        self._save_btn.setEnabled(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 自己接管拖动 按下记偏移
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
