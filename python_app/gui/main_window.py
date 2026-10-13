import os
import sys
import logging
from typing import List, Dict, Optional, Set
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QResizeEvent, QPixmap

from ..fomod.types import (
    FomodStep,
    FomodGroup,
    FomodOption,
    FomodFileItem,
    FomodFolderItem,
    FomodMetadata,
    ArchiveIndex,
    GroupType,
    StagingResult,
    ConditionalInstallPattern,
)
from ..fomod.parser import (
    parse_module_config_xml,
    parse_info_xml,
    option_matches_installed,
)
from ..fomod.plugins import annotate_option_masters
from ..fomod.demo_mod import get_demo_mod
from ..fomod.session import InstallSession
from .workers import ArchiveExtractWorker, StagingWorker, PreviewLoadWorker, StagingExportWorker
from ..fomod.preview import pick_preview_entries
from .mod_info_dialog import ModInfoDialog
from .modals import OpenModModal, DataDirModal, StagingResultModal, ImagePreviewModal
from .preview_generator import get_preview_pixmap_for_path, load_pixmap_safely

try:
    from ..locales import get_i18n, AVAILABLE_LANGUAGES
except (ImportError, ValueError):
    try:
        from python_app.locales import get_i18n, AVAILABLE_LANGUAGES
    except ImportError:
        from locales import get_i18n, AVAILABLE_LANGUAGES



logger = logging.getLogger(__name__)


class FitImageLabel(QLabel):
    """Image d'aperçu ajustée à la place disponible (largeur de la colonne d'abord), centrée,
    proportions conservées ; recalculée à chaque redimensionnement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: Optional[QPixmap] = None
        # Taille ignorée : le label prend la place que lui donne la mise en page, pas celle de l'image
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    def set_source(self, pixmap: Optional[QPixmap]) -> None:
        self._source = pixmap if pixmap is not None and not pixmap.isNull() else None
        self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source is None or self.width() < 2 or self.height() < 2:
            self.clear()
            return
        self.setPixmap(self._source.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))


def format_bytes(sz: int) -> str:
    if sz <= 0:
        return "0 o"
    if sz < 1024:
        return f"{sz} o"
    if sz < 1024 * 1024:
        return f"{sz / 1024:.1f} Ko"
    return f"{sz / (1024 * 1024):.2f} Mo"


class CircularSpinnerWidget(QWidget):
    """Spinner circulaire animé identique à l'interface web (Screenshot 3)."""

    def __init__(self, size: int=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.start(25)

    def _rotate(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)

        # Anneau de fond estompé
        pen_bg = QPen(QColor(56, 189, 248, 50), 4)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawEllipse(rect)

        # Arc tournant actif
        pen_fg = QPen(QColor("#38bdf8"), 4)
        pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)
        painter.drawArc(rect, -self.angle * 16, 90 * 16)


class DragOverlayWidget(QWidget):
    """Overlay plein écran affiché lors du survol Drag & Drop d'une archive (Screenshot 2)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("DragCard")
        card.setFixedWidth(520)
        card.setStyleSheet("""
            QFrame#DragCard {
                background-color: #1e1e1e;
                border: 1px solid #0ea5e9;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 28, 24, 28)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("📥")
        icon_lbl.setFont(QFont("Apple Color Emoji", 36))
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Déposez l'archive (ZIP, RAR, 7Z) du mod FOMOD ici")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_lbl)

        sub_lbl = QLabel("Extraction et analyse instantanées")
        sub_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #0ea5e9; border: none; background: transparent;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(sub_lbl)

        layout.addWidget(card)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fond bleu sombre semi-transparent
        painter.fillRect(self.rect(), QColor(10, 25, 45, 195))

        # Bordure pointillée cyan
        pen = QPen(QColor("#0369a1"), 3, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 6])
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(6, 6, -6, -6))


