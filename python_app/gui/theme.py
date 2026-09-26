"""Thème graphique Qt Style Sheets (QSS) moderne, borderless et épuré pour le Simulateur FOMOD."""

DARK_THEME_QSS = """
/* ==========================================================================
   SIMULATEUR FOMOD - DESIGN SYSTEM BORDERLESS ÉPURÉ
   Bordures superflues supprimées | Surfaces sombres hiérarchisées
   ========================================================================== */

QMainWindow {
    background-color: #18181b;
    color: #e4e4e7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QDialog {
    background-color: #1c1c1f;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    border: 1px solid #27272a;
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
    background-color: #202023;
    border: none;
    border-radius: 6px;
    min-height: 40px;
    max-height: 40px;
}

/* Colonnes principales nettes et modernes sans bordures */
QFrame#LeftColFrame {
    background-color: #202023;
    border: none;
    border-radius: 6px;
}

QFrame#CenterColFrame {
    background-color: #202023;
    border: none;
    border-radius: 6px;
}

QFrame#RightColFrame {
    background-color: #202023;
    border: none;
    border-radius: 6px;
}

/* Cartes de groupe et lignes d'options FOMOD */
QFrame#GroupCard {
    background-color: #1a1a1d;
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
    background-color: #28282c;
    color: #f4f4f5;
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #35353c;
}
QPushButton:pressed {
    background-color: #202024;
}
QPushButton:disabled {
    background-color: #1c1c1f;
    color: #52525b;
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
    background-color: #333338;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4f4f56;
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
    background-color: #333338;
    min-width: 24px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #4f4f56;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Arbre de staging et listes sans bordures parasites */
QTreeWidget, QListWidget {
    background-color: #161618;
    color: #e4e4e7;
    border: none;
    border-radius: 6px;
    padding: 4px;
}
QTreeWidget::item, QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #26262a;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #0369a1;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #1f1f23;
    color: #a1a1aa;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #27272a;
    font-size: 11px;
    font-weight: 600;
}

/* Champs de texte et zones éditables */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #161618;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    background-color: #1c1c20;
}
"""
