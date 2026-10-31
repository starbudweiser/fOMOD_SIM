#!/usr/bin/env python3
"""
fOMODSIM v1.0 - Skyrim Modding & Staging Tool
Portage PyQt6 autonome, non-bloquant et multi-format (.zip, .7z, .rar, dossiers).
"""

import sys
import os
import logging

# Support exécution gelée (PyInstaller / py2app) ou module standard
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import update_check

try:
    from python_app.gui.main_window import MainWindow
    from python_app.gui.theme import DARK_THEME_QSS
    from python_app.gui import socle_qt
    from python_app.gui.splash import SplashScreen
except ImportError:
    from gui.main_window import MainWindow
    from gui.theme import DARK_THEME_QSS
    from gui import socle_qt
    from gui.splash import SplashScreen


def setup_logging():
    """Configure la journalisation standard Python (bannir l'utilisation de print)."""
    log_level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    setup_logging()
    logger = logging.getLogger("fomod_simulator")
    logger.info("Démarrage de fOMODSIM v1.0 (PyQt6)")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Exception non interceptée :", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    # Configuration des attributs Qt pour affichage Haute Densité (HiDPI si disponible)
    attr_scaling = getattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling", None)
    if attr_scaling is not None:
        QApplication.setAttribute(attr_scaling, True)
    attr_pixmaps = getattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps", None)
    if attr_pixmaps is not None:
        QApplication.setAttribute(attr_pixmaps, True)

    app = QApplication(sys.argv)
    socle_qt.apply(app, full=False)  # design system Socle (palette + règles de base)
    socle_qt.brand(app, ["fOMODSIM", "fOMOD_SIM"], "#1677dc")  # « f » dans le bleu du logo
    if sys.platform == "darwin":
        from PyQt6.QtGui import QFont
        app.setFont(QFont(".AppleSystemUIFont", 13))
    app.setStyle("Fusion")
    app.setApplicationName("fOMODSIM")
    app.setApplicationVersion("1.3.0")
    app.setOrganizationName("SkyrimTools")
    app.setStyleSheet(socle_qt.qss(full=False) + DARK_THEME_QSS)

    window = MainWindow()

    # Si un fichier ou dossier d'archive est passé en argument CLI
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
        if os.path.exists(target_path):
            logger.info(f"Ouverture directe via CLI : {target_path}")
            window._start_archive_extraction(target_path)
        else:
            logger.warning(f"Fichier passé en argument inexistant : {target_path}")

    # Splash animé (règle Socle) : fenêtre principale à t = 2 s, sortie du splash à t = 4 s
    splash = SplashScreen(
        "fOMODSIM",
        window.i18n.get("splash", "subtitle"),
        f"{window.i18n.get('splash', 'footer')} · v{app.applicationVersion()}",
    )
    splash.start()
    splash.open_main_window(window)
    update_check.start_qt(window, "fOMOD_SIM", lang=lambda: window.i18n.current_language)  # nouvelle version ? (au plus une fois par jour)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
