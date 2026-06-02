# author: bdth
# email: 2074055628@qq.com
# 设置面板对话框：左侧竖向导航(主页/连接/聊天/权限/关于) + 右侧内容区，浅色平滑主题，无边框可拖拽

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
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

from desktop_pet import i18n
from desktop_pet.docs import docs
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


# 开机/关机按钮直接用自身样式表(不靠 objectName + 祖先 QSS——运行时切 objectName 背景常 cascade 不上、变白字白底)
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
    """分段按钮选择器：一排互斥按钮代替下拉框——无弹窗，且每个按钮用自身样式表(选中态紫底白字一定可见)。
    接口对齐 QComboBox：currentData() / currentText() / setCurrentData()；on_change 仅在用户点击时回调。"""

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
        self._group.buttonClicked.connect(self._on_clicked)  # 仅用户点击触发 on_change(不含 setCurrentData)
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

    def currentText(self) -> str:
        i = self._group.checkedId()
        return self._items[i][1] if 0 <= i < len(self._items) else ""


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageHint")
    label.setWordWrap(True)
    return label


class ControlPanel(QDialog):
    def __init__(self, settings: Settings, on_reset: Callable[[], None] | None = None,
                 on_apply: Callable[[], None] | None = None,
                 status_provider: Callable[[], dict] | None = None,
                 on_toggle_active: Callable[[], None] | None = None,
                 bond_provider: Callable[[], dict] | None = None,
                 on_set_language: Callable[[str], None] | None = None,
                 hotkey_status_provider: Callable[[], dict] | None = None) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._settings = settings
        self._on_reset = on_reset
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
        card.setFixedSize(720, 540)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(52)
        shadow.setColor(QColor(90, 80, 150, 90))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        self._build_fields(settings)

        page_specs: list[tuple[str, object]] = []
        if self._has_home:  # 仅在有状态源时挂「主页」(首次配置弹窗也会带上，见 app.run)
            page_specs.append(("tab_home", self._build_home_page))
        if self._has_bond:  # 「它眼中的你」羁绊档案
            page_specs.append(("tab_bond", self._build_bond_page))
        page_specs += [
            ("tab_docs", self._build_docs_page),
            ("tab_connect", self._build_connect_page),
            ("tab_chat", self._build_chat_page),
            ("tab_perm", self._build_perm_page),
            ("tab_about", self._build_about_page),
        ]
        self._page_keys = [k for k, _ in page_specs]

        # ── 左侧栏：头像 + 标题 + 竖向导航 ──
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
        self._footerless: set[int] = set()  # 主页/关于页隐藏「保存/取消」页脚
        for index, (key, builder) in enumerate(page_specs):
            btn = QPushButton(self._t(key), objectName="nav")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, i=index: self._switch(i))
            side.addWidget(btn)
            self._tabs.append(btn)
            self._stack.addWidget(builder())
            if key in ("tab_home", "tab_bond", "tab_about", "tab_docs"):
                self._footerless.add(index)
        side.addStretch(1)
        # 界面语言常驻侧边栏底部，点选即时切换(无需重启/保存)
        _lang_short = {"中文": "中", "English": "EN", "日本語": "日"}
        side.addWidget(QLabel(self._t("lbl_ui_lang"), objectName="help"))
        self._ui_language = _Segmented(
            [(lang, _lang_short.get(lang, lang)) for lang in UI_LANGUAGES],
            on_change=self._on_lang_clicked,
        )
        self._ui_language.setCurrentData(self._lang)
        side.addWidget(self._ui_language)

        # ── 右侧内容区：关闭按钮 + 页面 + 页脚 ──
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
        if self._has_home:  # 主页状态机信息定时刷新
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._refresh_status)
            self._status_timer.start(1500)
            self._refresh_status()

    def _t(self, key: str) -> str:
        return i18n.t(key, self._lang)

    def _build_fields(self, settings: Settings) -> None:
        self._api_key = QLineEdit(settings.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._base_url = QLineEdit(settings.base_url)
        self._model = QLineEdit(settings.model)
        self._embed_model = QLineEdit(settings.embed_model)
        self._proxy = QLineEdit(settings.proxy)
        self._proxy.setPlaceholderText("http://127.0.0.1:7897")
        self._language = QLineEdit(settings.language)
        self._language.setPlaceholderText(self._t("ph_reply_lang"))
        self._birthday = QLineEdit(settings.birthday)
        self._birthday.setPlaceholderText(self._t("ph_birthday"))
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
        self._temperature.setRange(0, 200)  # 放宽到 2.0：别把外部/手改的 1.5/2.0(接口合法)在加载时静默 clamp 回 1.3
        self._temperature.setValue(int(round(settings.temperature * 100)))
        self._temp_label = QLabel(f"{settings.temperature:.2f}")
        self._temperature.valueChanged.connect(
            lambda v: self._temp_label.setText(f"{v / 100:.2f}")
        )
        self._max_steps = QLineEdit(str(settings.max_steps))
        self._max_steps.setPlaceholderText(self._t("ph_max_steps"))
        self._think_level = _Segmented([(value, self._t(label_key)) for value, label_key in i18n.THINK_LEVEL_KEYS])
        self._think_level.setCurrentData(settings.think_level)
        self._proactive_enabled = QCheckBox(self._t("cb_proactive"))
        self._proactive_enabled.setChecked(settings.proactive_enabled)
        self._proactive_enabled.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tts = QCheckBox(self._t("cb_tts"))
        self._tts.setChecked(settings.tts_enabled)
        self._tts.setCursor(Qt.CursorShape.PointingHandCursor)
        self._proactive_level = _Segmented([(value, self._t(label_key)) for value, label_key in i18n.PROACTIVE_LABEL_KEYS])
        self._proactive_level.setCurrentData(settings.proactive_level)
        self._hk_summon = QKeySequenceEdit(QKeySequence(settings.hotkey_summon))
        self._hk_ask = QKeySequenceEdit(QKeySequence(settings.hotkey_ask))
        self._hk_quick = QKeySequenceEdit(QKeySequence(settings.hotkey_quick))
        self._hk_status_labels: dict = {}

    def _scroll_page(self, hint_text: str) -> tuple[QWidget, QVBoxLayout]:
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
        scroll.setFixedHeight(392)
        scroll.viewport().setStyleSheet("background: transparent;")
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
        tip.setContentsMargins(27, 0, 0, 0)
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

        self._toggle_btn = QPushButton("—")  # 开机/关机 开关；文字+样式随状态变
        self._toggle_btn.setStyleSheet(_TOGGLE_ON_QSS)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setMinimumHeight(48)
        self._toggle_btn.clicked.connect(self._toggle_clicked)
        body.addSpacing(10)
        body.addWidget(self._toggle_btn)
        body.addStretch(1)
        return page

    def _refresh_status(self) -> None:
        if not self._status_provider:
            return
        try:
            s = self._status_provider()
        except Exception:  # noqa: BLE001
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
        # 开机中→「关机」(描边)；关机中→「开机」(醒目 accent)。直接设按钮自身样式，保证一定渲染出来
        self._toggle_btn.setText(self._t("home_power_off") if shown else self._t("home_power_on"))
        self._toggle_btn.setStyleSheet(_TOGGLE_OFF_QSS if shown else _TOGGLE_ON_QSS)

    def _toggle_clicked(self) -> None:
        if self._on_toggle_active is not None:
            self._on_toggle_active()
        self._refresh_status()

    def _on_lang_clicked(self, lang: str) -> None:
        if self._on_set_language is not None:
            self._on_set_language(lang)  # 交给 app：立即保存+切语言+用新语言重开面板

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
        body.addStretch(1)
        return page

    def _refresh_bond(self) -> None:
        if not self._bond_provider:
            return
        try:
            s = self._bond_provider()
        except Exception:  # noqa: BLE001
            return
        rap = int(round(float(s.get("rapport", 0.0)) * 100))
        self._bond_stat.setText(self._t("bond_stat_fmt").format(
            days=s.get("days", 0), n=s.get("interactions", 0), rap=rap, sk=s.get("skills", 0)))
        portrait = (s.get("persona") or "").strip()
        self._bond_persona.setText(portrait or self._t("bond_persona_empty"))
        prefs = s.get("preferences") or []
        env = s.get("env") or []
        pref_lines = [f"· {k}：{v}" for k, v in prefs] + [f"· {k} = {v}" for k, v in env]
        self._bond_prefs.setText("\n".join(pref_lines) if pref_lines else self._t("bond_empty"))
        exps = s.get("experiences") or []
        self._bond_exp.setText("\n".join(f"· {e}" for e in exps) if exps else self._t("bond_empty"))

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
        except Exception:  # noqa: BLE001
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
        if not btn.property("armed"):  # 两段式：第一次点变红求确认，第二次才真删
            btn.setProperty("armed", "true")
            btn.setText(self._t("docs_del_arm"))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            return
        try:
            docs.forget_exact(source)
        except Exception:  # noqa: BLE001
            pass
        self._refresh_docs()

    def _add_docs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, self._t("docs_add"), "",
            "Docs (*.txt *.md *.rst *.pdf *.py *.js *.ts *.json *.yaml *.csv *.html *.java *.go *.rs *.c *.cpp *.sql *.vue);;All files (*.*)",
        )
        if not paths:
            return
        # ingest 要做向量化、慢，丢后台线程跑，跑完定时刷新（不阻塞 UI）
        def work() -> None:
            for p in paths:
                try:
                    docs.ingest(p)
                except Exception:  # noqa: BLE001
                    pass
        try:
            threading.Thread(target=work, daemon=True, name="panel-ingest").start()
        except RuntimeError:
            return
        QTimer.singleShot(3500, self._refresh_docs)

    def _build_connect_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_connect"))
        body.addWidget(self._field("lbl_api_key", self._api_key, "help_api_key"))
        body.addWidget(self._field("lbl_base_url", self._base_url, "help_base_url"))
        body.addWidget(self._field("lbl_model", self._model, "help_model"))
        body.addWidget(self._field("lbl_embed", self._embed_model, "help_embed"))
        body.addWidget(self._field("lbl_proxy", self._proxy, "help_proxy"))
        body.addStretch(1)
        return page

    def _build_chat_page(self) -> QWidget:
        page, body = self._scroll_page(self._t("hint_chat"))
        body.addWidget(self._field("lbl_reply_lang", self._language, "help_reply_lang"))
        body.addWidget(self._field("lbl_birthday", self._birthday, "help_birthday"))
        temp_row = QHBoxLayout()
        temp_row.setSpacing(10)
        temp_row.addWidget(self._temperature, 1)
        temp_row.addWidget(self._temp_label)
        body.addWidget(self._field("lbl_temp", temp_row, "help_temp"))
        body.addWidget(self._field("lbl_max_steps", self._max_steps, "help_max_steps"))
        body.addWidget(self._field("lbl_think_level", self._think_level, "help_think_level"))
        body.addWidget(self._check_field(self._proactive_enabled, "help_proactive"))
        body.addWidget(self._field("lbl_proactive_freq", self._proactive_level, "help_proactive_freq"))
        body.addWidget(self._check_field(self._tts, "help_tts"))
        body.addWidget(self._build_hotkeys_block())
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
        except Exception:  # noqa: BLE001
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
        body.addStretch(1)
        return page

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
        col.addSpacing(6)
        col.addLayout(rule("aboutRule", 56, 3))
        col.addSpacing(10)
        col.addWidget(label(self._t("about_sub"), "aboutSub"))
        col.addSpacing(4)
        col.addWidget(label(self._t("about_desc"), "aboutDesc", wrap=True))
        col.addSpacing(8)
        col.addWidget(label(self._t("about_chips"), "aboutChips"))
        col.addStretch(1)

        self._reset_btn = QPushButton(self._t("reset_btn"), objectName="reset")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_armed = False
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_row.addWidget(self._reset_btn)
        reset_row.addStretch(1)
        col.addLayout(reset_row)
        col.addSpacing(10)
        col.addLayout(rule("aboutSep", 220, 1))
        col.addSpacing(8)
        col.addWidget(label(self._t("about_made_by"), "aboutAuthor"))
        col.addWidget(label(self._t("about_meta"), "aboutMeta"))
        return page

    def _on_reset_clicked(self) -> None:
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

    def _switch(self, index: int) -> None:
        prev = self._stack.currentIndex()
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tabs):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._footer.setVisible(index not in self._footerless)
        key = self._page_keys[index] if 0 <= index < len(self._page_keys) else ""
        if key == "tab_home":  # 切到主页/羁绊立即刷新一次
            self._refresh_status()
        elif key == "tab_bond":
            self._refresh_bond()
        elif key == "tab_docs":
            self._refresh_docs()
        elif key == "tab_chat":
            self._refresh_hotkey_status()
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

    @staticmethod
    def _parse_max_steps(text: str) -> int:
        text = text.strip()
        if not text.isdigit():
            return 16
        # 上限对齐 loop 的 _MAX_STEPS_CEILING=64：别让面板接受 65–99 却被静默截断
        return max(1, min(int(text), 64))

    def _on_save(self) -> None:
        s = self._settings
        s.api_key = self._api_key.text().strip()
        s.base_url = self._base_url.text().strip()
        s.model = self._model.text().strip()
        s.embed_model = self._embed_model.text().strip()
        s.proxy = self._proxy.text().strip()
        s.language = self._language.text().strip()
        s.birthday = self._birthday.text().strip()
        s.temperature = round(self._temperature.value() / 100, 2)
        s.max_steps = self._parse_max_steps(self._max_steps.text())
        s.think_level = self._think_level.currentData() or "medium"
        s.enable_thinking, s.max_tokens = THINK_PRESETS[s.think_level]
        s.proactive_enabled = self._proactive_enabled.isChecked()
        s.proactive_level = self._proactive_level.currentData() or "正常"
        s.tts_enabled = self._tts.isChecked()
        s.allow_web = self._allow_web.isChecked()
        s.allow_control = self._allow_control.isChecked()
        s.allow_shell = self._allow_shell.isChecked()
        s.watch_screen = self._watch.isChecked()
        s.clip_sampler = self._clip_sampler.isChecked()
        s.clip_alchemy = self._clip_alchemy.isChecked()
        s.hotkey_summon = self._hk_summon.keySequence().toString().split(",")[0].strip() or s.hotkey_summon
        s.hotkey_ask = self._hk_ask.keySequence().toString().split(",")[0].strip() or s.hotkey_ask
        s.hotkey_quick = self._hk_quick.keySequence().toString().split(",")[0].strip() or s.hotkey_quick
        try:
            s.save()
        except Exception:  # noqa: BLE001 - 磁盘满/只读/被占用：别静默、别崩槽，明确告诉用户没存上
            self._flash_error()
            return
        if self._on_apply is not None:
            self._on_apply()
        if self._has_home:
            self._refresh_status()
        self._flash_saved()  # 反馈「已应用 ✓」；面板保留，关闭用 × / 取消
        QTimer.singleShot(900, self._refresh_hotkey_status)  # 重注册是异步的，稍等再读注册结果

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
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
