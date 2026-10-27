# -*- coding: utf-8 -*-
"""
Gestionnaire d'Internationalisation (i18n) pour fOMODSIM.
Supporte Français ('fr'), Anglais ('en'), Italien ('it'), Espagnol ('es').
"""

from typing import Dict, Any, List, Tuple
from PyQt6.QtCore import QLocale, QSettings

try:
    from python_app.locales.fr import STRINGS as FR_STRINGS
    from python_app.locales.en import STRINGS as EN_STRINGS
    from python_app.locales.it import STRINGS as IT_STRINGS
    from python_app.locales.es import STRINGS as ES_STRINGS
except ImportError:
    from locales.fr import STRINGS as FR_STRINGS
    from locales.en import STRINGS as EN_STRINGS
    from locales.it import STRINGS as IT_STRINGS
    from locales.es import STRINGS as ES_STRINGS

AVAILABLE_LANGUAGES: List[Tuple[str, str, str]] = [
    ("fr", "Français", "🇫🇷"),
    ("en", "English", "🇬🇧"),
    ("it", "Italiano", "🇮🇹"),
    ("es", "Español", "🇪🇸"),
]

TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "fr": FR_STRINGS,
    "en": EN_STRINGS,
    "it": IT_STRINGS,
    "es": ES_STRINGS,
}

SETTINGS_KEY = "language"
DEFAULT_LANGUAGE = "fr"


def system_language() -> str:
    """Langue préférée du système si elle fait partie des 4, sinon anglais."""
    for name in QLocale.system().uiLanguages():
        code = name[:2].lower()
        if code in TRANSLATIONS:
            return code
        break  # seule la langue préférée compte
    return "en"


class I18nManager:
    """Gestionnaire singleton de traduction."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18nManager, cls).__new__(cls)
            cls._instance._init_settings()
        return cls._instance

    def _init_settings(self):
        self.settings = QSettings("SkyrimTools", "FOMODSimulator")
        saved_lang = self.settings.value(SETTINGS_KEY, None)
        if saved_lang not in TRANSLATIONS:
            saved_lang = system_language()
        self._current_lang = saved_lang

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_code: str) -> bool:
        if lang_code in TRANSLATIONS and lang_code != self._current_lang:
            self._current_lang = lang_code
            self.settings.setValue(SETTINGS_KEY, lang_code)
            return True
        elif lang_code in TRANSLATIONS:
            self.settings.setValue(SETTINGS_KEY, lang_code)
        return False

    @property
    def strings(self) -> Dict[str, Any]:
        return TRANSLATIONS.get(self._current_lang, TRANSLATIONS[DEFAULT_LANGUAGE])

    def get(self, *keys: str, default: str = "") -> str:
        """Accède à une clé imbriquée avec repli sur le français si manquant."""
        curr = self.strings
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                # Repli sur le français
                fallback = TRANSLATIONS[DEFAULT_LANGUAGE]
                for fb_k in keys:
                    if isinstance(fallback, dict) and fb_k in fallback:
                        fallback = fallback[fb_k]
                    else:
                        return default
                return str(fallback)
        return str(curr) if curr is not None else default


def get_i18n() -> I18nManager:
    return I18nManager()
