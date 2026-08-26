# i18n/__init__.py
#
# Minimal translation layer for the PyQt5 UI in main.py. Not a general i18n
# framework — just enough to switch every static UI string (button labels,
# tooltips, dialog titles, error/success messages) between English and
# French, per the project's Canadian bilingual requirement.
#
# Metadata field labels (from metadata_profiles/*_profile.py) and the
# discipline-standard descriptions (from standards_registry.py) are NOT
# covered here — those describe the extracted data itself, catalogued
# separately, and translating them is out of this module's scope.

from i18n.strings_en import STRINGS_EN
from i18n.strings_fr import STRINGS_FR

LANGUAGES = {
    "EN": STRINGS_EN,
    "FR": STRINGS_FR,
}

_current_language = "EN"


def set_language(lang_code):
    """Sets the active language for tr(). No-op if lang_code isn't registered."""
    global _current_language
    if lang_code in LANGUAGES:
        _current_language = lang_code


def get_language():
    return _current_language


def tr(key, **kwargs):
    """
    Returns the translated string for key in the active language, falling
    back to English if the active language is missing that key, and to the
    key itself if English is missing it too (so a missing translation never
    crashes the UI — it just shows the raw key, which is easy to spot).
    """
    strings = LANGUAGES.get(_current_language, STRINGS_EN)
    template = strings.get(key, STRINGS_EN.get(key, key))
    return template.format(**kwargs) if kwargs else template
