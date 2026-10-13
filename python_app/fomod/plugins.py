"""Plugins Skyrim (.esp/.esm/.esl) : scan du dossier Data et masters des plugins fournis par le mod.

Sert à pré-cocher les options dont les plugins sont utilisables avec le Data de l'utilisateur :
un patch (plugin qui dépend d'un autre mod) est recommandé quand tous ses masters extérieurs au
mod sont présents dans Data.
"""
import logging
import os
import struct
from typing import Dict, Iterable, List, Optional, Set

from .parser import PLUGIN_EXTS, VANILLA_MASTERS, find_file_in_index, find_folder_in_index
from .types import ArchiveIndex, FomodOption, FomodStep, VirtualFileEntry

logger = logging.getLogger(__name__)

# Fichiers qui comptent pour la détection des dépendances (badge « Auto »)
DATA_SCAN_EXTS = PLUGIN_EXTS + (".dll", ".bsa", ".ba2")
# Dossiers de Data sans plugin : ignorés au scan (ils contiennent l'essentiel des fichiers)
DATA_SCAN_SKIP_DIRS = {
    "textures", "meshes", "sound", "music", "video", "scripts", "source", "seq", "strings",
    "lodsettings", "grass", "terrain", "shadersfx", "interface", "facegen", "dialogueviews",
}


def scan_data_dir(folder: str) -> Set[str]:
    """Noms (minuscules) des plugins, DLL et archives BSA présents dans un dossier Data."""
    found: Set[str] = set()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d.lower() not in DATA_SCAN_SKIP_DIRS]
        for f in files:
            lower = f.lower()
            if lower.endswith(DATA_SCAN_EXTS):
                found.add(lower)
    return found


def parse_plugin_masters(data: bytes) -> List[str]:
    """Masters (sous-enregistrements MAST de l'en-tête TES4) d'un plugin Skyrim, en minuscules."""
    if len(data) < 24 or data[:4] != b"TES4":
        return []
    size = struct.unpack_from("<I", data, 4)[0]
    pos, end = 24, min(24 + size, len(data))
    masters: List[str] = []
    big_size: Optional[int] = None
    while pos + 6 <= end:
        sub = data[pos:pos + 4]
        sub_size = struct.unpack_from("<H", data, pos + 4)[0]
        pos += 6
        if big_size is not None:
            sub_size, big_size = big_size, None
        if sub == b"XXXX":
            big_size = struct.unpack_from("<I", data, pos)[0]
        elif sub == b"MAST":
            name = data[pos:pos + sub_size].split(b"\0", 1)[0].decode("cp1252", "replace").strip()
            if name:
                masters.append(name.lower())
        pos += sub_size
    return masters


def _entry_bytes(entry: VirtualFileEntry) -> Optional[bytes]:
    if entry.data:
        return entry.data
    if entry.extracted_disk_path and os.path.isfile(entry.extracted_disk_path):
        try:
            with open(entry.extracted_disk_path, "rb") as fh:
                return fh.read(1 << 20)  # l'en-tête suffit
        except OSError:
            return None
    return None


def option_plugin_entries(index: ArchiveIndex, opt: FomodOption) -> List[VirtualFileEntry]:
    """Plugins que l'option installe (fichiers directs et contenu de ses dossiers)."""
    found: Dict[str, VirtualFileEntry] = {}
    for f in opt.files:
        e = find_file_in_index(index, f.source)
        if e is not None and e.path.lower().endswith(PLUGIN_EXTS):
            found[e.path.lower()] = e
    for fo in opt.folders:
        d = find_folder_in_index(index, fo.source)
        if d is None:
            continue
        prefix = d.lower().rstrip("/") + "/" if d else ""
        for key, e in index.files.items():
            if key.startswith(prefix) and not key.startswith("fomod/") and key.endswith(PLUGIN_EXTS):
                found[key] = e
    return list(found.values())


def annotate_option_masters(
    index: ArchiveIndex, steps: Iterable[FomodStep], read_bytes=_entry_bytes
) -> None:
    """Renseigne `required_masters` de chaque option : masters de ses plugins, hors jeu de base
    et hors plugins fournis par le mod lui-même."""
    provided = {k.rsplit("/", 1)[-1] for k in index.files if k.endswith(PLUGIN_EXTS)}
    cache: Dict[str, List[str]] = {}
    for step in steps:
        for grp in step.groups:
            for opt in grp.options:
                masters: Set[str] = set()
                for e in option_plugin_entries(index, opt):
                    key = e.path.lower()
                    if key not in cache:
                        data = read_bytes(e)
                        cache[key] = parse_plugin_masters(data) if data else []
                    masters.update(cache[key])
                opt.required_masters = {m for m in masters if m not in VANILLA_MASTERS and m not in provided}

