# -*- coding: utf-8 -*-
"""
Fenêtre « À propos de fOMODSIM » (Socle, section « Fenêtre « À propos » », modèle swift/AboutWindow.swift).

QDialog à nous plutôt que le panneau standard : colonne centrée de 300 px de texte, marges de 28 px,
12 px entre les blocs (6 px sous le nom, 18 px sous la version), hauteur calculée d'après le contenu.
"""

import os
import plistlib
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

APP_NAME = "fOMODSIM"
AUTHORS = "Starbudweiser & Claude Code (Anthropic)"
SIDE_MARGIN = 28
TEXT_WIDTH = 300

_dialog = None


def _build_number() -> str:
    """CFBundleVersion de l'appli compilée ; « dev » en lancement depuis les sources."""
    if getattr(sys, "frozen", False):
        plist = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "Info.plist")
        try:
            with open(plist, "rb") as f:
                return str(plistlib.load(f).get("CFBundleVersion") or "?")
        except Exception:
            pass
    return "dev"


def _label(text: str, size: int = 12, bold: bool = False, muted: bool = False) -> QLabel:
    lbl = QLabel()
    lbl.setText(text)  # setText : socle_qt.brand colore le « f » de fOMODSIM
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    lbl.setFixedWidth(TEXT_WIDTH)
    color = "#a3a3a3" if muted else "#f5f5f5"
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"font-size: {size}px; font-weight: {weight}; color: {color}; background: transparent; border: none;")
    return lbl


class AboutDialog(QDialog):
    def __init__(self, i18n, icon_path: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
                            | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)
        self.setWindowTitle(i18n.get("about", "menu"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SIDE_MARGIN, SIDE_MARGIN, SIDE_MARGIN, SIDE_MARGIN)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon = QLabel()
        icon.setFixedSize(84, 84)
        pix = QPixmap(icon_path)
        if not pix.isNull():
            ratio = self.devicePixelRatioF() or 2.0
            pix = pix.copy(100, 100, 824, 824).scaled(  # carré utile de icon.png, sans marges transparentes
                int(84 * ratio), int(84 * ratio),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pix.setDevicePixelRatio(ratio)
            icon.setPixmap(pix)
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)

        name = _label(APP_NAME, size=17, bold=True)  # « f » coloré par socle_qt.brand
        version = _label(i18n.get("about", "version").format(
            v=QApplication.applicationVersion() or "?", b=_build_number()), muted=True)
        blocks = [
            name,
            version,
            _label(i18n.get("about", "tagline")),
            _label(AUTHORS, bold=True),
            _label(i18n.get("about", "license")),
            _label(i18n.get("about", "disclaimer"), muted=True),
            _label(i18n.get("about", "credit"), muted=True),
        ]
        for i, w in enumerate(blocks):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
            if w is name:
                lay.addSpacing(6 - 12)
            elif w is version:
                lay.addSpacing(18 - 12)

        self.setFixedWidth(TEXT_WIDTH + 2 * SIDE_MARGIN)
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())


def show_about(i18n, icon_path: str, parent=None) -> AboutDialog:
    """Une seule instance : refaite si la langue a changé, réaffichée sinon. Centrée à l'écran."""
    global _dialog
    if _dialog is not None and _dialog.property("lang") != i18n.current_language:
        _dialog.close()
        _dialog = None
    if _dialog is None:
        _dialog = AboutDialog(i18n, icon_path, parent)
        _dialog.setProperty("lang", i18n.current_language)
    screen = QApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        _dialog.move(geo.center().x() - _dialog.width() // 2, geo.center().y() - _dialog.height() // 2)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog
