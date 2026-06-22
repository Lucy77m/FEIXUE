# i18n 键完整性 三种语言键集合必须一致 缺键会让面板显示 raw key

from __future__ import annotations

from desktop_pet import i18n
from desktop_pet.i18n import UI_LANGUAGES, _STRINGS


def _lang_to_code():
    # _STRINGS 内层 key 是语言码 设语言再读已知键反推不可靠 直接用 _STRINGS 顶层结构
    return _STRINGS


def test_all_languages_have_same_keys():
    tables = _STRINGS
    assert set(tables.keys()), "应有语言表"
    key_sets = {lang: set(keys) for lang, keys in tables.items()}
    langs = list(key_sets)
    base_lang = langs[0]
    base = key_sets[base_lang]
    for lang in langs[1:]:
        missing = base - key_sets[lang]
        extra = key_sets[lang] - base
        assert not missing, f"{lang} 相比 {base_lang} 缺键: {sorted(missing)[:10]}"
        assert not extra, f"{lang} 相比 {base_lang} 多键: {sorted(extra)[:10]}"


def test_audit_added_keys_present_everywhere():
    # 新增 docs_del_fail 三语都得有 否则面板会显示键名本身
    for keys in _STRINGS.values():
        assert "docs_del_fail" in keys
        assert "feed_busy" in keys  # 投喂再入保护复用的提示键


def test_t_returns_translation_for_known_key():
    for lang in UI_LANGUAGES:
        i18n.set_language(lang)
        val = i18n.t("docs_del_fail")
        assert val and val != "docs_del_fail", f"{lang} 的 docs_del_fail 没翻译"
