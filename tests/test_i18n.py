# tests/test_i18n.py

import i18n
from i18n import tr, set_language, get_language, LANGUAGES
from i18n.strings_en import STRINGS_EN
from i18n.strings_fr import STRINGS_FR


def teardown_function(_func):
    # Every test in this module must leave the global language as it found it.
    set_language("EN")


def test_default_language_is_en():
    assert get_language() == "EN"


def test_set_language_switches_active_strings():
    set_language("FR")
    assert get_language() == "FR"
    assert tr("btn_close") == STRINGS_FR["btn_close"]
    set_language("EN")
    assert tr("btn_close") == STRINGS_EN["btn_close"]


def test_set_language_ignores_unknown_code():
    set_language("EN")
    set_language("DE")  # not registered
    assert get_language() == "EN"


def test_tr_formats_placeholders():
    set_language("EN")
    result = tr("dialog_title_metadata_standard", context="Microscopy")
    assert result == "Metadata Standard — Microscopy"


def test_tr_formats_placeholders_in_french():
    set_language("FR")
    result = tr("dialog_title_metadata_standard", context="Microscopie")
    assert "Microscopie" in result
    assert result == STRINGS_FR["dialog_title_metadata_standard"].format(context="Microscopie")


def test_tr_falls_back_to_key_when_missing_everywhere():
    assert tr("this_key_does_not_exist") == "this_key_does_not_exist"


def test_en_and_fr_have_identical_key_sets():
    en_keys = set(STRINGS_EN.keys())
    fr_keys = set(STRINGS_FR.keys())
    assert en_keys == fr_keys, (
        f"Missing in FR: {en_keys - fr_keys}\nMissing in EN: {fr_keys - en_keys}"
    )


def test_languages_registry_exposes_both():
    assert set(LANGUAGES.keys()) == {"EN", "FR"}
    assert LANGUAGES["EN"] is STRINGS_EN
    assert LANGUAGES["FR"] is STRINGS_FR


def test_no_empty_translations():
    for lang_code, strings in LANGUAGES.items():
        for key, value in strings.items():
            assert value.strip(), f"{lang_code}.{key} is empty"
