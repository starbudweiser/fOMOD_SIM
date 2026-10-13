import os
import sys
import io
import logging
from typing import Optional
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPolygonF,
    QFont,
    QLinearGradient,
)
from ..fomod.types import ArchiveIndex
from ..fomod.parser import find_image_in_index

logger = logging.getLogger(__name__)

# Palette et métadonnées d'aperçu des mods de démonstration
SAMPLE_PREVIEW_CONFIGS = {
    "fomod/images/curvy.png": {
        "title": "CBBE Curvy Body",
        "subtitle": "Default voluptuous silhouette with smooth curves",
        "bg": "#1e293b",
        "accent": "#38bdf8",
    },
    "fomod/images/slim.png": {
        "title": "CBBE Slim Body",
        "subtitle": "Athletic and slender proportions for female characters",
        "bg": "#1e293b",
        "accent": "#38bdf8",
    },
    "fomod/images/vanilla.png": {
        "title": "CBBE Vanilla Shape",
        "subtitle": "Faithful to original Skyrim proportions",
        "bg": "#1e293b",
        "accent": "#38bdf8",
    },
    "fomod/images/tex4k.png": {
        "title": "4K Ultra Textures",
        "subtitle": "Ultra HD skin pores, specular maps and normal detail",
        "bg": "#312e81",
        "accent": "#a855f7",
    },
    "fomod/images/tex2k.png": {
        "title": "2K High Textures",
        "subtitle": "Balanced fidelity with excellent VRAM performance",
        "bg": "#312e81",
        "accent": "#a855f7",
    },
    "fomod/images/physics.png": {
        "title": "HDT-SMP / CBPC Physics",
        "subtitle": "Real-time soft body physics simulation enabled",
        "bg": "#14532d",
        "accent": "#4ade80",
    },
    "fomod/images/static.png": {
        "title": "Static Body (No Physics)",
        "subtitle": "Maximum FPS, zero performance impact",
        "bg": "#14532d",
        "accent": "#4ade80",
    },
    "fomod/images/underwear.png": {
        "title": "Underwear Version",
        "subtitle": "Includes discrete lore-friendly underwear meshes",
        "bg": "#7c2d12",
        "accent": "#fb923c",
    },
    "fomod/images/nevernude.png": {
        "title": "NeverNude Safe Version",
        "subtitle": "Includes permanent modesty cloth for safe streaming",
        "bg": "#7c2d12",
        "accent": "#fb923c",
    },
    "fomod/images/skyui_patch.png": {
        "title": "SkyUI SE Integration",
        "subtitle": "Custom icons and inventory management tags",
        "bg": "#0f172a",
        "accent": "#fbbf24",
    },
    "fomod/images/racemenu_patch.png": {
        "title": "RaceMenu Overlays",
        "subtitle": "High poly body morph sliders and tattoo overlays",
        "bg": "#0f172a",
        "accent": "#fbbf24",
    },
    # SMIM
    "fomod/images/smim_core.png": {
        "title": "SMIM - Static Meshes Core",
        "subtitle": "High-poly 3D chains, ropes, barrels and furniture",
        "bg": "#1e293b",
        "accent": "#38bdf8",
    },
    "fomod/images/smim_chains.png": {
        "title": "SMIM 3D Chains & Ropes",
        "subtitle": "Realistic geometric links replacing 2D cross-planes",
        "bg": "#312e81",
        "accent": "#a855f7",
    },
    "fomod/images/smim_barrels.png": {
        "title": "SMIM Barrels & Furniture",
        "subtitle": "Fully rounded 3D wooden staves and metal rings",
        "bg": "#7c2d12",
        "accent": "#fb923c",
    },
}


