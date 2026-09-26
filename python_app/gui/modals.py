import os
import logging
from typing import Optional, Set, Callable
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
    QFileDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QTabWidget,
    QWidget,
    QScrollArea,
    QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ..fomod.types import StagingResult
from ..fomod.staging import export_staging_to_zip

try:
    from ..locales import get_i18n
except (ImportError, ValueError):
    try:
        from python_app.locales import get_i18n
    except ImportError:
        from locales import get_i18n

logger = logging.getLogger(__name__)


def format_bytes(sz: int) -> str:
    if sz <= 0:
        return "0 o"
    if sz < 1024:
        return f"{sz} o"
    if sz < 1024 * 1024:
        return f"{sz / 1024:.1f} Ko"
    return f"{sz / (1024 * 1024):.2f} Mo"


class OpenModModal(QDialog):
    """Boîte de dialogue modale '📦 Ouvrir un FOMOD' harmonisée."""

    def __init__(
        self,
        parent=None,
        on_open_archive: Optional[Callable[[], None]]=None,
        on_open_folder: Optional[Callable[[], None]]=None,
        on_load_sample: Optional[Callable[[str], None]]=None,
    ):
        super().__init__(parent)
        i18n = get_i18n()
        self.setWindowTitle(i18n.get("modals", "openMod", "title", default="Ouvrir un FOMOD"))
        self.setMinimumSize(520, 480)
        self.resize(560, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1f;
                color: #ffffff;
                border: 1px solid #2e2e34;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # En-tête
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("📦  " + i18n.get("modals", "openMod", "title", default="Ouvrir un FOMOD"))
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #a1a1aa;
                font-size: 15px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #27272b;
                border-radius: 4px;
            }
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("background-color: #27272b; max-height: 1px; border: none;")
        layout.addWidget(div1)

        # Section 1 : Depuis votre ordinateur
        sec1_lbl = QLabel(i18n.get("modals", "openMod", "fromComputer", default="Depuis votre ordinateur").upper())
        sec1_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; border: none; background: transparent;")
        layout.addWidget(sec1_lbl)

        # Bouton 1 : Archive
        btn_archive = QPushButton()
        btn_archive.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_archive.setStyleSheet("""
            QPushButton {
                background-color: #212125;
                border: none;
                border-radius: 6px;
                padding: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #27272d;
            }
        """)
        btn_archive_layout = QVBoxLayout(btn_archive)
        btn_archive_layout.setContentsMargins(4, 2, 4, 2)
        btn_archive_layout.setSpacing(4)

        arch_title_row = QHBoxLayout()
        arch_title = QLabel("📦 Parcourir une archive (.ZIP, .RAR, .7Z)")
        arch_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #fbbf24; border: none; background: transparent;")
        arch_badge = QLabel("Support complet")
        arch_badge.setStyleSheet("font-size: 10px; color: #4ade80; background-color: rgba(74, 222, 128, 0.15); border: none; border-radius: 4px; padding: 2px 6px;")
        arch_title_row.addWidget(arch_title)
        arch_title_row.addStretch()
        arch_title_row.addWidget(arch_badge)
        btn_archive_layout.addLayout(arch_title_row)

        arch_desc = QLabel("Sélectionnez directement votre archive téléchargée (.zip, .rar ou .7z). Extraction et simulation instantanées.")
        arch_desc.setWordWrap(True)
        arch_desc.setStyleSheet("font-size: 11px; color: #a1a1aa; border: none; background: transparent;")
        btn_archive_layout.addWidget(arch_desc)

        btn_archive.clicked.connect(lambda: (self.accept(), on_open_archive and on_open_archive()))
        layout.addWidget(btn_archive)

        # Bouton 2 : Dossier décompressé
        btn_folder = QPushButton()
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #212125;
                border: none;
                border-radius: 6px;
                padding: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #27272d;
            }
        """)
        btn_folder_layout = QVBoxLayout(btn_folder)
        btn_folder_layout.setContentsMargins(4, 2, 4, 2)
        btn_folder_layout.setSpacing(4)

        folder_title_row = QHBoxLayout()
        folder_title = QLabel("📂 Parcourir un dossier décompressé")
        folder_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8; border: none; background: transparent;")
        folder_badge = QLabel("Dossier local")
        folder_badge.setStyleSheet("font-size: 10px; color: #a1a1aa; padding: 2px 4px; border: none; background: transparent;")
        folder_title_row.addWidget(folder_title)
        folder_title_row.addStretch()
        folder_title_row.addWidget(folder_badge)
        btn_folder_layout.addLayout(folder_title_row)

        folder_desc = QLabel("Si vous avez déjà extrait votre mod dans un répertoire local sur votre disque, sélectionnez directement ce dossier.")
        folder_desc.setWordWrap(True)
        folder_desc.setStyleSheet("font-size: 11px; color: #a1a1aa; border: none; background: transparent;")
        btn_folder_layout.addWidget(folder_desc)

        btn_folder.clicked.connect(lambda: (self.accept(), on_open_folder and on_open_folder()))
        layout.addWidget(btn_folder)

        # Section 2 : Mods démo intégrés
        layout.addSpacing(4)
        sec2_lbl = QLabel("MODS DE DÉMONSTRATION RÉALISTES INTÉGRÉS")
        sec2_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; border: none; background: transparent;")
        layout.addWidget(sec2_lbl)

        # Démo 1 : CBBE
        btn_cbbe = QPushButton()
        btn_cbbe.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cbbe.setStyleSheet("""
            QPushButton {
                background-color: #212125;
                border: none;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #27272d;
            }
        """)
        cbbe_layout = QHBoxLayout(btn_cbbe)
        cbbe_layout.setContentsMargins(4, 2, 4, 2)
        cbbe_title = QLabel("CBBE - Caliente's Beautiful Bodies Enhancer SE")
        cbbe_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #ffffff; border: none; background: transparent;")
        cbbe_btn_tag = QLabel("Charger →")
        cbbe_btn_tag.setStyleSheet("font-size: 11px; color: #4ade80; font-weight: bold; border: none; background: transparent;")
        cbbe_layout.addWidget(cbbe_title)
        cbbe_layout.addStretch()
        cbbe_layout.addWidget(cbbe_btn_tag)
        btn_cbbe.clicked.connect(lambda: (self.accept(), on_load_sample and on_load_sample("cbbe")))
        layout.addWidget(btn_cbbe)

        # Démo 2 : SMIM
        btn_smim = QPushButton()
        btn_smim.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_smim.setStyleSheet("""
            QPushButton {
                background-color: #212125;
                border: none;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #27272d;
            }
        """)
        smim_layout = QHBoxLayout(btn_smim)
        smim_layout.setContentsMargins(4, 2, 4, 2)
        smim_title = QLabel("SMIM - Static Mesh Improvement Mod")
        smim_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #ffffff; border: none; background: transparent;")
        smim_btn_tag = QLabel("Charger →")
        smim_btn_tag.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: bold; border: none; background: transparent;")
        smim_layout.addWidget(smim_title)
        smim_layout.addStretch()
        smim_layout.addWidget(smim_btn_tag)
        btn_smim.clicked.connect(lambda: (self.accept(), on_load_sample and on_load_sample("smim")))
        layout.addWidget(btn_smim)

        layout.addStretch()


class DataDirModal(QDialog):
    """Boîte de dialogue 'Choisir le dossier Data de Skyrim' harmonisée."""

    def __init__(
        self,
        current_data_path: Optional[str]=None,
        installed_plugins: Optional[Set[str]]=None,
        on_apply: Optional[Callable[[str, Set[str]], None]]=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Dossier Data de Skyrim")
        self.setMinimumSize(540, 420)
        self.resize(580, 440)
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1f;
                color: #ffffff;
                border: 1px solid #2e2e34;
                border-radius: 8px;
            }
        """)

        self.data_path = current_data_path or ""
        self.plugins = set(installed_plugins) if installed_plugins else set()
        self.on_apply = on_apply

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        title_lbl = QLabel("📂  Dossier Data de Skyrim (Détection automatique)")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        layout.addWidget(title_lbl)

        info_lbl = QLabel(
            "Le simulateur FOMOD peut inspecter votre dossier Skyrim Special Edition/Data "
            "pour pré-sélectionner automatiquement les options requises ou compatibles."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("font-size: 12px; color: #a1a1aa; line-height: 1.4; border: none; background: transparent;")
        layout.addWidget(info_lbl)

        # Chemin actuel
        path_box = QFrame()
        path_box.setStyleSheet("background-color: #161618; border: none; border-radius: 6px; padding: 10px;")
        path_layout = QVBoxLayout(path_box)
        path_layout.setContentsMargins(4, 4, 4, 4)
        path_hdr = QLabel("Répertoire actuellement lié :")
        path_hdr.setStyleSheet("font-size: 10px; font-weight: bold; color: #888888; border: none; background: transparent;")
        path_layout.addWidget(path_hdr)

        self.path_val_lbl = QLabel(self.data_path or "(Aucun dossier sélectionné)")
        self.path_val_lbl.setStyleSheet("font-size: 12px; font-family: 'Menlo', monospace; color: #38bdf8; border: none; background: transparent;")
        path_layout.addWidget(self.path_val_lbl)
        layout.addWidget(path_box)

        # Boutons d'action
        btn_row = QHBoxLayout()
        pick_btn = QPushButton("📁 Parcourir le disque...")
        pick_btn.setStyleSheet("""
            QPushButton {
                background-color: #28282c;
                border: none;
                color: #ffffff;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #323238;
            }
        """)
        pick_btn.clicked.connect(self._pick_folder)
        btn_row.addWidget(pick_btn)

        sim_btn = QPushButton("⚡ Simuler plugins Skyrim (CBPC, SkyUI, skee64)")
        sim_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                border: none;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
        """)
        sim_btn.clicked.connect(self._simulate_plugins)
        btn_row.addWidget(sim_btn)
        layout.addLayout(btn_row)

        # Fichiers détectés
        self.detected_lbl = QLabel(f"Plugins et DLLs détectés ({len(self.plugins)}) :")
        self.detected_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; margin-top: 4px; border: none; background: transparent;")
        layout.addWidget(self.detected_lbl)

        self.plugins_text = QTextEdit()
        self.plugins_text.setReadOnly(True)
        self.plugins_text.setStyleSheet("background-color: #161618; border: none; color: #d4d4d8; font-family: 'Menlo', monospace; font-size: 11px; padding: 6px; border-radius: 6px;")
        self._update_plugins_display()
        layout.addWidget(self.plugins_text)

        # Bouton fermer
        close_btn = QPushButton("Valider & Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        close_btn.clicked.connect(self._apply_and_close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier Skyrim Data")
        if folder:
            self.data_path = folder
            self.path_val_lbl.setText(folder)
            found = set()
            try:
                for _root, _, files in os.walk(folder):
                    for f in files:
                        lower = f.lower()
                        if lower.endswith((".esp", ".esm", ".esl", ".dll", ".bsa", ".ba2")):
                            found.add(lower)
            except Exception as e:
                logger.error("Erreur scan dossier Data: %s", e)
            self.plugins = found
            self._update_plugins_display()

    def _simulate_plugins(self):
        self.data_path = "C:/Program Files/Steam/steamapps/common/Skyrim Special Edition/Data"
        self.path_val_lbl.setText(self.data_path)
        self.plugins = {
            "skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm", "dragonborn.esm",
            "skyui_se.esp", "cbpc.dll", "skee64.dll", "hdtsmp64.dll", "lanterns of skyrim ii.esm",
            "jks skyrim.esp", "elfx - exteriors.esp", "windhelm_braziers.esp", "gourmettables.esp",
        }
        self._update_plugins_display()

    def _update_plugins_display(self):
        display_plugins = [p for p in self.plugins if p.endswith((".esp", ".esm", ".esl", ".dll", ".bsa", ".ba2"))]
        self.detected_lbl.setText(f"Plugins et DLLs détectés ({len(display_plugins)}) :")
        if display_plugins:
            self.plugins_text.setText("\n".join(sorted(display_plugins)))
        else:
            self.plugins_text.setText("(Aucun plugin détecté)")

    def _apply_and_close(self):
        if self.on_apply:
            self.on_apply(self.data_path, self.plugins)
        self.accept()


class StagingResultModal(QDialog):
    """Boîte de dialogue modale affichant les résultats de la génération du staging."""

    def __init__(
        self,
        result: StagingResult,
        staging_dir_path: str="Bureau (Desktop)",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Staging généré avec succès")
        self.setMinimumSize(780, 560)
        self.resize(860, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1f;
                color: #ffffff;
                border: 1px solid #2e2e34;
                border-radius: 8px;
            }
        """)
        self.result = result
        self.staging_dir_path = staging_dir_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # En-tête de succès
        top_row = QHBoxLayout()
        icon_lbl = QLabel("✓")
        icon_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #0ea5e9; border: none; background: transparent;")
        title_lbl = QLabel("Staging généré avec succès !")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #a1a1aa;
                font-size: 15px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #27272b;
                border-radius: 4px;
            }
        """)
        close_btn.clicked.connect(self.accept)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        sub_info = QLabel(
            f"<b>{result.copied_count}</b> fichiers préparés &bull; "
            f"Taille totale : <b>{format_bytes(result.total_size)}</b> &bull; "
            f"Destination : <span style='color:#38bdf8;'>{staging_dir_path}</span>"
        )
        sub_info.setStyleSheet("font-size: 12px; color: #a1a1aa; border: none; background: transparent;")
        layout.addWidget(sub_info)

        # Onglets : Fichiers installés / Journal
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #161618;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #202024;
                color: #a1a1aa;
                padding: 6px 16px;
                border: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #161618;
                color: #0ea5e9;
                font-weight: bold;
                border: none;
            }
        """)

        # Tab 1 : Arborescence
        tab_files = QWidget()
        tab_files_layout = QVBoxLayout(tab_files)
        tab_files_layout.setContentsMargins(8, 8, 8, 8)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Destination dans Data", "Taille", "Source Option"])
        tree.setStyleSheet("""
            QTreeWidget {
                background-color: #161618;
                border: none;
                color: #f4f4f5;
                font-family: 'Menlo', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #0ea5e9;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1f1f23;
                color: #a1a1aa;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid #27272b;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        dir_nodes = {}
        for item in result.items:
            parts = item.destination_path.split("/")
            parent_node = None
            cur_path = ""
            for i in range(len(parts) - 1):
                cur_path = f"{cur_path}/{parts[i]}" if cur_path else parts[i]
                if cur_path not in dir_nodes:
                    node = QTreeWidgetItem([parts[i], "Dossier", ""])
                    node.setForeground(0, Qt.GlobalColor.cyan)
                    if parent_node:
                        parent_node.addChild(node)
                    else:
                        tree.addTopLevelItem(node)
                    node.setExpanded(True)
                    dir_nodes[cur_path] = node
                parent_node = dir_nodes[cur_path]

            file_leaf = QTreeWidgetItem([parts[-1], format_bytes(item.size), item.matched_from_option])
            if parent_node:
                parent_node.addChild(file_leaf)
            else:
                tree.addTopLevelItem(file_leaf)

        tab_files_layout.addWidget(tree)
        tabs.addTab(tab_files, "Fichiers installés")

        # Tab 2 : Journal
        tab_log = QWidget()
        tab_log_layout = QVBoxLayout(tab_log)
        tab_log_layout.setContentsMargins(8, 8, 8, 8)
        log_edit = QTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setStyleSheet("background-color: #161618; border: none; color: #a1a1aa; font-family: 'Menlo', monospace; font-size: 11px;")
        log_edit.setText("\n".join(result.log) if result.log else "Aucun avertissement. Installation propre.")
        tab_log_layout.addWidget(log_edit)
        tabs.addTab(tab_log, "Journal de staging")

        layout.addWidget(tabs)

        # Boutons d'action en bas
        btn_bar = QHBoxLayout()
        export_zip_btn = QPushButton("📦 Exporter en archive ZIP")
        export_zip_btn.setStyleSheet("""
            QPushButton {
                background-color: #28282c;
                border: none;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #323238;
            }
        """)
        export_zip_btn.clicked.connect(self._export_zip)
        btn_bar.addWidget(export_zip_btn)

        btn_bar.addStretch()

        close_dialog_btn = QPushButton("Fermer")
        close_dialog_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        close_dialog_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_dialog_btn)

        layout.addLayout(btn_bar)

    def _export_zip(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le mod prêt pour MO2 / Vortex",
            "Staging_Skyrim_Mod.zip",
            "Archive ZIP (*.zip)",
        )
        if path:
            try:
                export_staging_to_zip(self.result, path)
            except Exception as e:
                logger.error("Erreur lors de l'export ZIP: %s", e)


class ImagePreviewModal(QDialog):
    """Boîte de dialogue affichant l'image d'aperçu dans sa taille réelle."""

    def __init__(self, pixmap: QPixmap, title: str="Aperçu FOMOD", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Aperçu taille réelle — {title}")

        screen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else None
        max_w = (screen_geom.width() - 80) if screen_geom else 1200
        max_h = (screen_geom.height() - 100) if screen_geom else 800

        target_w = min(max(pixmap.width() + 40, 500), max_w)
        target_h = min(max(pixmap.height() + 70, 400), max_h)

        self.resize(target_w, target_h)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #141416;
                border: 1px solid #2e2e34;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #161618;
                border: none;
                border-radius: 6px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: transparent;
                width: 6px;
                height: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background-color: #333338;
                border-radius: 3px;
            }
            QScrollBar::handle:hover {
                background-color: #0ea5e9;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: #161618; border: none;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setPixmap(pixmap)
        lbl.setFixedSize(pixmap.size())
        container_layout.addWidget(lbl)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        bottom_bar = QHBoxLayout()
        res_info = QLabel(f"Dimensions : {pixmap.width()} × {pixmap.height()} px (taille réelle)")
        res_info.setStyleSheet("color: #a1a1aa; font-size: 11px; background: transparent; border: none;")
        bottom_bar.addWidget(res_info)

        bottom_bar.addStretch()

        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #28282c;
                color: #ffffff;
                padding: 6px 16px;
                border-radius: 5px;
                border: none;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #323238;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)
