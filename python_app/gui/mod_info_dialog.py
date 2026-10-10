import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
)
from PyQt6.QtCore import Qt
from ..fomod.types import FomodMetadata

try:
    from ..locales import get_i18n
except (ImportError, ValueError):
    try:
        from python_app.locales import get_i18n
    except ImportError:
        from locales import get_i18n

logger = logging.getLogger(__name__)


class ModInfoDialog(QDialog):
    """Boîte de dialogue affichant les métadonnées détaillées du mod (info.xml) avec design moderne sans bordures parasites."""

    def __init__(self, metadata: FomodMetadata, parent=None):
        super().__init__(parent)
        i18n = get_i18n()
        self.setWindowTitle(f"{i18n.get('modals', 'modInfo', 'title', default='Infos du mod')} - {metadata.name}")
        self.setMinimumSize(540, 420)
        self.resize(600, 460)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #262626;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Titre
        title_label = QLabel(metadata.name)
        title_label.setStyleSheet("font-size: 17px; font-weight: bold; color: #fbbf24; border: none; background: transparent;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Ligne Auteur / Version
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        author_str = i18n.get("modals", "modInfo", "author", default="Auteur")
        author_label = QLabel(f"<b>{author_str} :</b> {metadata.author or '—'}")
        author_label.setStyleSheet("color: #aaaaaa; border: none; background: transparent;")
        meta_row.addWidget(author_label)

        version_str = i18n.get("modals", "modInfo", "version", default="Version")
        version_label = QLabel(f"<b>{version_str} :</b> {metadata.version or '1.0'}")
        version_label.setStyleSheet("color: #38bdf8; border: none; background: transparent;")
        meta_row.addWidget(version_label)

        meta_row.addStretch()
        layout.addLayout(meta_row)

        # Site web
        if metadata.website:
            site_str = i18n.get("modals", "modInfo", "website", default="Site Web")
            site_label = QLabel(f"<b>{site_str} :</b> <a style='color:#38bdf8;' href='{metadata.website}'>{metadata.website}</a>")
            site_label.setOpenExternalLinks(True)
            site_label.setStyleSheet("border: none; background: transparent;")
            layout.addWidget(site_label)

        # Séparateur subtil
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #262626; max-height: 1px; border: none;")
        layout.addWidget(sep)

        # Description
        desc_str = i18n.get("modals", "modInfo", "description", default="Description")
        desc_title = QLabel(f"{desc_str} :")
        desc_title.setStyleSheet("font-weight: 600; color: #dddddd; border: none; background: transparent;")
        layout.addWidget(desc_title)

        desc_box = QTextEdit()
        desc_box.setReadOnly(True)
        desc_box.setPlainText(metadata.description or "")
        desc_box.setStyleSheet(
            "background-color: #181818; border: none; border-radius: 6px; padding: 10px; color: #dddddd; font-size: 13px; line-height: 1.5;"
        )
        layout.addWidget(desc_box)

        # Bouton Fermer
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(i18n.get("common", "close", default="Fermer"))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #262626;
                color: #ffffff;
                padding: 8px 20px;
                border-radius: 5px;
                border: none;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
