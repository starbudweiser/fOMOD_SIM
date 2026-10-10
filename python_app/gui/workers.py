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
from ..fomod.staging import build_staging

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
        parent=None,
    ):
        super().__init__(parent)
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
            )
            logger.debug(f"Staging calculé : {len(res.items)} fichiers, {res.total_size} octets")
            self.finished.emit(res)
        except Exception as e:
            logger.exception("Erreur lors de la construction du staging")
            self.error.emit(str(e))