class LoadingOverlayWidget(QWidget):
    """Modal plein écran avec spinner circulaire animé affiché lors du chargement (Screenshot 3)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("LoadingCard")
        card.setFixedWidth(480)
        card.setStyleSheet("""
            QFrame#LoadingCard {
                background-color: #222222;
                border: 1px solid rgba(56, 189, 248, 0.6);
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner animé
        self.spinner = CircularSpinnerWidget(48)
        card_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("Chargement du mod FOMOD")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_lbl)

        # Zone monospace d'état
        status_box = QFrame()
        status_box.setObjectName("StatusBox")
        status_box.setStyleSheet("""
            QFrame#StatusBox {
                background-color: #181818;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)
        sb_layout = QVBoxLayout(status_box)
        sb_layout.setContentsMargins(14, 10, 14, 10)
        self.status_lbl = QLabel("Extraction et analyse des fichiers de l'archive...")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-family: 'Menlo', monospace; font-size: 11px; border: none; background: transparent;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb_layout.addWidget(self.status_lbl)
        card_layout.addWidget(status_box)

        sub_lbl = QLabel("Extraction en mémoire et génération de l'installateur à 3 colonnes...")
        sub_lbl.setStyleSheet("font-size: 11px; color: #8f8f8f; border: none; background: transparent;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(sub_lbl)

        layout.addWidget(card)

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 204))  # 80% opacité sombre


class IndicatorWidget(QWidget):
    """Indicateur visuel personnalisé (Radio rond ou Checkbox carré) harmonisé."""

    def __init__(self, is_single: bool, is_checked: bool, parent=None):
        super().__init__(parent)
        self.is_single = is_single
        self.is_checked = is_checked
        self.setFixedSize(18, 18)

    def set_checked(self, checked: bool):
        self.is_checked = checked
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        if self.is_single:
            # Radio circulaire
            if self.is_checked:
                painter.setPen(QPen(QColor("#0ea5e9"), 1.2))
                painter.setBrush(QBrush(QColor("#0ea5e9")))
                painter.drawEllipse(rect)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor("#ffffff")))
                painter.drawEllipse(rect.center(), 3, 3)
            else:
                painter.setPen(QPen(QColor("#444444"), 1.2))
                painter.setBrush(QBrush(QColor("#1e1e1e")))
                painter.drawEllipse(rect)
        else:
            # Checkbox carré arrondi
            if self.is_checked:
                painter.setPen(QPen(QColor("#0ea5e9"), 1.2))
                painter.setBrush(QBrush(QColor("#0ea5e9")))
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QPen(QColor("#ffffff"), 1.8))
                painter.drawLine(rect.left() + 4, rect.top() + 8, rect.left() + 7, rect.bottom() - 4)
                painter.drawLine(rect.left() + 7, rect.bottom() - 4, rect.right() - 4, rect.top() + 5)
            else:
                painter.setPen(QPen(QColor("#444444"), 1.2))
                painter.setBrush(QBrush(QColor("#1e1e1e")))
                painter.drawRoundedRect(rect, 4, 4)

        painter.end()


class OptionRowWidget(QFrame):
    """Ligne d'option FOMOD avec survol fluide et sélection harmonisée."""

    def __init__(
        self,
        option: FomodOption,
        is_single: bool,
        is_selected: bool,
        matches_dep: bool,
        on_select_callback=None,
        on_hover_callback=None,
        on_select=None,
        on_hover=None,
        parent=None,
    ):
        super().__init__(parent)
        self.option = option
        self.is_single = is_single
        self.is_selected = is_selected
        self.on_select_callback = on_select_callback if on_select_callback is not None else (on_select if on_select is not None else (lambda _opt: None))
        self.on_hover_callback = on_hover_callback if on_hover_callback is not None else (on_hover if on_hover is not None else (lambda _opt: None))
        self.setObjectName("OptionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Indicateur radio ou case à cocher
        self.indicator = IndicatorWidget(is_single, is_selected)
        layout.addWidget(self.indicator, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Libellé de l'option
        self.label = QLabel(option.name)
        layout.addWidget(self.label, 1)

        # Badge Auto sans bordure abrasive
        if matches_dep:
            auto_txt = get_i18n().get("common", "auto", default="Auto")
            badge = QLabel(auto_txt)
            badge.setStyleSheet(
                "background-color: rgba(14, 165, 233, 0.15); color: #38bdf8; font-size: 9px; font-weight: 600; padding: 2px 6px; border-radius: 4px; border: none;"
            )
            layout.addWidget(badge)

        self._update_style()

    def _update_style(self, hovered: bool=False):
        if self.is_selected:
            bg = "#262626"
            text_color = "#38bdf8"
            weight = "600"
        elif hovered:
            bg = "#262626"
            text_color = "#ffffff"
            weight = "normal"
        else:
            bg = "transparent"
            text_color = "#dddddd"
            weight = "normal"

        self.setStyleSheet(f"QFrame#OptionRow {{ background-color: {bg}; border: none; border-radius: 5px; }}")
        self.label.setStyleSheet(f"background: transparent; border: none; font-size: 12px; font-weight: {weight}; color: {text_color};")

    def enterEvent(self, event):
        self._update_style(hovered=True)
        self.on_hover_callback(self.option)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style(hovered=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_select_callback(self.option)
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    """Fenêtre principale de fOMODSIM en PyQt6 avec fidélité visuelle stricte."""

    def __init__(self):
        super().__init__()
        self.i18n = get_i18n()
        app = QApplication.instance()
        if app and sys.platform == "darwin":
            app.setFont(QFont(".AppleSystemUIFont", 13))
        self.setWindowTitle(self.i18n.get("header", "title"))
        self.resize(1340, 840)
        self.setMinimumSize(1000, 680)

        # État interne
        self.archive_index: ArchiveIndex = ArchiveIndex()
        self.metadata: FomodMetadata = FomodMetadata(
            name="fOMODSIM",
            author="",
            version="1.0.0",
            website="",
            description="",
        )
        self.steps: List[FomodStep] = []
        self.required_files = []
        self.conditional_installs: List[ConditionalInstallPattern] = []
        self.current_step_idx = 0
        self.session: Optional[InstallSession] = None
        self.active_preview_option: Optional[FomodOption] = None
        self._preview_cache: Dict[str, object] = {}  # chemin -> QImage décodée
        self._preview_worker = None
        self._preview_pending = False
        self.current_staging_result: Optional[StagingResult] = None
        self.installed_basenames: Set[str] = set()

        # Chemins de staging et data
        self.data_dir_path: Optional[str] = None
        self.staging_dir_path: str = "Bureau (Desktop)"
        self.staging_dir_chosen: bool = False  # vrai une fois un dossier choisi par l'utilisateur

        # Tree widget invisible maintenu pour rétro-compatibilité
        self.staging_tree = QTreeWidget()
        self.staging_tree.setHeaderLabels(["Destination dans Data", "Taille", "Source Option"])

        # Workers d'arrière-plan
        self._extract_worker: Optional[ArchiveExtractWorker] = None
        self._staging_worker: Optional[StagingWorker] = None
        self._export_worker: Optional[StagingExportWorker] = None

        self._init_ui()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if hasattr(self, "drag_overlay"):
            self.drag_overlay.resize(self.size())
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.resize(self.size())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drag_overlay.resize(self.size())
            self.drag_overlay.show()
            self.drag_overlay.raise_()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if not self.drag_overlay.isVisible():
                self.drag_overlay.resize(self.size())
                self.drag_overlay.show()
                self.drag_overlay.raise_()

    def dragLeaveEvent(self, event):
        self.drag_overlay.hide()
        event.accept()

    def dropEvent(self, event):
        self.drag_overlay.hide()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self._load_archive(path)

    def _init_ui(self):
        self.setAcceptDrops(True)
        central = QWidget()
        central.setObjectName("RootWidget")
        central.setStyleSheet("QWidget#RootWidget { background-color: #181818; }")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. En-tête supérieur persistant (Présent sur l'accueil et le simulateur)
        self.header_widget = self._create_header()
        root_layout.addWidget(self.header_widget)

        # 2. Pile centrale
        self.central_stack = QStackedWidget()

        # Page 0 : Accueil
        self.welcome_widget = self._create_welcome_view()
        self.central_stack.addWidget(self.welcome_widget)

        # Page 1 : Interface simulateur 3 colonnes
        self.simulator_widget = self._create_simulator_view()
        self.central_stack.addWidget(self.simulator_widget)

        root_layout.addWidget(self.central_stack, 1)
        self.central_stack.setCurrentIndex(0)

        # Overlays Drag & Drop et Chargement
        self.drag_overlay = DragOverlayWidget(self)
        self.drag_overlay.hide()

        self.loading_overlay = LoadingOverlayWidget(self)
        self.loading_overlay.hide()

        self._update_header()
        self._update_lang_selector_ui()
        self.retranslate_ui()

    def _create_welcome_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(580)
        card.setObjectName("WelcomeCard")
        card.setStyleSheet("""
            QFrame#WelcomeCard {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 20, 28, 24)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 0. Boutons de choix de langue centrés et compacts
        lang_bar = QWidget()
        lang_bar_layout = QHBoxLayout(lang_bar)
        lang_bar_layout.setContentsMargins(0, 0, 0, 0)
        lang_bar_layout.setSpacing(6)
        lang_bar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.welcome_lang_buttons: Dict[str, QPushButton] = {}
        for code, label, flag in AVAILABLE_LANGUAGES:
            btn = QPushButton(f"{flag} {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(25)
            btn.clicked.connect(lambda _checked, c=code: self._change_language(c))
            self.welcome_lang_buttons[code] = btn
            lang_bar_layout.addWidget(btn)

        card_layout.addWidget(lang_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        lang_divider = QFrame()
        lang_divider.setFrameShape(QFrame.Shape.HLine)
        lang_divider.setStyleSheet("background-color: #2c2c2c; max-height: 1px; border: none; margin-bottom: 2px;")
        card_layout.addWidget(lang_divider)

        # Badge circulaire avec icône 📦
        badge = QFrame()
        badge.setObjectName("WelcomeBadge")
        badge.setFixedSize(64, 64)
        badge.setStyleSheet("""
            QFrame#WelcomeBadge {
                background-color: #262626;
                border: 1px solid #404040;
                border-radius: 32px;
            }
        """)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_icon = QLabel("📦")
        badge_icon.setFont(QFont("Apple Color Emoji", 26))
        badge_icon.setStyleSheet("border: none; background: transparent;")
        badge_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(badge_icon)
        card_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        self.welcome_title_lbl = QLabel(self.i18n.get("welcome", "title"))
        self.welcome_title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff; border: none; background: transparent; letter-spacing: 0.5px;")
        self.welcome_title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.welcome_title_lbl)

        self.welcome_sub_lbl = QLabel(self.i18n.get("welcome", "subtitle"))
        self.welcome_sub_lbl.setWordWrap(True)
        self.welcome_sub_lbl.setStyleSheet("font-size: 12px; color: #8f8f8f; border: none; line-height: 1.5; background: transparent;")
        self.welcome_sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.welcome_sub_lbl)

        # Zone Drop mTranslator
        drop_frame = QFrame()
        drop_frame.setObjectName("WelcomeDropFrame")
        drop_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        drop_frame.setStyleSheet("""
            QFrame#WelcomeDropFrame {
                background-color: #1a1a1a;
                border: 2px dashed #444444;
                border-radius: 8px;
            }
            QFrame#WelcomeDropFrame:hover {
                border-color: #38bdf8;
                background-color: #222222;
            }
        """)
        drop_frame.mousePressEvent = lambda _e: self._pick_archive_file()
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setContentsMargins(20, 24, 20, 24)
        drop_layout.setSpacing(10)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tray_icon = QLabel("📥")
        tray_icon.setFont(QFont("Apple Color Emoji", 30))
        tray_icon.setStyleSheet("border: none; background: transparent;")
        tray_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(tray_icon)

        self.welcome_drop_txt = QLabel(self.i18n.get("welcome", "dropTitle"))
        self.welcome_drop_txt.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffffff; border: none; background: transparent;")
        self.welcome_drop_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.welcome_drop_txt)

        self.welcome_fmt_txt = QLabel(self.i18n.get("welcome", "supportedFormats"))
        self.welcome_fmt_txt.setTextFormat(Qt.TextFormat.RichText)
        self.welcome_fmt_txt.setStyleSheet("font-size: 11px; color: #707070; border: none; background: transparent;")
        self.welcome_fmt_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.welcome_fmt_txt)

        self.welcome_btn_archive = QPushButton("📁  " + self.i18n.get("welcome", "loadArchiveBtn"))
        self.welcome_btn_archive.setFixedHeight(38)
        self.welcome_btn_archive.setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_btn_archive.setStyleSheet("""
            QPushButton {
                background-color: #fbbf24;
                color: #1a1a1a;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 20px;
                border: none;
            }
            QPushButton:hover { background-color: #f59e0b; }
            QPushButton:pressed { background-color: #d97706; }
        """)
        self.welcome_btn_archive.clicked.connect(self._pick_archive_file)
        drop_layout.addWidget(self.welcome_btn_archive, alignment=Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(drop_frame)

        # Actions secondaires
        sub_actions = QHBoxLayout()
        sub_actions.setSpacing(12)
        sub_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.welcome_btn_folder = QPushButton("📂  " + self.i18n.get("welcome", "loadFolderBtn"))
        self.welcome_btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_btn_folder.setStyleSheet("color: #8f8f8f; font-size: 12px; background: transparent; border: none; text-decoration: underline;")
        self.welcome_btn_folder.clicked.connect(self._pick_folder_mod)
        sub_actions.addWidget(self.welcome_btn_folder)

        sep = QLabel("•")
        sep.setStyleSheet("color: #444444; border: none; background: transparent;")
        sub_actions.addWidget(sep)

        self.welcome_btn_demo = QPushButton("🧪  " + self.i18n.get("welcome", "loadDemoBtn"))
        self.welcome_btn_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_btn_demo.setStyleSheet("color: #8f8f8f; font-size: 12px; background: transparent; border: none; text-decoration: underline;")
        self.welcome_btn_demo.clicked.connect(self.load_demo_mod)
        sub_actions.addWidget(self.welcome_btn_demo)

        card_layout.addLayout(sub_actions)

        # Ligne de séparation et pied de carte
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #2c2c2c; max-height: 1px; border: none; margin-top: 10px;")
        card_layout.addWidget(divider)

        footer_box = QHBoxLayout()
        self.welcome_f_left = QLabel(self.i18n.get("welcome", "standaloneEngine"))
        self.welcome_f_left.setStyleSheet("color: #666666; font-size: 11px; border: none; background: transparent;")
        footer_box.addWidget(self.welcome_f_left)
        footer_box.addStretch()
        self.welcome_f_right = QLabel(self.i18n.get("welcome", "noGameRequired"))
        self.welcome_f_right.setStyleSheet("color: #666666; font-size: 11px; border: none; background: transparent;")
        footer_box.addWidget(self.welcome_f_right)

        card_layout.addLayout(footer_box)

        layout.addWidget(card)
        return container

    def _create_simulator_view(self) -> QWidget:
        sim_widget = QWidget()
        layout = QVBoxLayout(sim_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Splitter 3 Colonnes (195 / 345 / 460)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self._create_left_column())
        self.splitter.addWidget(self._create_center_column())
        self.splitter.addWidget(self._create_right_column())
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([195, 345, 460])
        layout.addWidget(self.splitter, 1)

        return sim_widget

    def _change_language(self, lang_code: str):
        self.i18n.set_language(lang_code)
        self._update_lang_selector_ui()
        self.retranslate_ui()

    def _on_header_lang_changed(self, idx: int):
        if 0 <= idx < len(AVAILABLE_LANGUAGES):
            lang_code = AVAILABLE_LANGUAGES[idx][0]
            if lang_code != self.i18n.current_language:
                self._change_language(lang_code)

    def _update_lang_selector_ui(self):
        curr = self.i18n.current_language
        for code, btn in getattr(self, "welcome_lang_buttons", {}).items():
            if code == curr:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0ea5e9;
                        color: #ffffff;
                        font-weight: 600;
                        font-size: 11px;
                        border-radius: 5px;
                        border: 1px solid #0ea5e9;
                        padding: 0 9px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2a2a2a;
                        color: #aaaaaa;
                        font-weight: 500;
                        font-size: 11px;
                        border-radius: 5px;
                        border: 1px solid #2a2a2a;
                        padding: 0 9px;
                    }
                    QPushButton:hover {
                        background-color: #333333;
                        border-color: #333333;
                        color: #ffffff;
                    }
                """)

        if hasattr(self, "header_lang_combo"):
            self.header_lang_combo.blockSignals(True)
            for i, (code, _l, _f) in enumerate(AVAILABLE_LANGUAGES):
                if code == curr:
                    self.header_lang_combo.setCurrentIndex(i)
                    break
            self.header_lang_combo.blockSignals(False)

    def _update_data_status_label(self):
        if not hasattr(self, "data_status_label"):
            return
        i18n = getattr(self, "i18n", None)
        data_lbl = i18n.get("common", "dataFolder", default="Data :") if i18n else "Data :"
        click_lbl = i18n.get("common", "clickToSimulate", default="(Cliquez pour simuler Skyrim)") if i18n else "(Cliquez pour simuler Skyrim)"
        if self.data_dir_path:
            count = len(self.installed_basenames)
            files_lbl = i18n.get("common", "filesDetected", default="fichiers détectés") if i18n else "fichiers détectés"
            self.data_status_label.setText(
                f'<span style="font-weight:600; color:#dddddd;">{data_lbl}</span> <span style="color:#aaaaaa;">{os.path.basename(self.data_dir_path)}</span><br/><span style="color:#38bdf8; font-size:10px;">({count} {files_lbl})</span>'
            )
        else:
            not_set = i18n.get("common", "notSet", default="(non défini)") if i18n else "(non défini)"
            self.data_status_label.setText(
                f'<span style="font-weight:600; color:#dddddd;">{data_lbl}</span> <span style="font-style:italic; color:#aaaaaa;">{not_set}</span><br/><span style="color:#8f8f8f; font-size:10px;">{click_lbl}</span>'
            )

    def retranslate_ui(self):
        """Met à jour dynamiquement tous les textes de l'interface selon la langue active."""
        i18n = self.i18n
        self.setWindowTitle(i18n.get("header", "title"))

        # En-tête
        if hasattr(self, "btn_close"):
            self.btn_close.setText(i18n.get("header", "closeMod"))
            self.btn_close.setToolTip(i18n.get("header", "closeModTooltip"))
        self._update_header()

        # Écran d'accueil
        if hasattr(self, "welcome_title_lbl"):
            self.welcome_title_lbl.setText(i18n.get("welcome", "title"))
            self.welcome_sub_lbl.setText(i18n.get("welcome", "subtitle"))
            self.welcome_drop_txt.setText(i18n.get("welcome", "dropTitle"))
            self.welcome_fmt_txt.setText(i18n.get("welcome", "supportedFormats"))
            self.welcome_btn_archive.setText("📁  " + i18n.get("welcome", "loadArchiveBtn"))
            self.welcome_btn_folder.setText("📂  " + i18n.get("welcome", "loadFolderBtn"))
            self.welcome_btn_demo.setText("🧪  " + i18n.get("welcome", "loadDemoBtn"))
            self.welcome_f_left.setText(i18n.get("welcome", "standaloneEngine"))
            self.welcome_f_right.setText(i18n.get("welcome", "noGameRequired"))

        # Colonne de gauche
        if hasattr(self, "btn_open_fomod"):
            self.btn_open_fomod.setText("📦  " + i18n.get("sidebar", "openFomod"))
            self.btn_open_fomod.setToolTip(i18n.get("sidebar", "openFomodTooltip"))
        if hasattr(self, "btn_mod_info"):
            self.btn_mod_info.setText("ℹ️  " + i18n.get("sidebar", "modInfo"))
        if hasattr(self, "btn_choose_data"):
            self.btn_choose_data.setText("📁  " + i18n.get("sidebar", "chooseDataDir"))
        if hasattr(self, "btn_choose_dest"):
            self.btn_choose_dest.setText("📁  " + i18n.get("sidebar", "chooseStagingDir"))
        if hasattr(self, "dest_hdr"):
            self.dest_hdr.setText(i18n.get("common", "destination"))
        if hasattr(self, "btn_generate_staging"):
            self.btn_generate_staging.setText(i18n.get("sidebar", "generateStaging"))
        self._update_data_status_label()

        # Colonne centrale (Navigation)
        total = len(self.steps)
        if hasattr(self, "btn_prev"):
            self.btn_prev.setText(i18n.get("steps", "prevStep"))
            is_last = total > 0 and self._is_last_step()
            self.btn_next.setText(i18n.get("steps", "finishStep") if is_last else i18n.get("steps", "nextStep"))

        # Colonne de droite (Aperçu / Description)
        if hasattr(self, "right_sec_title"):
            self.right_sec_title.setText("📖  " + i18n.get("preview", "instructionsTitle").upper())

        # Si un mod est en cours, rafraîchir l'étape courante pour re-traduire les types d'options (ex: "Choix unique", "Recommandé")
        if total > 0:
            self._render_current_step()

    def _update_header(self):
        is_sim = (self.central_stack.currentIndex() == 1)
        i18n = getattr(self, "i18n", None)
        if is_sim:
            self.title_label.setText(self.metadata.name)
            self.btn_close.show()
            self.pipe1.show()
            step_num, total_steps = self._step_position()
            if i18n:
                step_str = i18n.get("header", "stepCounter", default="Étape {current} / {total}").format(
                    current=step_num, total=total_steps
                )
            else:
                step_str = f"Étape {step_num} / {total_steps}"
            self.step_counter_label.setText(step_str)
            self.step_counter_label.show()
            self.pipe2.show()
            if self.active_flags:
                if i18n:
                    flags_str = i18n.get("header", "flagsCount", default="{count} flags actifs").format(
                        count=len(self.active_flags)
                    )
                else:
                    flags_str = f"{len(self.active_flags)} flags actifs"
                self.env_badge_label.setText(flags_str)
            else:
                self.env_badge_label.setText(i18n.get("header", "skyrimEnv", default="Skyrim SE/AE") if i18n else "Skyrim SE/AE")
            self.env_badge_label.show()
        else:
            self.title_label.setText(i18n.get("header", "title", default="fOMODSIM") if i18n else "fOMODSIM")
            self.btn_close.hide()
            self.pipe1.hide()
            self.step_counter_label.hide()
            self.pipe2.hide()
            self.env_badge_label.setText(i18n.get("header", "waitingArchive", default="Skyrim SE/AE • En attente d'archive") if i18n else "Skyrim SE/AE • En attente d'archive")
            self.env_badge_label.show()

    def _close_mod(self):
        self.cleanup_workers()
        self.steps.clear()
        default_name = self.i18n.get("header", "title", default="fOMODSIM") if hasattr(self, "i18n") else "fOMODSIM"
        self.metadata = FomodMetadata(name=default_name)
        self.session = None
        self.central_stack.setCurrentIndex(0)
        self._update_header()

    # =========================================================================
    # 1. EN-TÊTE SUPÉRIEUR
    # =========================================================================

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(40)
        header.setStyleSheet("QFrame#HeaderBar { background-color: #262626; border: 1px solid #333333; border-radius: 6px; }")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Icône éclair + Titre du mod
        left_box = QHBoxLayout()
        left_box.setSpacing(8)
        bolt_icon = QLabel("⚡")
        bolt_icon.setFont(QFont("Apple Color Emoji", 13))
        bolt_icon.setStyleSheet("background: transparent; border: none;")
        left_box.addWidget(bolt_icon)

        self.title_label = QLabel(self.i18n.get("header", "title"))
        self.title_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        left_box.addWidget(self.title_label)
        layout.addLayout(left_box)

        layout.addStretch()

        # Badges droite épurés
        right_box = QHBoxLayout()
        right_box.setSpacing(8)

        self.btn_close = QPushButton(self.i18n.get("header", "closeMod"))
        self.btn_close.setFixedHeight(26)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip(self.i18n.get("header", "closeModTooltip"))
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #dddddd;
                border: 1px solid #2c2c2c;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #333333; border-color: #333333; color: #ffffff; }
        """)
        self.btn_close.clicked.connect(self._close_mod)
        right_box.addWidget(self.btn_close)

        self.pipe1 = QLabel("|")
        self.pipe1.setStyleSheet("color: #444444; background: transparent; border: none;")
        right_box.addWidget(self.pipe1)

        self.step_counter_label = QLabel("Étape 1 / 5")
        self.step_counter_label.setStyleSheet("color: #8f8f8f; font-family: 'Menlo', monospace; font-size: 11px; background: transparent; border: none;")
        right_box.addWidget(self.step_counter_label)

        self.pipe2 = QLabel("|")
        self.pipe2.setStyleSheet("color: #444444; background: transparent; border: none;")
        right_box.addWidget(self.pipe2)

        self.env_badge_label = QLabel(self.i18n.get("header", "waitingArchive"))
        self.env_badge_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent; border: none;")
        right_box.addWidget(self.env_badge_label)

        self.pipe3 = QLabel("|")
        self.pipe3.setStyleSheet("color: #444444; background: transparent; border: none;")
        right_box.addWidget(self.pipe3)

        # Menu déroulant de changement de langue
        self.header_lang_combo = QComboBox()
        self.header_lang_combo.setFixedHeight(24)
        self.header_lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for code, label, flag in AVAILABLE_LANGUAGES:
            self.header_lang_combo.addItem(f"{flag} {label}", code)
        self.header_lang_combo.setStyleSheet("""
            QComboBox {
                background-color: #222222;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 0 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #0ea5e9;
                background-color: #262626;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #dddddd;
                selection-background-color: #0ea5e9;
                selection-color: #ffffff;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self.header_lang_combo.currentIndexChanged.connect(self._on_header_lang_changed)
        right_box.addWidget(self.header_lang_combo)

        layout.addLayout(right_box)
        return header

    # =========================================================================
    # 2. COLONNE GAUCHE (CONTRÔLES, ACTIONS & DESTINATION DU STAGING) ~19.5%
    # =========================================================================

    def _create_left_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("LeftColFrame")
        col.setStyleSheet("QFrame#LeftColFrame { background-color: #222222; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Haut : Boutons Principaux
        top_box = QVBoxLayout()
        top_box.setSpacing(8)

        # 1. Bouton "Ouvrir un FOMOD"
        self.btn_open_fomod = QPushButton("📦  Ouvrir un FOMOD")
        self.btn_open_fomod.setFixedHeight(46)
        self.btn_open_fomod.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_fomod.setStyleSheet("""
            QPushButton {
                background-color: #fbbf24;
                color: #181818;
                font-weight: bold;
                font-size: 13px;
                border-radius: 5px;
                border: none;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #f59e0b; }
            QPushButton:pressed { background-color: #d97706; }
        """)
        self.btn_open_fomod.clicked.connect(self._open_open_mod_modal)
        top_box.addWidget(self.btn_open_fomod)

        # 2. Bouton "Infos du mod"
        self.btn_mod_info = QPushButton("ℹ️  Infos du mod")
        self.btn_mod_info.setFixedHeight(34)
        self.btn_mod_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mod_info.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #dddddd;
                font-size: 12px;
                font-weight: 500;
                border-radius: 5px;
                border: none;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333333; color: #ffffff; }
        """)
        self.btn_mod_info.clicked.connect(self._show_mod_info_dialog)
        top_box.addWidget(self.btn_mod_info)

        # 3. Bouton "Choisir le dossier Data"
        self.btn_choose_data = QPushButton("📁  Choisir le dossier Data")
        self.btn_choose_data.setFixedHeight(34)
        self.btn_choose_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_data.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #dddddd;
                font-size: 12px;
                font-weight: 500;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333333; color: #ffffff; }
        """)
        self.btn_choose_data.clicked.connect(self._open_data_dir_modal)
        top_box.addWidget(self.btn_choose_data)

        # 4. État du dossier Data
        self.data_status_label = QLabel()
        self.data_status_label.setTextFormat(Qt.TextFormat.RichText)
        self.data_status_label.setText(
            '<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="font-style:italic; color:#aaaaaa;">(non défini)</span><br/><span style="color:#8f8f8f; font-size:10px;">(Cliquez pour simuler Skyrim)</span>'
        )
        self.data_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data_status_label.setStyleSheet("font-size: 11px; line-height: 1.3; background: transparent; border: none;")
        top_box.addWidget(self.data_status_label)

        layout.addLayout(top_box)
        layout.addStretch()

        # Bas : Destination & Génération directe
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(8)

        # Bouton "Choisir le dossier"
        self.btn_choose_dest = QPushButton("📁  Choisir le dossier")
        self.btn_choose_dest.setFixedHeight(34)
        self.btn_choose_dest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_dest.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #dddddd;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333333; color: #ffffff; }
        """)
        self.btn_choose_dest.clicked.connect(self._pick_staging_destination)
        bottom_box.addWidget(self.btn_choose_dest)

        # Carte d'affichage de la destination
        dest_card = QFrame()
        dest_card.setStyleSheet("background-color: #181818; border: none; border-radius: 5px; padding: 6px;")
        dest_layout = QVBoxLayout(dest_card)
        dest_layout.setContentsMargins(4, 2, 4, 2)
        dest_layout.setSpacing(2)

        self.dest_hdr = QLabel(self.i18n.get("common", "destination", default="Destination :"))
        self.dest_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dest_hdr.setStyleSheet("color: #8f8f8f; font-size: 10px; background: transparent; border: none;")
        dest_layout.addWidget(self.dest_hdr)

        self.dest_path_label = QLabel(self.staging_dir_path)
        self.dest_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dest_path_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500; font-family: 'Menlo', monospace; background: transparent; border: none;")
        dest_layout.addWidget(self.dest_path_label)
        bottom_box.addWidget(dest_card)

        # Bouton "GÉNÉRER LE STAGING"
        self.btn_generate_staging = QPushButton("GÉNÉRER LE STAGING")
        self.btn_generate_staging.setFixedHeight(40)
        self.btn_generate_staging.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate_staging.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.5px;
                border-radius: 5px;
                border: none;
                padding: 8px 12px;
            }
            QPushButton:hover { background-color: #0ea5e9; }
            QPushButton:pressed { background-color: #0369a1; }
        """)
        self.btn_generate_staging.clicked.connect(self._on_generate_staging)
        bottom_box.addWidget(self.btn_generate_staging)

        layout.addLayout(bottom_box)
        return col

    # =========================================================================
    # 3. COLONNE CENTRALE (OPTIONS & NAVIGATION) ~32.5%
    # =========================================================================

    def _create_center_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("CenterColFrame")
        col.setStyleSheet("QFrame#CenterColFrame { background-color: #222222; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # En-tête de l'étape courante
        step_header = QFrame()
        step_header.setObjectName("StepHeader")
        step_header.setStyleSheet("QFrame#StepHeader { border-bottom: 1px solid #262626; background-color: transparent; }")
        step_header_layout = QHBoxLayout(step_header)
        step_header_layout.setContentsMargins(14, 12, 14, 12)

        self.step_title_label = QLabel("Silhouette & Version du corps")
        self.step_title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        step_header_layout.addWidget(self.step_title_label)

        step_header_layout.addStretch()

        self.step_index_label = QLabel("1 / 5")
        self.step_index_label.setStyleSheet("color: #aaaaaa; font-family: 'Menlo', monospace; font-size: 11px; border: none; background: transparent;")
        step_header_layout.addWidget(self.step_index_label)
        layout.addWidget(step_header)

        # Zone déroulante des groupes d'options
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_area.viewport().setStyleSheet("background-color: #222222; border: none;")
        self.groups_widget = QWidget()
        self.groups_widget.setStyleSheet("background-color: #222222; border: none;")
        self.groups_layout = QVBoxLayout(self.groups_widget)
        self.groups_layout.setContentsMargins(12, 12, 12, 12)
        self.groups_layout.setSpacing(10)
        self.scroll_area.setWidget(self.groups_widget)
        layout.addWidget(self.scroll_area, 1)

        # Barre de navigation en bas
        nav_bar = QFrame()
        nav_bar.setObjectName("NavBar")
        nav_bar.setStyleSheet("QFrame#NavBar { border-top: 1px solid #262626; background-color: #222222; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; }")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(12, 12, 12, 12)
        nav_layout.setSpacing(10)

        self.btn_prev = QPushButton("RETOUR")
        self.btn_prev.setFixedHeight(38)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #dddddd;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.5px;
                border-radius: 5px;
                border: none;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #333333; }
            QPushButton:disabled {
                background-color: #1e1e1e;
                color: #444444;
                border: none;
            }
        """)
        self.btn_prev.clicked.connect(self._prev_step)
        nav_layout.addWidget(self.btn_prev, 1)

        self.btn_next = QPushButton("CONTINUER")
        self.btn_next.setFixedHeight(38)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.5px;
                border-radius: 5px;
                border: none;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #0ea5e9; }
            QPushButton:pressed { background-color: #0369a1; }
            QPushButton:disabled {
                background-color: rgba(14, 165, 233, 0.3);
                color: rgba(255, 255, 255, 0.35);
                border: none;
            }
        """)
        self.btn_next.clicked.connect(self._next_step)
        nav_layout.addWidget(self.btn_next, 1)

        layout.addWidget(nav_bar)
        return col

    # =========================================================================
    # 4. COLONNE DROITE (DESCRIPTION & IMAGE APERÇU) ~48%
    # =========================================================================

    def _create_right_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("RightColFrame")
        col.setStyleSheet("QFrame#RightColFrame { background-color: #222222; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Titre Instructions & Description
        self.right_sec_title = QLabel("📖  " + self.i18n.get("preview", "instructionsTitle", default="INSTRUCTIONS & DESCRIPTION").upper())
        self.right_sec_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #aaaaaa; letter-spacing: 0.5px; background: transparent; border: none;")
        layout.addWidget(self.right_sec_title)

        # Description textuelle
        self.preview_desc_label = QLabel("Description de l'option...")
        self.preview_desc_label.setWordWrap(True)
        self.preview_desc_label.setStyleSheet("color: #ffffff; font-size: 13px; line-height: 1.5; border: none; background: transparent;")
        layout.addWidget(self.preview_desc_label)

        # Cadre d'image sans fond parasite ni bordure rugueuse
        preview_img_frame = QFrame()
        preview_img_frame.setObjectName("PreviewCard")
        preview_img_frame.setToolTip("Cliquer pour afficher dans sa taille réelle")
        preview_img_frame.setStyleSheet("""
            QFrame#PreviewCard {
                background-color: transparent;
                border: none;
            }
        """)
        img_layout = QVBoxLayout(preview_img_frame)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(0)

        self.preview_image_label = FitImageLabel()
        self.preview_image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_image_label.setToolTip("Cliquer pour afficher dans sa taille réelle")
        self.preview_image_label.mousePressEvent = lambda _e: self._open_image_preview_modal()
        preview_img_frame.mousePressEvent = lambda _e: self._open_image_preview_modal()
        img_layout.addWidget(self.preview_image_label)

        # L'image occupe toute la place restante sous la description
        layout.addWidget(preview_img_frame, 1)
        return col

    # =========================================================================
    # LOGIQUE D'AFFICHAGE ET D'INTERACTION
    # =========================================================================

    # ------------------------------------------------------------------ session d'installation

    @property
    def selected_option_ids(self) -> Set[str]:
        return self.session.selected if self.session else set()

    @property
    def active_flags(self) -> Dict[str, str]:
        return self.session.active_flags if self.session else {}

    def _start_session(self, steps: List[FomodStep], req_files, cond_installs) -> None:
        self.steps = steps
        self.required_files = req_files
        self.conditional_installs = cond_installs
        # Masters des plugins de chaque option (pré-sélection des patchs selon le dossier Data)
        annotate_option_masters(self.archive_index, steps)
        self.session = InstallSession(steps, req_files, cond_installs, self.installed_basenames)
        vis = self.session.visible_step_indices()
        self.current_step_idx = vis[0] if vis else 0

    def _visible_steps(self) -> List[int]:
        return self.session.visible_step_indices() if self.session else []

    def _step_position(self) -> tuple:
        """(position 1-based de l'étape courante parmi les étapes visibles, nombre d'étapes visibles)."""
        vis = self._visible_steps()
        if not vis:
            return 0, 0
        pos = vis.index(self.current_step_idx) + 1 if self.current_step_idx in vis else 1
        return pos, len(vis)

    def _is_last_step(self) -> bool:
        vis = self._visible_steps()
        return not vis or self.current_step_idx >= vis[-1]

    def auto_select_options_for_environment(self, preserve_manual: bool=False):
        """Recalcule les sélections par défaut après un changement du dossier Data."""
        if self.session:
            self.session.set_installed_basenames(self.installed_basenames)

    def load_demo_mod(self, _mod_id: str="cbbe"):
        """Charge le mod de démonstration CBBE intégré."""
        logger.info("Chargement du mod démo : %s", _mod_id)
        try:
            index, cfg_xml, info_xml = get_demo_mod()
            self.archive_index = index
            self.metadata = parse_info_xml(info_xml)
            mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)

            if mod_name:
                self.metadata.name = mod_name
            self._start_session(steps, req_files, cond_installs)

            self._render_current_step()
            self._trigger_background_staging()
            self.central_stack.setCurrentIndex(1)
            self._update_header()

        except Exception as e:
            logger.error("Erreur chargement mod démo: %s", e)

    def _render_current_step(self):
        """Affiche les options de l'étape courante dans la colonne centrale."""
        vis = self._visible_steps()
        if vis and self.current_step_idx not in vis:
            # Étape devenue invisible après un changement de choix : on se replace sur la plus proche
            earlier = [i for i in vis if i < self.current_step_idx]
            self.current_step_idx = earlier[-1] if earlier else vis[0]
        step_num, total_steps = self._step_position()

        self.step_counter_label.setText(
            self.i18n.get("header", "stepCounter", default="Étape {current} / {total}").format(
                current=step_num, total=total_steps
            )
        )
        self.step_index_label.setText(f"{step_num} / {total_steps}")

        # Activation / Désactivation des boutons Précédent & Suivant
        self.btn_prev.setEnabled(step_num > 1)
        self.btn_next.setEnabled(total_steps > 0)
        self.btn_prev.setText(self.i18n.get("steps", "prevStep", default="← RETOUR"))
        self.btn_next.setText(
            self.i18n.get("steps", "finishStep", default="TERMINER")
            if self._is_last_step()
            else self.i18n.get("steps", "nextStep", default="CONTINUER")
        )

        # Nettoyage de l'ancien contenu
        while self.groups_layout.count() > 0:
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.steps or self.current_step_idx >= len(self.steps):
            self.step_title_label.setText(self.i18n.get("steps", "noStepsFound", default="Aucune étape disponible"))
            return

        current_step = self.steps[self.current_step_idx]
        self.step_title_label.setText(current_step.name)

        first_option = None

        for grp in current_step.groups:
            grp_box = QFrame()
            grp_box.setObjectName("GroupCard")
            grp_box.setStyleSheet("QFrame#GroupCard { background-color: #1a1a1a; border: none; border-radius: 6px; }")
            grp_layout = QVBoxLayout(grp_box)
            grp_layout.setContentsMargins(12, 10, 12, 10)
            grp_layout.setSpacing(6)

            # En-tête du groupe
            grp_hdr = QHBoxLayout()
            grp_name = QLabel(grp.name)
            grp_name.setStyleSheet("font-size: 12px; font-weight: bold; color: #dddddd; border: none; background: transparent;")
            grp_hdr.addWidget(grp_name)
            grp_hdr.addStretch()

            is_single = grp.type in (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)
            choice_lbl = self.i18n.get("common", "singleChoice") if is_single else self.i18n.get("common", "multipleChoice")
            grp_type_lbl = QLabel(choice_lbl)
            grp_type_lbl.setStyleSheet("font-size: 10px; color: #aaaaaa; border: none; background: transparent;")
            grp_hdr.addWidget(grp_type_lbl)
            grp_layout.addLayout(grp_hdr)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("background-color: #262626; max-height: 1px; border: none; margin-bottom: 2px;")
            grp_layout.addWidget(div)

            # Options du groupe
            for opt in grp.options:
                if first_option is None:
                    first_option = opt

                is_sel = opt.id in self.selected_option_ids
                matches_dep = option_matches_installed(
                    opt, self.installed_basenames, self.session.flags_before(self.current_step_idx)
                )

                row = OptionRowWidget(
                    option=opt,
                    is_single=is_single,
                    is_selected=is_sel,
                    matches_dep=matches_dep,
                    on_select_callback=lambda o=opt, g=grp: self._on_select_option(o, g),
                    on_hover_callback=self._on_hover_option,
                )
                grp_layout.addWidget(row)

            self.groups_layout.addWidget(grp_box)

        self.groups_layout.addStretch()

        # Mettre à jour l'aperçu
        preview_target = None
        for grp in current_step.groups:
            for opt in grp.options:
                if opt.id in self.selected_option_ids:
                    preview_target = opt
                    break
            if preview_target:
                break
        if not preview_target:
            preview_target = first_option

        if preview_target:
            self._on_hover_option(preview_target)

        self._update_header()

    def _group_of(self, option: FomodOption) -> Optional[FomodGroup]:
        for step in self.steps:
            for grp in step.groups:
                if any(o.id == option.id for o in grp.options):
                    return grp
        return None

    def _preview_pixmap(self, option: FomodOption) -> QPixmap:
        """Image déclarée propre à l'option, sinon image tirée des fichiers qu'elle installe
        (chargée en arrière-plan si besoin), sinon bannière partagée ou visuel généré."""
        primary, fallback = pick_preview_entries(self.archive_index, option, self._group_of(option))
        for entry in (primary, fallback):
            if entry is None:
                continue
            key = entry.path.lower()
            if key in self._preview_cache:
                return QPixmap.fromImage(self._preview_cache[key])
            if entry.data or entry.extracted_disk_path:
                pix = load_pixmap_safely(file_path=entry.extracted_disk_path, data=entry.data)
                if pix and not pix.isNull():
                    return pix
            elif entry is primary:
                self._prefetch_previews()
        return get_preview_pixmap_for_path(None, option.name, option.description, self.archive_index)

    def _prefetch_previews(self):
        """Charge en une passe les aperçus différés de toutes les options de l'étape courante."""
        if not self.steps or self.current_step_idx >= len(self.steps):
            return
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_pending = True
            return
        entries = []
        for grp in self.steps[self.current_step_idx].groups:
            for opt in grp.options:
                primary, _ = pick_preview_entries(self.archive_index, opt, grp)
                if primary and not primary.data and not primary.extracted_disk_path \
                        and primary.path.lower() not in self._preview_cache:
                    entries.append(primary)
        if not entries:
            return
        self._preview_worker = PreviewLoadWorker(self.archive_index, entries)
        self._preview_worker.loaded.connect(self._on_previews_loaded)
        self._preview_worker.start()

    def _on_previews_loaded(self, images: dict):
        self._preview_cache.update(images)
        if self.active_preview_option:
            self._on_hover_option(self.active_preview_option)
        if self._preview_pending:
            self._preview_pending = False
            self._prefetch_previews()

    def _on_hover_option(self, option: FomodOption):
        """Met à jour instantanément la description et l'image d'aperçu."""
        self.active_preview_option = option
        self.preview_desc_label.setText(option.description or "(Aucune description disponible pour cette option)")
        self.preview_image_label.set_source(self._preview_pixmap(option))

    def _on_select_option(self, option: FomodOption, group: FomodGroup):
        """Bascule la sélection d'une option selon les règles du groupe et met à jour le staging."""
        if not self.session or not self.session.toggle(option, group):
            self._on_hover_option(option)
            return
        self._render_current_step()
        self._on_hover_option(option)
        self._trigger_background_staging()

    def _next_step(self):
        later = [i for i in self._visible_steps() if i > self.current_step_idx]
        if later:
            self.current_step_idx = later[0]
            self._render_current_step()
        else:
            self._on_generate_staging()

    def _prev_step(self):
        earlier = [i for i in self._visible_steps() if i < self.current_step_idx]
        if earlier:
            self.current_step_idx = earlier[-1]
            self._render_current_step()

    # =========================================================================
    # STAGING ET SYNCHRONISATION
    # =========================================================================

    def _trigger_background_staging(self):
        """Calcule le staging en arrière-plan et alimente le résultat."""
        if not self.session:
            return

        if self._staging_worker and self._staging_worker.isRunning():
            try:
                self._staging_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._staging_worker.wait(1000)

        self._staging_worker = StagingWorker(
            selected_options=self.session.selected_options(),
            required_files=self.required_files,
            archive_index=self.archive_index,
            conditional_installs=self.conditional_installs,
            active_flags=dict(self.active_flags),
            installed_basenames=set(self.installed_basenames),
            forced_items=self.session.forced_items(),
        )
        self._staging_worker.finished.connect(self._on_staging_finished)
        self._staging_worker.start()

    def _on_staging_finished(self, result: StagingResult):
        self.current_staging_result = result
        self.staging_tree.clear()
        for item in result.items:
            leaf = QTreeWidgetItem([item.destination_path, format_bytes(item.size), item.matched_from_option])
            self.staging_tree.addTopLevelItem(leaf)

    def _on_generate_staging(self):
        """Génère physiquement les fichiers dans le dossier choisi et ouvre la modale de résultat."""
        try:
            if not self.session:
                return
            if not self._ensure_staging_dir():
                return
            res = self.session.build_staging(self.archive_index)
            self.current_staging_result = res

            self.loading_overlay.set_status(self.i18n.get("stagingExport", "writing"))
            self.loading_overlay.resize(self.size())
            self.loading_overlay.show()
            self.loading_overlay.raise_()
            self._export_worker = StagingExportWorker(res, self.staging_dir_path, self.archive_index)
            self._export_worker.progress.connect(self.loading_overlay.set_status)
            self._export_worker.finished.connect(lambda failures, r=res: self._on_staging_written(r, failures))
            self._export_worker.error.connect(self._on_staging_write_error)
            self._export_worker.start()
        except Exception as e:
            logger.exception("Erreur génération staging")
            QMessageBox.critical(self, "Erreur Staging", f"Une erreur est survenue lors de la génération du staging :\n{e}")

    def _on_staging_written(self, res: StagingResult, failures: list):
        self.loading_overlay.hide()
        if failures:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(self.i18n.get("stagingExport", "failedTitle").format(count=len(failures)))
            box.setInformativeText(self.i18n.get("stagingExport", "failedMessage"))
            box.setDetailedText("\n".join(failures))
            box.exec()
        modal = StagingResultModal(res, self.staging_dir_path, self, archive_index=self.archive_index)
        modal.exec()

    def _on_staging_write_error(self, err: str):
        self.loading_overlay.hide()
        QMessageBox.critical(self, "Erreur Staging", f"Une erreur est survenue lors de l'écriture du staging :\n{err}")

    # =========================================================================
    # OUVERTURE DES DIALOGUES MODALES
    # =========================================================================

    def _open_open_mod_modal(self):
        modal = OpenModModal(
            parent=self,
            on_open_archive=self._pick_archive_file,
            on_open_folder=self._pick_folder_mod,
            on_load_sample=self.load_demo_mod,
        )
        modal.exec()

    def _show_mod_info_dialog(self):
        dialog = ModInfoDialog(self.metadata, self)
        dialog.exec()

    def _open_data_dir_modal(self):
        modal = DataDirModal(
            current_data_path=self.data_dir_path,
            installed_plugins=self.installed_basenames,
            on_apply=self._apply_data_dir,
            parent=self,
        )
        modal.exec()

    def _apply_data_dir(self, path: str, plugins: Set[str]):
        self.data_dir_path = path
        self.installed_basenames = plugins
        if path:
            self.data_status_label.setText(
                f'<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="color:#aaaaaa;">{os.path.basename(path)}</span><br/><span style="color:#38bdf8; font-size:10px;">({len(plugins)} plugins détectés)</span>'
            )
        else:
            self.data_status_label.setText(
                '<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="font-style:italic; color:#aaaaaa;">(non défini)</span><br/><span style="color:#8f8f8f; font-size:10px;">(Cliquez pour simuler Skyrim)</span>'
            )
        # Scan intelligent : sélectionne automatiquement les patches correspondant aux mods trouvés
        self.auto_select_options_for_environment(preserve_manual=True)
        self._render_current_step()
        self._trigger_background_staging()
        self._update_header()

    def _pick_staging_destination(self) -> bool:
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de destination du Staging")
        if folder:
            self.staging_dir_path = folder
            self.staging_dir_chosen = True
            self.dest_path_label.setText(folder)
        return bool(folder)

    def _ensure_staging_dir(self) -> bool:
        """Vrai si un dossier de staging existant a été choisi ; sinon avertit et propose d'en choisir un."""
        if self.staging_dir_chosen and os.path.isdir(self.staging_dir_path):
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(self.i18n.get("stagingWarning", "title"))
        # macOS n'affiche pas le titre de fenêtre d'une alerte : titre en texte principal
        box.setText(self.i18n.get("stagingWarning", "title"))
        box.setInformativeText(self.i18n.get("stagingWarning", "message"))
        choose = box.addButton(self.i18n.get("stagingWarning", "choose"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(self.i18n.get("stagingWarning", "cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(choose)
        box.exec()
        return box.clickedButton() is choose and self._pick_staging_destination()

    def _pick_archive_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner l'archive du mod FOMOD",
            "",
            "Archives Mod (*.zip *.7z *.rar *.tar *.gz);;Tous les fichiers (*.*)",
        )
        if path:
            self._load_archive(path)

    def _pick_folder_mod(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier du mod FOMOD décompressé")
        if folder:
            self._load_archive(folder)

    def _load_archive(self, file_path: str):
        if self._extract_worker and self._extract_worker.isRunning():
            try:
                self._extract_worker.finished.disconnect()
                self._extract_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._extract_worker.wait(1000)

        # Affichage du modal de chargement animé (Screenshot 3)
        self.loading_overlay.set_status(f"Extraction et analyse de : {os.path.basename(file_path)}...")
        self.loading_overlay.resize(self.size())
        self.loading_overlay.show()
        self.loading_overlay.raise_()

        self._extract_worker = ArchiveExtractWorker(file_path)
        self._extract_worker.progress.connect(self.loading_overlay.set_status)
        self._extract_worker.finished.connect(self._on_archive_extracted)
        self._extract_worker.error.connect(self._on_archive_error)
        self._extract_worker.start()

    def _on_archive_error(self, err: str):
        self.loading_overlay.hide()
        QMessageBox.warning(self, "Erreur", err)

    def _on_archive_extracted(self, index: ArchiveIndex, arg1: str, arg2: str):
        try:
            self.loading_overlay.hide()

            cfg_xml = ""
            info_xml = ""
            for s in (arg1, arg2):
                if not s:
                    continue
                if "<moduleConfiguration" in s or "<installSteps" in s or "<optionalFileGroups" in s:
                    cfg_xml = s
                elif "<fomod" in s or "<Name>" in s or "<Author>" in s:
                    info_xml = s

            if not cfg_xml and arg1:
                cfg_xml = arg1
            if not info_xml and arg2:
                info_xml = arg2

            if not cfg_xml:
                for k, entry in index.files.items():
                    if k.endswith("moduleconfig.xml"):
                        if entry.data:
                            from ..fomod.extractor import decode_xml_text
                            cfg_xml = decode_xml_text(entry.data)
                        elif entry.extracted_disk_path and os.path.exists(entry.extracted_disk_path):
                            with open(entry.extracted_disk_path, "r", encoding="utf-8", errors="ignore") as fh:
                                cfg_xml = fh.read()
                        break

            if not cfg_xml:
                QMessageBox.warning(
                    self,
                    "ModuleConfig.xml introuvable",
                    "L'archive a été ouverte avec succès mais aucun fichier 'fomod/ModuleConfig.xml' n'a été détecté.\n"
                    "Assurez-vous qu'il s'agit bien d'une archive contenant un installateur FOMOD pour Skyrim."
                )
                return

            self.archive_index = index
            self.metadata = parse_info_xml(info_xml) if info_xml else FomodMetadata(name="Mod FOMOD")
            mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)

            if not steps:
                steps = [
                    FomodStep(
                        id="step_default",
                        name="Installation du Mod",
                        groups=[
                            FomodGroup(
                                id="grp_default",
                                name="Composants du mod",
                                type=GroupType.SelectExactlyOne,
                                options=[
                                    FomodOption(
                                        id="opt_default",
                                        name="Installer les fichiers par défaut",
                                        description="Ce mod est configuré pour une installation automatique sans options personnalisées supplémentaires.",
                                        files=[f for f in req_files if isinstance(f, FomodFileItem)],
                                        folders=[fo for fo in req_files if isinstance(fo, FomodFolderItem)],
                                        is_default=True,
                                    )
                                ]
                            )
                        ]
                    )
                ]

            if mod_name:
                self.metadata.name = mod_name
            self._start_session(steps, req_files, cond_installs)

            self._render_current_step()
            self._trigger_background_staging()
            self.central_stack.setCurrentIndex(1)
            self._update_header()

        except Exception as e:
            self.loading_overlay.hide()
            logger.exception("Erreur lors de l'analyse du mod FOMOD extrait")
            QMessageBox.critical(
                self,
                "Erreur de traitement",
                f"Une erreur est survenue lors de l'analyse du mod :\n{e}"
            )

    def _open_image_preview_modal(self):
        if self.active_preview_option:
            pix = self._preview_pixmap(self.active_preview_option)
            modal = ImagePreviewModal(pix, self.active_preview_option.name, self)
            modal.exec()

    def cleanup_workers(self):
        """Termine proprement les threads à la fermeture sans bloquer."""
        if self._extract_worker and self._extract_worker.isRunning():
            try:
                self._extract_worker.finished.disconnect()
                self._extract_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._extract_worker.wait(1000)
        if self._staging_worker and self._staging_worker.isRunning():
            try:
                self._staging_worker.finished.disconnect()
                self._staging_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._staging_worker.wait(1000)
        if self._export_worker and self._export_worker.isRunning():
            # Écriture en cours : on la laisse finir pour ne pas laisser de fichiers tronqués
            self._export_worker.wait()

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)
