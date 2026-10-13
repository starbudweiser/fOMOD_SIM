import logging
from typing import List, Dict, Optional, Set
from PyQt6.QtCore import QThread, pyqtSignal
from ..fomod.types import (
    ArchiveIndex,
    FomodOption,
    FomodFileItem,
    FomodFolderItem,
    StagingResult,
    ConditionalInstallPattern,
)
from ..fomod.extractor import extract_archive
from ..fomod.staging import build_staging, export_staging_to_directory

logger = logging.getLogger(__name__)


class ArchiveExtractWorker(QThread):
    """Travailleur d'arrière-plan pour l'extraction et l'indexation non-bloquante d'archives."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(object, str, str)  # (ArchiveIndex, module_config_xml, info_xml)
    error = pyqtSignal(str)

    def __init__(self, target_path: str, parent=None):
        super().__init__(parent)
        self.target_path = target_path

    def run(self):
        logger.info(f"Début de l'extraction en arrière-plan : {self.target_path}")
        try:
            index, cfg_xml, info_xml = extract_archive(
                self.target_path,
                progress_cb=lambda msg: self.progress.emit(msg),
            )
            logger.info(f"Extraction terminée avec succès ({len(index.files)} fichiers indexés)")
            self.finished.emit(index, cfg_xml, info_xml)
        except Exception as e:
            logger.exception("Erreur lors de l'extraction de l'archive")
            self.error.emit(str(e))


class StagingWorker(QThread):
    """Travailleur d'arrière-plan pour le calcul non-bloquant de la simulation de staging."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # StagingResult
    error = pyqtSignal(str)

    def __init__(
        self,
        selected_options: List[FomodOption],
        required_files: List[FomodFileItem | FomodFolderItem],
        archive_index: ArchiveIndex,
        conditional_installs: Optional[List[ConditionalInstallPattern]] = None,
        active_flags: Optional[Dict[str, str]] = None,
        installed_basenames: Optional[Set[str]] = None,
        forced_items: Optional[list] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.forced_items = forced_items or []
        self.selected_options = selected_options
        self.required_files = required_files
        self.archive_index = archive_index
        self.conditional_installs = conditional_installs or []
        self.active_flags = active_flags or {}
        self.installed_basenames = installed_basenames or set()

    def run(self):
        logger.debug(f"Calcul du staging pour {len(self.selected_options)} options sélectionnées...")
        try:
            self.progress.emit("Résolution des fichiers et dossiers du staging...")
            res = build_staging(
                selected_options=self.selected_options,
                required_files=self.required_files,
                archive_index=self.archive_index,
                conditional_installs=self.conditional_installs,
                active_flags=self.active_flags,
                installed_basenames=self.installed_basenames,
                forced_items=self.forced_items,
            )
            logger.debug(f"Staging calculé : {len(res.items)} fichiers, {res.total_size} octets")
            self.finished.emit(res)
        except Exception as e:
            logger.exception("Erreur lors de la construction du staging")
            self.error.emit(str(e))


class PreviewLoadWorker(QThread):
    """Lit et décode en arrière-plan les images d'aperçu non chargées (textures DDS dans un 7z…),
    en une seule passe d'archive, puis les réduit en vignettes."""

    loaded = pyqtSignal(object)  # {chemin en minuscules: QImage}

    def __init__(self, archive_index, entries, parent=None):
        super().__init__(parent)
        self.archive_index = archive_index
        self.entries = entries

    def run(self):
        import io
        from PyQt6.QtGui import QImage
        from ..fomod.extractor import read_entries_bytes

        out = {}
        try:
            for key, data in read_entries_bytes(self.archive_index, self.entries).items():
                img = QImage()
                if not img.loadFromData(data):
                    try:
                        from PIL import Image, ImageQt

                        im = Image.open(io.BytesIO(data))
                        im.thumbnail((1280, 1280))
                        img = ImageQt.ImageQt(im.convert("RGBA")).copy()
                    except Exception as e:
                        logger.debug("Aperçu non décodable %s : %s", key, e)
                        continue
                if img.width() > 1280 or img.height() > 1280:
                    img = img.scaled(1280, 1280, aspectRatioMode=1, transformMode=1)
                out[key] = img
        except Exception:
            logger.exception("Erreur de chargement des aperçus")
        self.loaded.emit(out)


class StagingExportWorker(QThread):
    """Écrit le staging sur disque en arrière-plan (lecture des fichiers dans l'archive comprise)."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # liste des fichiers sans contenu
    error = pyqtSignal(str)

    def __init__(self, result: StagingResult, target_dir: str, archive_index: ArchiveIndex, parent=None):
        super().__init__(parent)
        self.result = result
        self.target_dir = target_dir
        self.archive_index = archive_index

    def run(self):
        try:
            failures = export_staging_to_directory(
                self.result, self.target_dir, self.archive_index, progress_cb=self.progress.emit
            )
            self.finished.emit(failures)
        except Exception as e:
            logger.exception("Erreur lors de l'écriture du staging")
            self.error.emit(str(e))
