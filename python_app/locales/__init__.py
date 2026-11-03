# -*- coding: utf-8 -*-
"""
Gestionnaire d'Internationalisation (i18n) pour fOMODSIM.
Supporte Français ('fr'), Anglais ('en'), Italien ('it'), Espagnol ('es').
"""

from typing import Dict, Any
from PyQt6.QtCore import QSettings

try:  # module commun : langue du Mac et menu « Langue »
    from python_app import lang_menu
except ImportError:
    import lang_menu

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

TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "fr": FR_STRINGS,
    "en": EN_STRINGS,
    "it": IT_STRINGS,
    "es": ES_STRINGS,
}

SETTINGS_KEY = "language"
DEFAULT_LANGUAGE = "fr"


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
        # « auto » (langue du Mac, par défaut) ou code choisi dans le menu « Langue »
        self._choice = lang_menu.normalize_choice(self.settings.value(SETTINGS_KEY, lang_menu.AUTO))
        self._current_lang = lang_menu.resolve(self._choice)

    @property
    def choice(self) -> str:
        return self._choice

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, choice: str) -> bool:
        """Mémorise le choix (« auto » ou code) ; vrai si la langue affichée change."""
        self._choice = lang_menu.normalize_choice(choice)
        self.settings.setValue(SETTINGS_KEY, self._choice)
        lang_code = lang_menu.resolve(self._choice)
        if lang_code != self._current_lang:
            self._current_lang = lang_code
            return True
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
