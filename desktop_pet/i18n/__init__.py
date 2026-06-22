# 多语言文案表 提供切语言和取词

from __future__ import annotations

from desktop_pet.i18n.zh import STRINGS as _ZH
from desktop_pet.i18n.en import STRINGS as _EN
from desktop_pet.i18n.ja import STRINGS as _JA

UI_LANGUAGES = ("中文", "English", "日本語")
_DEFAULT = "中文"
_current = _DEFAULT


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in _STRINGS else _DEFAULT


def t(key: str, lang: str | None = None) -> str:
    table = _STRINGS.get(lang or _current, _STRINGS[_DEFAULT])
    return table.get(key) or _STRINGS[_DEFAULT].get(key, key)


_STRINGS: dict[str, dict[str, str]] = {
    "中文": _ZH,
    "English": _EN,
    "日本語": _JA,
}


# --- post-dict constants ---
PROACTIVE_LABEL_KEYS = (("安静", "pl_quiet"), ("正常", "pl_normal"), ("话痨", "pl_chatty"))
AUTONOMY_LABEL_KEYS = (("省心", "au_frugal"), ("正常", "au_normal"), ("放手干", "au_auto"))

THINK_LEVEL_KEYS = (("off", "tl_off"), ("low", "tl_low"), ("medium", "tl_medium"), ("high", "tl_high"), ("max", "tl_max"))

_NOARG_STEP_KEYS = ("s_run_shell", "s_run_python", "s_screenshot", "s_list_windows", "s_list_skills")


def thinking_label() -> str:
    return t("thinking")


def is_noarg_tool_label(label: str) -> bool:
    return label in {t(k) for k in _NOARG_STEP_KEYS}
