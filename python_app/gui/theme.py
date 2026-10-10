"""Thème graphique Qt Style Sheets (QSS) moderne, borderless et épuré pour fOMODSIM."""

DARK_THEME_QSS = """
/* ==========================================================================
   fOMODSIM - DESIGN SYSTEM BORDERLESS ÉPURÉ
   Bordures superflues supprimées | Surfaces sombres hiérarchisées
   ========================================================================== */

QMainWindow {
    background-color: #181818;
    color: #dddddd;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QDialog {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    border: 1px solid #262626;
    border-radius: 8px;
}

/* Réinitialisation universelle pour éviter l'héritage parasite de bordures */
QFrame {
    border: none;
}

QLabel {
    background: transparent;
    border: none;
}

/* En-tête supérieur harmonisé sans contour */
QFrame#HeaderBar {
    background-color: #222222;
    border: none;
    border-radius: 6px;
    min-height: 40px;
    max-height: 40px;
}

/* Colonnes principales nettes et modernes sans bordures */
QFrame#LeftColFrame {
    background-color: #222222;
    border: none;
    border-radius: 6px;
}

QFrame#CenterColFrame {
    background-color: #222222;
    border: none;
    border-radius: 6px;
}

QFrame#RightColFrame {
    background-color: #222222;
    border: none;
    border-radius: 6px;
}

/* Cartes de groupe et lignes d'options FOMOD */
QFrame#GroupCard {
    background-color: #1a1a1a;
    border: none;
    border-radius: 6px;
}

QFrame#OptionRow {
    background-color: transparent;
    border: none;
    border-radius: 5px;
}

/* Séparateur discret sans ligne agressive */
QSplitter::handle {
    background-color: transparent;
}
QSplitter::handle:horizontal {
    width: 6px;
}
QSplitter::handle:horizontal:hover {
    background-color: rgba(14, 165, 233, 0.3);
}

/* Boutons épurés et plats sans bordures abrasives */
QPushButton {
    background-color: #262626;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #333333;
}
QPushButton:pressed {
    background-color: #222222;
}
QPushButton:disabled {
    background-color: #1e1e1e;
    color: #444444;
    border: none;
}

/* Barres de défilement douces */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #333333;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background-color: #444444;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #333333;
    min-width: 24px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #444444;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Arbre de staging et listes sans bordures parasites */
QTreeWidget, QListWidget {
    background-color: #181818;
    color: #dddddd;
    border: none;
    border-radius: 6px;
    padding: 4px;
}
QTreeWidget::item, QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #262626;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #0369a1;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #1e1e1e;
    color: #aaaaaa;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #262626;
    font-size: 11px;
    font-weight: 600;
}

/* Champs de texte et zones éditables */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #181818;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    background-color: #1e1e1e;
}
"""
