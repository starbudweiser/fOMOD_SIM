"""Choix de l'image d'aperçu d'une option FOMOD.

Ordre de préférence :
1. l'image déclarée par l'option, si elle lui est propre (pas la même image pour tout le groupe) ;
2. sinon, une image tirée des fichiers que l'option installe (capture fournie, puis texture
   principale), pour voir ce qu'on choisit même quand l'auteur n'a rien prévu ;
3. sinon, l'image déclarée partagée (bannière générique du FOMOD).
"""
import re
from typing import List, Optional, Tuple

from .parser import find_file_in_index, find_folder_in_index, find_image_in_index, norm
from .types import ArchiveIndex, FomodGroup, FomodOption, VirtualFileEntry

PICTURE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")
TEXTURE_EXTS = (".dds", ".tga")
# Cartes techniques d'une texture (normales, spéculaire, masques…) : pas représentatives
TECHNICAL_MAP = re.compile(r"_(n|msn|s|m|g|p|em|sk|b|bl|rmaos|e|h|mask|spec|norm|normal)\.(dds|tga)$", re.I)
PREVIEW_HINT = re.compile(r"(preview|screenshot|screen|apercu|thumb|sample|cover)", re.I)


def declared_image_is_shared(group: Optional[FomodGroup], opt: FomodOption) -> bool:
    """Vrai si plusieurs options du groupe déclarent la même image (bannière générique)."""
    if not group or not opt.image_path:
        return False
    key = norm(opt.image_path).lower()
    return sum(1 for o in group.options if o.image_path and norm(o.image_path).lower() == key) > 1


def option_content_images(index: ArchiveIndex, opt: FomodOption) -> List[VirtualFileEntry]:
    """Images contenues dans les fichiers et dossiers que l'option installe, de la plus parlante à la moins."""
    found: dict = {}
    for f in opt.files:
        e = find_file_in_index(index, f.source)
        if e is not None and e.path.lower().endswith(PICTURE_EXTS + TEXTURE_EXTS):
            found[e.path.lower()] = e
    for fo in opt.folders:
        d = find_folder_in_index(index, fo.source)
        if d is None:
            continue
        prefix = d.lower().rstrip("/") + "/" if d else ""
        for key, e in index.files.items():
            if key.startswith(prefix) and not key.startswith("fomod/") and key.endswith(PICTURE_EXTS + TEXTURE_EXTS):
                found[key] = e

    def rank(e: VirtualFileEntry) -> Tuple[int, int, int, int]:
        name = e.path.lower()
        is_texture = name.endswith(TEXTURE_EXTS)
        return (
            0 if PREVIEW_HINT.search(name) else 1,
            1 if is_texture else 0,
            1 if TECHNICAL_MAP.search(name) else 0,
            -(e.size or 0),
        )

    return sorted(found.values(), key=rank)


def pick_preview_entries(
    index: Optional[ArchiveIndex], opt: FomodOption, group: Optional[FomodGroup] = None
) -> Tuple[Optional[VirtualFileEntry], Optional[VirtualFileEntry]]:
    """(image à afficher, image de repli). L'image de repli est la bannière partagée éventuelle."""
    if index is None:
        return None, None
    declared = find_image_in_index(index, opt.image_path) if opt.image_path else None
    if declared is not None and not declared_image_is_shared(group, opt):
        return declared, None
    content = option_content_images(index, opt)
    if content:
        return content[0], declared
    return declared, None