def load_pixmap_safely(file_path: Optional[str] = None, data: Optional[bytes] = None) -> Optional[QPixmap]:
    """Charge de manière robuste une image vers QPixmap, avec fallback Pillow pour DDS/TGA."""
    if not file_path and not data:
        return None

    # 1. Essai direct Qt
    try:
        pix = QPixmap()
        if file_path and os.path.exists(file_path):
            if pix.load(file_path) and not pix.isNull():
                return pix
        elif data:
            if pix.loadFromData(data) and not pix.isNull():
                return pix
    except Exception:
        pass

    # 2. Fallback Pillow (DDS, TGA, WebP, etc.)
    try:
        import importlib
        pil_image = importlib.import_module("PIL.Image")
        pil_imageqt = importlib.import_module("PIL.ImageQt")
        im = None
        if file_path and os.path.exists(file_path):
            im = pil_image.open(file_path)
        elif data:
            im = pil_image.open(io.BytesIO(data))
        if im is not None:
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            qim = pil_imageqt.ImageQt(im)
            pix = QPixmap.fromImage(qim)
            if not pix.isNull():
                return pix
    except (ImportError, Exception) as e:
        logger.debug("Fallback Pillow échec : %s", e)

    return None


def generate_preview_pixmap(
    title: str,
    subtitle: str,
    bg_color: str = "#1e293b",
    accent_color: str = "#38bdf8",
    width: int = 640,
    height: int = 400,
) -> QPixmap:
    """Génère un canevas pixmap vectoriel HD pour les options sans image disque."""
    pix = QPixmap(width, height)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Dégradé d'arrière-plan avec bg_color
    gradient = QLinearGradient(0.0, 0.0, float(width), float(height))
    gradient.setColorAt(0.0, QColor(bg_color))
    gradient.setColorAt(1.0, QColor("#111111"))
    painter.fillRect(0, 0, width, height, gradient)

    # 1. Emblème central géométrique
    cx = width // 2
    cy = 130
    accent = QColor(accent_color)

    circle_pen = QPen(accent, 2.5)
    painter.setPen(circle_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(cx - 55, cy - 55, 110, 110)

    diamond = QPolygonF([
        QPointF(cx - 32, cy),
        QPointF(cx, cy - 32),
        QPointF(cx + 32, cy),
        QPointF(cx, cy + 32),
    ])
    accent_brush = QColor(accent.red(), accent.green(), accent.blue(), 200)
    painter.setBrush(QBrush(accent_brush))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(diamond)

    # 2. Titre de l'option
    painter.setPen(QColor("#ffffff"))
    title_font = QFont(".AppleSystemUIFont" if sys.platform == "darwin" else "", 16, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(QRectF(20, 210, width - 40, 32), Qt.AlignmentFlag.AlignCenter, title)

    # 3. Sous-titre
    painter.setPen(QColor("#a1a1aa"))
    sub_font = QFont(".AppleSystemUIFont" if sys.platform == "darwin" else "", 12)
    painter.setFont(sub_font)
    painter.drawText(QRectF(20, 246, width - 40, 28), Qt.AlignmentFlag.AlignCenter, subtitle)

    painter.end()
    return pix


def get_preview_pixmap_for_path(
    image_path: Optional[str],
    opt_name: str,
    opt_desc: str,
    archive_index: Optional[ArchiveIndex] = None,
) -> QPixmap:
    """Retourne l'image de prévisualisation adéquate pour un chemin donné,
    en chargeant en priorité l'image réelle depuis l'archive indexée."""
    if image_path:
        norm_key = image_path.replace("\\", "/").strip().lower()

        # 1. Vérification dans l'archive indexée
        if archive_index:
            entry = find_image_in_index(archive_index, image_path)
            if entry:
                pix = load_pixmap_safely(
                    file_path=entry.extracted_disk_path,
                    data=entry.data,
                )
                if pix and not pix.isNull():
                    return pix

        # 2. Vérification dans les configurations démo
        for k, cfg in SAMPLE_PREVIEW_CONFIGS.items():
            if norm_key.endswith(k.lower()) or k.lower() in norm_key:
                return generate_preview_pixmap(
                    title=cfg["title"],
                    subtitle=cfg["subtitle"],
                    bg_color=cfg["bg"],
                    accent_color=cfg["accent"],
                )

    # 3. Aperçu dynamique par défaut si aucune image spécifique n'est fournie ou lisible
    sub = (opt_desc.split(".")[0] + ".") if opt_desc else "Option de configuration du mod"
    if len(sub) > 65:
        sub = sub[:62] + "..."
    return generate_preview_pixmap(title=opt_name, subtitle=sub, bg_color="#1e293b", accent_color="#38bdf8")
