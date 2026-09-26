#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
            SIMULATEUR FOMOD v1.0 - SCRIPT PYTHON UNIQUE & AUTONOME
================================================================================
Application de bureau complète avec interface graphique PyQt6 non-bloquante,
moteur de parsing XML FOMOD, simulateur de staging Skyrim Data et extracteur
universel d'archives (.zip, .7z, .rar, .tar, dossiers).

Conception soignée, fidèle au design de l'application web d'origine :
- En-tête supérieur avec indicateurs d'étape et de compatibilité.
- Disposition 3 colonnes : Contrôles & Staging (26%), Sélection des Options (29%),
  Instructions & Aperçu d'image vectoriel dynamique (45%).
- Modales interactives : 'Ouvrir un FOMOD', 'Infos du mod', 'Dossier Data',
  'Staging généré', 'Plein écran'.
- Journalisation rigoureuse via le module natif `logging`.

INSTRUCTIONS DE COMPILATION AUTONOME (PYINSTALLER) :
---------------------------------------------------
1. Prérequis :
   pip install PyQt6 py7zr pyinstaller

2. Compilation binaire autonome (Linux / Windows) :
   pyinstaller --windowed --onefile --name="FOMOD_Simulator" fomod_simulator_standalone.py

3. Compilation application native macOS (.app bundle) :
   pyinstaller --windowed --onefile \
               --name="FOMOD Simulator" \
               --osx-bundle-identifier="com.skyrimtools.fomodsimulator" \
               fomod_simulator_standalone.py

L'exécutable compilé sera directement généré dans le dossier 'dist/'.
================================================================================
"""

import sys
import os
import io
import re
import shutil
import subprocess
import zipfile
import tarfile
import tempfile
import logging
import importlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any, Tuple
from enum import Enum
import xml.etree.ElementTree as ET

# Configuration initiale de logging
logger = logging.getLogger("fomod_simulator")

# ---------------------------------------------------------------------------
# Imports PyQt6 avec validation
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QStackedWidget, QLabel, QPushButton, QScrollArea, QFrame, QTreeWidget,
        QTreeWidgetItem, QFileDialog, QMessageBox, QDialog, QComboBox,
        QTextEdit, QHeaderView, QTabWidget
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QSettings
    from PyQt6.QtGui import (
        QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont, QLinearGradient
    )
except ImportError as err:
    sys.stderr.write(f"ERREUR : Bibliothèque PyQt6 manquante ({err}).\nInstallez-la via : pip install PyQt6\n")
    sys.exit(1)

# ==============================================================================
# 1. STRUCTURES DE DONNÉES DU DOMAINE FOMOD
# ==============================================================================


class GroupType(Enum):
    SelectAny = "SelectAny"
    SelectAll = "SelectAll"
    SelectExactlyOne = "SelectExactlyOne"
    SelectAtMostOne = "SelectAtMostOne"
    SelectAtLeastOne = "SelectAtLeastOne"


@dataclass
class FomodMetadata:
    name: str = "Mod Skyrim"
    author: str = ""
    version: str = "1.0.0"
    website: str = ""
    description: str = ""


@dataclass
class FomodFileItem:
    source: str
    destination: str
    priority: int = 0


@dataclass
class FomodFolderItem:
    source: str
    destination: str
    priority: int = 0


@dataclass
class FileDependency:
    file: str
    state: str  # 'Active' | 'Inactive' | 'Missing'


@dataclass
class FlagDependency:
    flag: str
    value: str


@dataclass
class FomodDependencies:
    operator: str = "And"  # 'And' | 'Or' | 'Not'
    file_dependencies: List[FileDependency] = field(default_factory=list)
    flag_dependencies: List[FlagDependency] = field(default_factory=list)
    nested_dependencies: List['FomodDependencies'] = field(default_factory=list)


@dataclass
class TypeDescriptorPattern:
    dependencies: Optional[FomodDependencies]
    type_name: str  # "Required", "Optional", "Recommended", "NotUsable", "CouldBeUsable"


@dataclass
class TypeDescriptor:
    default_type: str = "Optional"
    patterns: List[TypeDescriptorPattern] = field(default_factory=list)


@dataclass
class ConditionalInstallPattern:
    dependencies: Optional[FomodDependencies]
    files: List[FomodFileItem] = field(default_factory=list)
    folders: List[FomodFolderItem] = field(default_factory=list)


@dataclass
class FomodOption:
    id: str
    name: str
    description: str
    image_path: Optional[str] = None
    files: List[FomodFileItem] = field(default_factory=list)
    folders: List[FomodFolderItem] = field(default_factory=list)
    flags: Dict[str, str] = field(default_factory=dict)
    dependencies: Optional[FomodDependencies] = None
    is_default: bool = False
    type_descriptor: Optional[TypeDescriptor] = None


@dataclass
class FomodGroup:
    id: str
    name: str
    type: GroupType
    options: List[FomodOption] = field(default_factory=list)


@dataclass
class FomodStep:
    id: str
    name: str
    groups: List[FomodGroup] = field(default_factory=list)
    visible: bool = True


@dataclass
class VirtualFileEntry:
    path: str
    is_dir: bool = False
    size: int = 0
    data: Optional[bytes] = None
    extracted_disk_path: Optional[str] = None


@dataclass
class ArchiveIndex:
    files: Dict[str, VirtualFileEntry] = field(default_factory=dict)
    dirs: Dict[str, str] = field(default_factory=dict)
    temp_dir: Optional[str] = None
    archive_path: Optional[str] = None


@dataclass
class StagingItem:
    destination_path: str
    source_entry: VirtualFileEntry
    size: int
    priority: int
    matched_from_option: str


@dataclass
class StagingResult:
    items: List[StagingItem]
    total_size: int
    copied_count: int
    skipped_count: int
    log: List[str]


def format_bytes(sz: int) -> str:
    if sz <= 0:
        return "0 o"
    if sz < 1024:
        return f"{sz} o"
    if sz < 1024 * 1024:
        return f"{sz / 1024:.1f} Ko"
    return f"{sz / (1024 * 1024):.2f} Mo"

# ==============================================================================
# 2. PARSEUR XML FOMOD ROBUSTE & ÉVALUATEUR DE DÉPENDANCES
# ==============================================================================


def norm(path: Optional[str]) -> str:
    if not path:
        return ""
    p = path.replace("\\", "/").strip()
    p = re.sub(r"/+", "/", p)
    p = re.sub(r"^\./", "", p)
    return p.strip("/")


def strip_num_prefix(name: str) -> str:
    base = name.split("/")[-1] if "/" in name else name
    return re.sub(r"^\d+\s*[_-]*\s*", "", base).lower()


def extract_element_image(el: Optional[ET.Element]) -> Optional[str]:
    """Extrait le chemin d'image depuis un élément XML ou ses descendants de manière universelle."""
    if el is None:
        return None

    # 1. Attributs directs sur l'élément (ex: <plugin image="..." Path="..." />)
    for attr in ("image", "imagepath", "imagePath", "Path", "path", "file", "File", "src", "Src", "preview", "previewImage"):
        val = el.attrib.get(attr)
        if val and val.strip():
            return norm(val)

    # 2. Balises enfants directes ou imbriquées (image, Image, previewImage, headerImage, etc.)
    target_tags = {"image", "headerimage", "previewimage", "img", "pic"}
    for ch in el.iter():
        if ch is el:
            continue
        tag = ch.tag.split("}")[-1].lower()
        if tag in target_tags:
            for attr in ("path", "Path", "file", "File", "src", "Src", "url", "Url", "name", "Name"):
                val = ch.attrib.get(attr)
                if val and val.strip():
                    return norm(val)
            if ch.text and ch.text.strip():
                txt = ch.text.strip()
                if re.search(r"\.(jpe?g|png|bmp|webp|gif|dds|tga)$", txt, re.I) or "/" in txt or "\\" in txt:
                    return norm(txt)

    return None


def find_file_in_index(index: ArchiveIndex, src: str) -> Optional[VirtualFileEntry]:
    """Recherche de fichier robuste et insensible à la casse avec variations de préfixes FOMOD."""
    raw_key = norm(src)
    if not raw_key:
        return None
    key = raw_key.lower()

    # 1. Correspondance directe exacte
    if key in index.files:
        f = index.files[key]
        if "__macosx" not in f.path.lower():
            return f

    # 2. Variations fréquentes de préfixes (fomod/, images/, fomod/images/)
    variations = [
        key,
        re.sub(r"^fomod\/", "", key),
        re.sub(r"^images\/", "", key),
        re.sub(r"^fomod\/images\/", "images/", key),
        f"fomod/{key}",
        f"images/{key}",
        f"fomod/images/{key}",
    ]
    for v in variations:
        if v in index.files:
            f = index.files[v]
            if "__macosx" not in f.path.lower():
                return f

    # 3. Correspondance par suffixe dans les deux sens
    suffix_cands: List[VirtualFileEntry] = []
    suffix_slash_key = "/" + key
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        if (
            rel_key == key
            or rel_key.endswith(key)
            or rel_key.endswith(suffix_slash_key)
            or key.endswith("/" + rel_key)
            or key.endswith(rel_key)
        ):
            suffix_cands.append(entry)

    if suffix_cands:
        suffix_cands.sort(key=lambda x: len(x.path))
        return suffix_cands[0]

    # 4. Correspondance par nom de fichier final (basename)
    base = key.split("/")[-1]
    if base:
        base_slash = "/" + base
        base_cands: List[VirtualFileEntry] = []
        for rel_key, entry in index.files.items():
            if "__macosx" in rel_key:
                continue
            if rel_key == base or rel_key.endswith(base_slash):
                base_cands.append(entry)
        if base_cands:
            base_cands.sort(key=lambda x: len(x.path))
            return base_cands[0]

    # 5. Correspondance souple en ignorant les préfixes numériques
    key_stripped = strip_num_prefix(key)
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        rel_stripped = strip_num_prefix(rel_key)
        if rel_stripped == key_stripped or rel_stripped.endswith("/" + key_stripped):
            return entry

    return None
    key = raw_key.lower()

    if key in index.files:
        f = index.files[key]
        if "__macosx" not in f.path.lower():
            return f

    suffix_slash_key = "/" + key
    suffix_cands: List[VirtualFileEntry] = []
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        if rel_key.endswith(key) or rel_key.endswith(suffix_slash_key):
            suffix_cands.append(entry)

    if suffix_cands:
        suffix_cands.sort(key=lambda x: len(x.path))
        return suffix_cands[0]

    base = key.split("/")[-1]
    if base:
        base_slash = "/" + base
        base_cands: List[VirtualFileEntry] = []
        for rel_key, entry in index.files.items():
            if "__macosx" in rel_key:
                continue
            if rel_key == base or rel_key.endswith(base_slash):
                base_cands.append(entry)
        if base_cands:
            base_cands.sort(key=lambda x: len(x.path))
            return base_cands[0]

    key_stripped = strip_num_prefix(key)
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        rel_stripped = strip_num_prefix(rel_key)
        if rel_stripped == key_stripped or rel_stripped.endswith("/" + key_stripped):
            return entry

    return None


def reanchor_index(files_map: Dict[str, VirtualFileEntry], dirs_map: Dict[str, str]) -> Tuple[Dict[str, VirtualFileEntry], Dict[str, str]]:
    """Détecte si tous les fichiers du mod sont contenus dans un sous-dossier et réaligne la racine."""
    root_prefix = ""

    # 1. Chercher le chemin vers ModuleConfig.xml pour déterminer la racine du FOMOD
    for lower_path in files_map.keys():
        fomod_idx = lower_path.find("fomod/moduleconfig.xml")
        if fomod_idx > 0:
            root_prefix = lower_path[:fomod_idx]
            break

    # 2. Si non trouvé par fomod, vérifier si tous les fichiers partagent un préfixe commun unique
    if not root_prefix and files_map:
        first_key = next(iter(files_map.keys()))
        if "/" in first_key:
            cand = first_key.split("/")[0] + "/"
            if all(k.startswith(cand) for k in files_map.keys()):
                root_prefix = cand

    if not root_prefix:
        return files_map, dirs_map

    logger.info(f"Racine englobante détectée et réalignée : '{root_prefix}'")
    prefix_segments = len([p for p in root_prefix.split("/") if p])
    new_files: Dict[str, VirtualFileEntry] = {}
    new_dirs: Dict[str, str] = {}

    for lower_path, entry in files_map.items():
        new_norm_path = entry.path
        new_lower = lower_path

        if lower_path.startswith(root_prefix):
            new_lower = lower_path[len(root_prefix):]
            parts = entry.path.split("/")
            new_norm_path = "/".join(parts[prefix_segments:])

        new_files[new_lower] = VirtualFileEntry(
            path=new_norm_path,
            is_dir=getattr(entry, "is_dir", False),
            size=entry.size,
            data=entry.data,
            extracted_disk_path=entry.extracted_disk_path,
        )

        parts = new_norm_path.split("/")
        cur = ""
        for i in range(len(parts) - 1):
            cur = f"{cur}/{parts[i]}" if cur else parts[i]
            new_dirs[cur.lower()] = cur

    return new_files, new_dirs


def find_folder_in_index(index: ArchiveIndex, src: str) -> Optional[str]:
    raw_key = norm(src).strip("/")
    if not raw_key:
        return None
    key = raw_key.lower()

    # 1. Correspondance exacte
    if key in index.dirs:
        orig = index.dirs[key]
        if "__macosx" not in orig.lower():
            return orig

    # 2. Correspondance par suffixe
    cands: List[str] = []
    slash_key = "/" + key
    for rel_key, orig in index.dirs.items():
        if "__macosx" in rel_key:
            continue
        if rel_key == key or rel_key.endswith(slash_key) or rel_key.endswith(key):
            cands.append(orig)
    if cands:
        cands.sort(key=len)
        return cands[0]

    # 3. Correspondance sans préfixes numériques
    key_bn = strip_num_prefix(key)
    prefix_cands: List[str] = []
    for rel_key, orig in index.dirs.items():
        if "__macosx" in rel_key:
            continue
        stripped_rel = strip_num_prefix(rel_key)
        if stripped_rel == key_bn or stripped_rel.endswith("/" + key_bn):
            prefix_cands.append(orig)
    if prefix_cands:
        prefix_cands.sort(key=len)
        return prefix_cands[0]

    # 4. Dossier contenu dans les chemins de fichiers indexés
    slash_key_slash = "/" + key + "/"
    for rel_key in index.files.keys():
        if "__macosx" in rel_key:
            continue
        if rel_key.startswith(key + "/"):
            return rel_key[: len(key)]
        idx = ("/" + rel_key).find(slash_key_slash)
        if idx != -1:
            return rel_key[idx: idx + len(key)]

    # 5. Suffixe sur les répertoires parents des fichiers indexés
    for rel_key in index.files.keys():
        if "__macosx" in rel_key:
            continue
        parent_dir = rel_key.rsplit("/", 1)[0] if "/" in rel_key else ""
        if parent_dir and (parent_dir == key or parent_dir.endswith("/" + key)):
            idx = ("/" + parent_dir).rfind("/" + key)
            return parent_dir[idx: idx + len(key)]

    return None


def parse_dependencies_node(dep_el: ET.Element) -> FomodDependencies:
    op = dep_el.attrib.get("operator", "And").capitalize()
    if op not in ("And", "Or", "Not"):
        op = "And"

    file_deps: List[FileDependency] = []
    for f in dep_el.findall("./fileDependency"):
        fn = f.attrib.get("file", "")
        st = f.attrib.get("state", "Active")
        if fn:
            file_deps.append(FileDependency(file=fn, state=st))

    flag_deps: List[FlagDependency] = []
    for fl in dep_el.findall("./flagDependency"):
        flg = fl.attrib.get("flag", "")
        val = fl.attrib.get("value", "")
        if flg:
            flag_deps.append(FlagDependency(flag=flg, value=val))

    nested: List[FomodDependencies] = []
    for sub in dep_el.findall("./dependencies"):
        nested.append(parse_dependencies_node(sub))

    return FomodDependencies(
        operator=op,
        file_dependencies=file_deps,
        flag_dependencies=flag_deps,
        nested_dependencies=nested,
    )


def check_flag_value(curr_val: Optional[str], expected_val: str) -> bool:
    """Compare une valeur de flag actuelle avec la valeur attendue."""
    c = (curr_val or "").strip().lower()
    e = (expected_val or "").strip().lower()
    if not c:
        return e in ("inactive", "false", "0", "missing", "none")
    return c == e


def evaluate_dependencies(
    deps: Optional[FomodDependencies],
    active_flags: Dict[str, str],
    installed_files: Set[str],
) -> bool:
    if not deps:
        return True

    results: List[bool] = []

    for fd in deps.file_dependencies:
        base = fd.file.replace("\\", "/").split("/")[-1].strip().lower()
        is_inst = base in installed_files
        st = fd.state.lower()
        if st == "active":
            results.append(is_inst)
        elif st in ("inactive", "missing"):
            results.append(not is_inst)
        else:
            results.append(is_inst)

    for fl in deps.flag_dependencies:
        cur_val = active_flags.get(fl.flag)
        results.append(check_flag_value(cur_val, fl.value))

    for nd in deps.nested_dependencies:
        results.append(evaluate_dependencies(nd, active_flags, installed_files))

    if not results:
        return True

    op = deps.operator.lower()
    if op == "and":
        return all(results)
    elif op == "or":
        return any(results)
    elif op == "not":
        return not any(results)
    return True


def compute_option_type(
    opt: FomodOption,
    active_flags: Dict[str, str],
    installed_files: Set[str],
) -> str:
    """Détermine le type calculé d'une option FOMOD selon ses descripteurs et dépendances."""
    if not opt.type_descriptor:
        return "Recommended" if opt.is_default else "Optional"

    td = opt.type_descriptor
    for pat in td.patterns:
        if evaluate_dependencies(pat.dependencies, active_flags, installed_files):
            return pat.type_name

    return td.default_type


def is_option_recommended(
    opt: FomodOption,
    active_flags: Dict[str, str],
    installed_files: Set[str],
) -> bool:
    """Détermine si une option doit être pré-cochée ou marquée recommandée."""
    computed = compute_option_type(opt, active_flags, installed_files).lower()
    if computed in ("recommended", "required"):
        return True

    if opt.dependencies and opt.dependencies.file_dependencies:
        if evaluate_dependencies(opt.dependencies, active_flags, installed_files):
            return True

    if installed_files:
        for f in opt.files:
            b = f.source.replace("\\", "/").split("/")[-1].strip().lower()
            if b.endswith((".esp", ".esm", ".esl")):
                for inst in installed_files:
                    if len(inst) > 4 and (inst in b or b in inst):
                        return True

    return opt.is_default


def parse_info_xml(xml_text: str) -> FomodMetadata:
    if not xml_text:
        return FomodMetadata(name="Mod Skyrim")

    try:
        cleaned = xml_text.strip().lstrip("\ufeff")
        root = ET.fromstring(cleaned)
        for el in root.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]

        def get_text(tags: List[str]) -> str:
            for tag in tags:
                for el in root.iter():
                    if el.tag.lower() == tag.lower() and el.text:
                        return el.text.strip()
            return ""

        return FomodMetadata(
            name=get_text(["Name", "ModName", "Title"]) or "Mod Skyrim",
            author=get_text(["Author", "Authors"]) or "Inconnu",
            version=get_text(["Version"]) or "1.0.0",
            website=get_text(["Website", "URL", "Homepage", "Link"]) or "",
            description=get_text(["Description", "Summary", "Details"]) or "(Aucune description disponible)",
        )
    except Exception:
        logger.exception("Erreur lors de la lecture d'info.xml")
        return FomodMetadata(name="Mod Skyrim")


def parse_module_config_xml(xml_text: str) -> Tuple[str, List[FomodStep], List[Any], List[ConditionalInstallPattern]]:
    if not xml_text:
        return "Mod sans configuration FOMOD", [], [], []

    try:
        cleaned = xml_text.strip().lstrip("\ufeff")
        root = ET.fromstring(cleaned)
        # SUPPRESSION UNIVERSELLE DES NAMESPACES XML
        for el in root.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
    except Exception:
        logger.exception("Erreur lors du parsing XML")
        return "Erreur XML", [], [], []

    module_name = ""
    for child in root.iter():
        tag = child.tag.lower()
        if tag == "modulename" and child.text and child.text.strip():
            module_name = child.text.strip()
            break
    if not module_name:
        module_name = root.attrib.get("name", "Mod Skyrim")

    required_files: List[Any] = []
    for req in root.findall(".//requiredInstallFiles/*"):
        tag = req.tag.lower()
        s = norm(req.attrib.get("source"))
        d = norm(req.attrib.get("destination"))
        prio = int(req.attrib.get("priority", "0") or "0")
        if not s:
            continue
        if tag == "file":
            required_files.append(FomodFileItem(source=s, destination=d, priority=prio))
        elif tag == "folder":
            required_files.append(FomodFolderItem(source=s, destination=d, priority=prio))

    steps: List[FomodStep] = []
    all_steps = root.findall(".//installStep") or root.findall(".//step") or root.findall(".//installSteps/installStep")

    for step_idx, step_el in enumerate(all_steps):
        step_name = step_el.attrib.get("name", "").strip() or f"Étape {step_idx + 1}"
        groups: List[FomodGroup] = []

        raw_groups = step_el.findall(".//group") or step_el.findall(".//optionalFileGroup") or step_el.findall(".//optionalFileGroups/group")
        seen_grps = set()
        group_elements = []
        for g in raw_groups:
            if g not in seen_grps:
                seen_grps.add(g)
                group_elements.append(g)

        for grp_idx, grp_el in enumerate(group_elements):
            group_name = grp_el.attrib.get("name", "").strip() or f"Groupe {grp_idx + 1}"
            raw_type = grp_el.attrib.get("type", "SelectAny")

            try:
                grp_type = GroupType(raw_type)
            except ValueError:
                grp_type = GroupType.SelectAny

            options: List[FomodOption] = []
            raw_plugins = grp_el.findall(".//plugin") or grp_el.findall(".//option") or grp_el.findall(".//plugins/plugin")
            seen_pls = set()
            plugin_elements = []
            for p in raw_plugins:
                if p not in seen_pls:
                    seen_pls.add(p)
                    plugin_elements.append(p)

            for pl_idx, pl_el in enumerate(plugin_elements):
                opt_name = pl_el.attrib.get("name", "").strip()
                if not opt_name:
                    for child in pl_el:
                        if child.tag.lower() in ("name", "text") and child.text:
                            opt_name = child.text.strip()
                            break

                desc = ""
                for child in pl_el:
                    if child.tag.lower() == "description" and child.text:
                        desc = child.text.strip()
                        break

                image_path = extract_element_image(pl_el)

                files: List[FomodFileItem] = []
                for fn in pl_el.findall(".//file"):
                    s = norm(fn.attrib.get("source"))
                    d = norm(fn.attrib.get("destination"))
                    prio = int(fn.attrib.get("priority", "0") or "0")
                    if s:
                        files.append(FomodFileItem(source=s, destination=d, priority=prio))

                folders: List[FomodFolderItem] = []
                for fld in pl_el.findall(".//folder"):
                    s = norm(fld.attrib.get("source"))
                    d = norm(fld.attrib.get("destination"))
                    prio = int(fld.attrib.get("priority", "0") or "0")
                    if s:
                        folders.append(FomodFolderItem(source=s, destination=d, priority=prio))

                if not opt_name:
                    if files:
                        opt_name = files[0].source.split("/")[-1]
                    elif folders:
                        opt_name = folders[0].source.split("/")[-1]
                    else:
                        opt_name = f"Option {pl_idx + 1}"

                flags: Dict[str, str] = {}
                for fl_el in pl_el.findall(".//conditionFlags/flag"):
                    fn = fl_el.attrib.get("name")
                    fv = fl_el.attrib.get("value", "true")
                    if fn:
                        flags[fn] = fv

                td_node = pl_el.find(".//typeDescriptor")
                type_descriptor = None
                if td_node is not None:
                    def_type = "Optional"
                    dt_node = td_node.find(".//defaultType")
                    if dt_node is not None:
                        def_type = dt_node.attrib.get("name", "Optional")
                    elif td_node.find("./type") is not None:
                        def_type = td_node.find("./type").attrib.get("name", "Optional")

                    patterns = []
                    for p_node in td_node.findall(".//patterns/pattern"):
                        dep_sub = p_node.find("./dependencies")
                        p_deps = parse_dependencies_node(dep_sub) if dep_sub is not None else None
                        t_sub = p_node.find("./type")
                        p_type = t_sub.attrib.get("name", "Optional") if t_sub is not None else "Optional"
                        patterns.append(TypeDescriptorPattern(dependencies=p_deps, type_name=p_type))

                    type_descriptor = TypeDescriptor(default_type=def_type, patterns=patterns)

                deps: Optional[FomodDependencies] = None
                dep_el = pl_el.find(".//typeDescriptor/dependencyType/defaultType/dependencies") or pl_el.find(".//dependencies")
                if dep_el is not None:
                    deps = parse_dependencies_node(dep_el)

                options.append(
                    FomodOption(
                        id=f"step_{step_idx}_grp_{grp_idx}_opt_{pl_idx}",
                        name=opt_name,
                        description=desc,
                        image_path=image_path,
                        files=files,
                        folders=folders,
                        flags=flags,
                        dependencies=deps,
                        is_default=(pl_idx == 0 and grp_type in (GroupType.SelectExactlyOne, GroupType.SelectAtLeastOne)),
                        type_descriptor=type_descriptor,
                    )
                )

            groups.append(
                FomodGroup(
                    id=f"step_{step_idx}_grp_{grp_idx}",
                    name=group_name,
                    type=grp_type,
                    options=options,
                )
            )

        steps.append(
            FomodStep(
                id=f"step_{step_idx}",
                name=step_name,
                groups=groups,
                visible=True,
            )
        )

    # Déduplication
    unique_steps: List[FomodStep] = []
    seen_sigs: Set[str] = set()
    for s in steps:
        sig = "|".join(
            f"{g.name}:" + ",".join(
                f"{o.name}:" + "+".join(sorted(f.source for f in o.files) + sorted(fo.source for fo in o.folders))
                for o in g.options
            )
            for g in s.groups
        )
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            unique_steps.append(s)

    conditional_installs: List[ConditionalInstallPattern] = []
    for pat_node in root.findall(".//conditionalFileInstalls/patterns/pattern"):
        dep_node = pat_node.find("./dependencies")
        p_deps = parse_dependencies_node(dep_node) if dep_node is not None else None
        p_files: List[FomodFileItem] = []
        p_folders: List[FomodFolderItem] = []

        for fl in pat_node.findall(".//files/file"):
            s = norm(fl.attrib.get("source"))
            d = norm(fl.attrib.get("destination"))
            prio = int(fl.attrib.get("priority", "0") or "0")
            if s:
                p_files.append(FomodFileItem(source=s, destination=d, priority=prio))

        for fld in pat_node.findall(".//files/folder"):
            s = norm(fld.attrib.get("source"))
            d = norm(fld.attrib.get("destination"))
            prio = int(fld.attrib.get("priority", "0") or "0")
            if s:
                p_folders.append(FomodFolderItem(source=s, destination=d, priority=prio))

        conditional_installs.append(
            ConditionalInstallPattern(dependencies=p_deps, files=p_files, folders=p_folders)
        )

    return module_name, unique_steps, required_files, conditional_installs

# ==============================================================================
# 3. EXTRACTION ET STAGING
# ==============================================================================


def resolve_file_destination(dest_rule: str, src_path: str) -> str:
    cleaned_dest = norm(dest_rule)
    cleaned_src = norm(src_path)
    file_name = cleaned_src.split("/")[-1]

    if not cleaned_dest or cleaned_dest == ".":
        return file_name

    ext = ""
    if "." in file_name:
        ext = "." + file_name.split(".")[-1].lower()

    if ext and cleaned_dest.lower().endswith(ext):
        return cleaned_dest

    return f"{cleaned_dest}/{file_name}"


def resolve_folder_destination(dest_rule: str, relative_inside_folder: str) -> str:
    cleaned_dest = norm(dest_rule)
    cleaned_rel = norm(relative_inside_folder)

    if not cleaned_dest or cleaned_dest == ".":
        return cleaned_rel
    return f"{cleaned_dest}/{cleaned_rel}"


def build_staging(
    selected_options: List[FomodOption],
    required_files: List[Any],
    archive_index: ArchiveIndex,
    conditional_installs: Optional[List[ConditionalInstallPattern]]=None,
    active_flags: Optional[Dict[str, str]]=None,
    installed_basenames: Optional[Set[str]]=None,
) -> StagingResult:
    dest_map: Dict[str, StagingItem] = {}
    logs: List[str] = []

    def process_item(item: Any, opt_name: str):
        if isinstance(item, FomodFileItem):
            entry = find_file_in_index(archive_index, item.source)
            if entry:
                dest = resolve_file_destination(item.destination, item.source)
                if dest not in dest_map or item.priority >= dest_map[dest].priority:
                    dest_map[dest] = StagingItem(
                        destination_path=dest,
                        source_entry=entry,
                        size=entry.size,
                        priority=item.priority,
                        matched_from_option=opt_name,
                    )
            else:
                folder_orig = find_folder_in_index(archive_index, item.source)
                if folder_orig:
                    folder_lower = folder_orig.lower().rstrip("/")
                    folder_slash = folder_lower + "/"
                    for k, entry in archive_index.files.items():
                        if getattr(entry, "is_dir", False) or "__macosx" in k:
                            continue
                        matched = False
                        rel_sub = ""
                        if k.startswith(folder_slash):
                            matched = True
                            rel_sub = entry.path[len(folder_lower):].lstrip("/\\")
                        elif ("/" + folder_slash) in ("/" + k):
                            idx = ("/" + k).find("/" + folder_slash)
                            matched = True
                            matched_prefix_len = idx + len(folder_lower)
                            rel_sub = entry.path[matched_prefix_len:].lstrip("/\\")
                        if matched:
                            dest = resolve_folder_destination(item.destination, rel_sub)
                            if dest not in dest_map or item.priority >= dest_map[dest].priority:
                                dest_map[dest] = StagingItem(
                                    destination_path=dest,
                                    source_entry=entry,
                                    size=entry.size,
                                    priority=item.priority,
                                    matched_from_option=opt_name,
                                )
                else:
                    logs.append(f"Avertissement : Fichier source non trouvé dans l'archive : '{item.source}'")
        elif isinstance(item, FomodFolderItem):
            folder_orig = find_folder_in_index(archive_index, item.source)
            if folder_orig:
                folder_lower = folder_orig.lower().rstrip("/")
                folder_slash = folder_lower + "/"
                found_any = False
                for k, entry in archive_index.files.items():
                    if getattr(entry, "is_dir", False) or "__macosx" in k:
                        continue
                    matched = False
                    rel_sub = ""
                    if k.startswith(folder_slash):
                        matched = True
                        rel_sub = entry.path[len(folder_lower):].lstrip("/\\")
                    elif ("/" + folder_slash) in ("/" + k):
                        idx = ("/" + k).find("/" + folder_slash)
                        matched = True
                        matched_prefix_len = idx + len(folder_lower)
                        rel_sub = entry.path[matched_prefix_len:].lstrip("/\\")
                    if matched:
                        found_any = True
                        dest = resolve_folder_destination(item.destination, rel_sub)
                        if dest not in dest_map or item.priority >= dest_map[dest].priority:
                            dest_map[dest] = StagingItem(
                                destination_path=dest,
                                source_entry=entry,
                                size=entry.size,
                                priority=item.priority,
                                matched_from_option=opt_name,
                            )
                if not found_any:
                    logs.append(f"Avertissement : Aucun fichier trouvé sous le dossier : '{item.source}'")
            else:
                entry = find_file_in_index(archive_index, item.source)
                if entry:
                    dest = resolve_file_destination(item.destination, item.source)
                    if dest not in dest_map or item.priority >= dest_map[dest].priority:
                        dest_map[dest] = StagingItem(
                            destination_path=dest,
                            source_entry=entry,
                            size=entry.size,
                            priority=item.priority,
                            matched_from_option=opt_name,
                        )
                else:
                    logs.append(f"Avertissement : Dossier source non trouvé dans l'archive : '{item.source}'")

    for req in required_files:
        process_item(req, "Requis")

    for opt in selected_options:
        for f in opt.files:
            process_item(f, opt.name)
        for fld in opt.folders:
            process_item(fld, opt.name)

    # Évaluation des installations conditionnelles globales (conditionalFileInstalls)
    if conditional_installs:
        flags = active_flags if active_flags is not None else {}
        inst_files = installed_basenames if installed_basenames is not None else set()
        for c_pat in conditional_installs:
            if evaluate_dependencies(c_pat.dependencies, flags, inst_files):
                for f in c_pat.files:
                    process_item(f, "Conditionnel")
                for fld in c_pat.folders:
                    process_item(fld, "Conditionnel")

    items = sorted(dest_map.values(), key=lambda x: x.destination_path.lower())
    total_size = sum(x.size for x in items)

    return StagingResult(
        items=items,
        total_size=total_size,
        copied_count=len(items),
        skipped_count=0,
        log=logs,
    )


def export_staging_to_directory(staging: StagingResult, target_dir: str, archive_path: Optional[str]=None):
    os.makedirs(target_dir, exist_ok=True)
    for item in staging.items:
        dest_full = os.path.join(target_dir, item.destination_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest_full), exist_ok=True)

        if item.source_entry.data is not None:
            with open(dest_full, "wb") as f:
                f.write(item.source_entry.data)
        elif item.source_entry.extracted_disk_path and os.path.exists(item.source_entry.extracted_disk_path):
            shutil.copy2(item.source_entry.extracted_disk_path, dest_full)
        elif archive_path and os.path.exists(archive_path) and zipfile.is_zipfile(archive_path):
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for name in zf.namelist():
                        if name.lower() == item.source_entry.path.lower():
                            with zf.open(name) as zf_in, open(dest_full, "wb") as f_out:
                                shutil.copyfileobj(zf_in, f_out)
                            break
            except Exception as e:
                logger.error(f"Erreur extraction ZIP pour {item.source_entry.path}: {e}")


def export_staging_to_zip(staging: StagingResult, zip_path: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in staging.items:
            if item.source_entry.data is not None:
                zf.writestr(item.destination_path, item.source_entry.data)
            elif item.source_entry.extracted_disk_path and os.path.exists(item.source_entry.extracted_disk_path):
                zf.write(item.source_entry.extracted_disk_path, item.destination_path)

# ==============================================================================
# 4. GOUVERNANCE DES IMAGES & APERÇUS VECTORIELS
# ==============================================================================


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
}


def generate_preview_pixmap(
    title: str,
    subtitle: str,
    bg_color: str="#1e293b",
    accent_color: str="#38bdf8",
    width: int=640,
    height: int=400,
) -> QPixmap:
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

    painter.setPen(QColor("#ffffff"))
    title_font = QFont(".AppleSystemUIFont" if sys.platform == "darwin" else "", 16, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(QRectF(20, 210, width - 40, 32), Qt.AlignmentFlag.AlignCenter, title)

    painter.setPen(QColor("#a1a1aa"))
    sub_font = QFont(".AppleSystemUIFont" if sys.platform == "darwin" else "", 12)
    painter.setFont(sub_font)
    painter.drawText(QRectF(20, 246, width - 40, 28), Qt.AlignmentFlag.AlignCenter, subtitle)

    painter.end()
    return pix


def load_pixmap_safely(file_path: Optional[str]=None, data: Optional[bytes]=None) -> Optional[QPixmap]:
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
        PIL_Image = importlib.import_module("PIL.Image")
        PIL_ImageQt = importlib.import_module("PIL.ImageQt")
        im = None
        if file_path and os.path.exists(file_path):
            im = PIL_Image.open(file_path)
        elif data:
            im = PIL_Image.open(io.BytesIO(data))
        if im is not None:
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            qim = PIL_ImageQt.ImageQt(im)
            pix = QPixmap.fromImage(qim)
            if not pix.isNull():
                return pix
    except Exception as e:
        logger.debug(f"Fallback Pillow échec : {e}")

    return None


def get_preview_pixmap_for_path(
    image_path: Optional[str],
    opt_name: str,
    opt_desc: str,
    archive_index: Optional[ArchiveIndex]=None,
) -> QPixmap:
    if image_path:
        norm_key = image_path.replace("\\", "/").strip().lower()

        # 1. Vérification dans l'archive indexée
        if archive_index:
            entry = find_file_in_index(archive_index, image_path)
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

    sub = (opt_desc.split(".")[0] + ".") if opt_desc else "Option de configuration du mod"
    if len(sub) > 65:
        sub = sub[:62] + "..."
    return generate_preview_pixmap(title=opt_name, subtitle=sub, bg_color="#1e293b", accent_color="#38bdf8")

# ==============================================================================
# 5. MODS DE DÉMONSTRATION INTÉGRÉS
# ==============================================================================


SAMPLE_CBBE_INFO_XML = """<?xml version="1.0" encoding="utf-8"?>
<fomod>
  <Name>Caliente's Beautiful Bodies Enhancer - CBBE - SE</Name>
  <Author>Caliente and Ousnius</Author>
  <Version>2.0.3</Version>
  <Website>https://www.nexusmods.com/skyrimspecialedition/mods/198</Website>
  <Description>Caliente's Beautiful Bodies Enhancer (CBBE) is a complete female body mesh and texture overhaul for The Elder Scrolls V: Skyrim Special Edition.</Description>
</fomod>"""

SAMPLE_CBBE_MODULE_CONFIG_XML = """<?xml version="1.0" encoding="utf-8"?>
<moduleConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>Caliente's Beautiful Bodies Enhancer - CBBE - SE</moduleName>
  <requiredInstallFiles>
    <folder source="00 Core" destination="." priority="0"/>
  </requiredInstallFiles>
  <installSteps order="Explicit">
    <installStep name="Silhouette &amp; Version du corps">
      <optionalFileGroups order="Explicit">
        <group name="Type de corps principal" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="CBBE Curvy (Recommandé)">
              <description>The standard voluptuous body shape. Best for users looking for feminine curves and full compatibility with existing armor conversions. Recommended for most players.</description>
              <image path="fomod/images/curvy.png"/>
              <files>
                <folder source="01 Curvy/meshes" destination="meshes" priority="1"/>
              </files>
            </plugin>
            <plugin name="CBBE Slim">
              <description>A more slender, athletic physique with reduced proportions. Maintains smooth topology and accurate rigging.</description>
              <image path="fomod/images/slim.png"/>
              <files>
                <folder source="01 Slim/meshes" destination="meshes" priority="1"/>
              </files>
            </plugin>
            <plugin name="CBBE Vanilla Shape">
              <description>Body proportions matched closely to original Bethesda Skyrim models while retaining the high vertex count and seamless seams of CBBE.</description>
              <image path="fomod/images/vanilla.png"/>
              <files>
                <folder source="01 Vanilla/meshes" destination="meshes" priority="1"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Résolution des Textures">
      <optionalFileGroups order="Explicit">
        <group name="Pack de textures de peau" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Textures 4K Ultra HD (Haute Qualité)">
              <description>Ultra-high definition diffuse, subsurface scattering, normal maps and specular maps (4096x4096). Recommended for GPUs with 6GB+ VRAM.</description>
              <image path="fomod/images/tex4k.png"/>
              <files>
                <folder source="02 Textures 4K/textures" destination="textures" priority="2"/>
              </files>
            </plugin>
            <plugin name="Textures 2K Haute Performance">
              <description>High quality 2048x2048 textures. Sharp details with minimal performance impact and reduced memory footprint.</description>
              <image path="fomod/images/tex2k.png"/>
              <files>
                <folder source="02 Textures 2K/textures" destination="textures" priority="2"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Moteur Physique &amp; Animation">
      <optionalFileGroups order="Explicit">
        <group name="Prise en charge de la physique" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Physique HDT-SMP / CBPC">
              <description>Enables dynamic physics weighting for breast, butt, and belly motion in real-time. Requires HDT-SMP or CBPC plugins.</description>
              <image path="fomod/images/physics.png"/>
              <files>
                <folder source="03 Physics/meshes" destination="meshes" priority="3"/>
                <file source="03 Physics/CBBE_Physics.esp" destination="CBBE_Physics.esp" priority="3"/>
              </files>
            </plugin>
            <plugin name="Corps Statique (Sans Physique)">
              <description>Standard static weighting without extra performance overhead. Recommended for lower end systems.</description>
              <image path="fomod/images/static.png"/>
              <files>
                <folder source="03 Static/meshes" destination="meshes" priority="3"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Tenues &amp; Modestie">
      <optionalFileGroups order="Explicit">
        <group name="Version des sous-vêtements" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Sous-vêtements (Underwear)">
              <description>Replaces default underwear with custom fitted textures and models for CBBE.</description>
              <image path="fomod/images/underwear.png"/>
              <files>
                <folder source="04 Underwear/meshes" destination="meshes" priority="4"/>
                <folder source="04 Underwear/textures" destination="textures" priority="4"/>
              </files>
            </plugin>
            <plugin name="NeverNude (Sécurisé pour Streaming)">
              <description>Includes permanent modesty cloth for safe livestreaming and public gameplay.</description>
              <image path="fomod/images/nevernude.png"/>
              <files>
                <folder source="04 NeverNude/meshes" destination="meshes" priority="4"/>
                <folder source="04 NeverNude/textures" destination="textures" priority="4"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Patches de Compatibilité">
      <optionalFileGroups order="Explicit">
        <group name="Modules additionnels" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="Patch d'intégration SkyUI SE">
              <description>Adds inventory icons and category filters tailored for body items. Automatically preselected when SkyUI_SE.esp is detected in Data.</description>
              <image path="fomod/images/skyui_patch.png"/>
              <files>
                <file source="05 Patches/CBBE_SkyUI_Addon.esp" destination="CBBE_SkyUI_Addon.esp" priority="5"/>
              </files>
              <dependencies operator="And">
                <fileDependency file="SkyUI_SE.esp" state="Active"/>
              </dependencies>
            </plugin>
            <plugin name="Support des Sliders RaceMenu (skee64)">
              <description>Installs body morph sliders, overlay textures and bodypaint slots into RaceMenu character generation menu.</description>
              <image path="fomod/images/racemenu_patch.png"/>
              <files>
                <folder source="05 RaceMenu/SKSE" destination="SKSE" priority="5"/>
                <file source="05 RaceMenu/CBBE_RaceMenu_Morphs.esp" destination="CBBE_RaceMenu_Morphs.esp" priority="5"/>
              </files>
              <dependencies operator="And">
                <fileDependency file="skee64.dll" state="Active"/>
              </dependencies>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</moduleConfiguration>"""


def get_demo_mod() -> Tuple[ArchiveIndex, str, str]:
    files: Dict[str, VirtualFileEntry] = {}
    dirs: Dict[str, str] = {}

    info_bytes = SAMPLE_CBBE_INFO_XML.encode("utf-8")
    files["fomod/info.xml"] = VirtualFileEntry(path="fomod/info.xml", size=len(info_bytes), data=info_bytes)
    dirs["fomod"] = "fomod"

    cfg_bytes = SAMPLE_CBBE_MODULE_CONFIG_XML.encode("utf-8")
    files["fomod/moduleconfig.xml"] = VirtualFileEntry(path="fomod/ModuleConfig.xml", size=len(cfg_bytes), data=cfg_bytes)

    dummy_files = [
        "00 Core/meshes/actors/character/character assets/femalehead.nif",
        "00 Core/textures/actors/character/female/femalehead.dds",
        "01 Curvy/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Curvy/meshes/actors/character/character assets/femalebody_1.nif",
        "01 Slim/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Slim/meshes/actors/character/character assets/femalebody_1.nif",
        "01 Vanilla/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Vanilla/meshes/actors/character/character assets/femalebody_1.nif",
        "02 Textures 4K/textures/actors/character/female/femalebody_4k.dds",
        "02 Textures 4K/textures/actors/character/female/femalebody_msn.dds",
        "02 Textures 2K/textures/actors/character/female/femalebody_2k.dds",
        "02 Textures 2K/textures/actors/character/female/femalebody_msn.dds",
        "03 Physics/meshes/actors/character/character assets/femalebody_physics.nif",
        "03 Physics/CBBE_Physics.esp",
        "03 Static/meshes/actors/character/character assets/femalebody_static.nif",
        "04 Underwear/meshes/actors/character/character assets/femaleunderwear.nif",
        "04 Underwear/textures/actors/character/female/underwear.dds",
        "04 NeverNude/meshes/actors/character/character assets/nevernude.nif",
        "04 NeverNude/textures/actors/character/female/nevernude.dds",
        "05 Patches/CBBE_SkyUI_Addon.esp",
        "05 RaceMenu/SKSE/Plugins/CharGen/Overlays.ini",
        "05 RaceMenu/CBBE_RaceMenu_Morphs.esp",
    ]

    for fpath in dummy_files:
        k = fpath.lower()
        sz = 14200 if fpath.endswith(".esp") else 854000
        files[k] = VirtualFileEntry(path=fpath, size=sz, data=b"DUMMY_DATA")

        parts = fpath.split("/")
        cur = ""
        for i in range(len(parts) - 1):
            cur = f"{cur}/{parts[i]}" if cur else parts[i]
            dirs[cur.lower()] = cur

    return ArchiveIndex(files=files, dirs=dirs), SAMPLE_CBBE_MODULE_CONFIG_XML, SAMPLE_CBBE_INFO_XML

# ==============================================================================
# 6. WORKERS QTHREAD NON-BLOQUANTS
# ==============================================================================


class StagingWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        selected_options: List[FomodOption],
        required_files: List[Any],
        archive_index: ArchiveIndex,
        conditional_installs: Optional[List[ConditionalInstallPattern]]=None,
        active_flags: Optional[Dict[str, str]]=None,
        installed_basenames: Optional[Set[str]]=None,
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
        try:
            res = build_staging(
                self.selected_options,
                self.required_files,
                self.archive_index,
                self.conditional_installs,
                self.active_flags,
                self.installed_basenames,
            )
            self.finished.emit(res)
        except Exception as e:
            logger.exception("Erreur staging worker")
            self.error.emit(str(e))


class ArchiveExtractWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object, str, str)
    error = pyqtSignal(str)

    def __init__(self, target_path: str, parent=None):
        super().__init__(parent)
        self.target_path = target_path

    def run(self):
        try:
            files: Dict[str, VirtualFileEntry] = {}
            dirs: Dict[str, str] = {}
            tmp = tempfile.mkdtemp(prefix="fomod_extracted_")

            target_lower = self.target_path.lower()
            if os.path.isdir(self.target_path):
                for root, _, fnames in os.walk(self.target_path):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, self.target_path).replace("\\", "/")
                        sz = os.path.getsize(fp)
                        files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                        parts = rel.split("/")
                        cur = ""
                        for i in range(len(parts) - 1):
                            cur = f"{cur}/{parts[i]}" if cur else parts[i]
                            dirs[cur.lower()] = cur
            elif target_lower.endswith(".zip") or zipfile.is_zipfile(self.target_path):
                with zipfile.ZipFile(self.target_path, "r") as zf:
                    zf.extractall(tmp)
                    for root, _, fnames in os.walk(tmp):
                        for fn in fnames:
                            fp = os.path.join(root, fn)
                            rel = os.path.relpath(fp, tmp).replace("\\", "/")
                            sz = os.path.getsize(fp)
                            files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                            parts = rel.split("/")
                            cur = ""
                            for i in range(len(parts) - 1):
                                cur = f"{cur}/{parts[i]}" if cur else parts[i]
                                dirs[cur.lower()] = cur
            elif target_lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2")) or tarfile.is_tarfile(self.target_path):
                with tarfile.open(self.target_path, "r:*") as tf:
                    tf.extractall(tmp)
                    for root, _, fnames in os.walk(tmp):
                        for fn in fnames:
                            fp = os.path.join(root, fn)
                            rel = os.path.relpath(fp, tmp).replace("\\", "/")
                            sz = os.path.getsize(fp)
                            files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                            parts = rel.split("/")
                            cur = ""
                            for i in range(len(parts) - 1):
                                cur = f"{cur}/{parts[i]}" if cur else parts[i]
                                dirs[cur.lower()] = cur
            elif target_lower.endswith(".7z"):
                # Tentative avec py7zr ou utilitaires CLI
                extracted_ok = False
                try:
                    import py7zr
                    with py7zr.SevenZipFile(self.target_path, "r") as sz:
                        sz.extractall(tmp)
                        extracted_ok = True
                except Exception as py7_e:
                    logger.warning("py7zr échec, tentative fallback CLI: %s", py7_e)

                if not extracted_ok:
                    cmd_7z = shutil.which("7z") or shutil.which("7za") or shutil.which("bsdtar")
                    if cmd_7z:
                        if "7z" in os.path.basename(cmd_7z):
                            subprocess.run([cmd_7z, "x", self.target_path, f"-o{tmp}", "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                        else:
                            subprocess.run([cmd_7z, "-xf", self.target_path, "-C", tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                        extracted_ok = True

                for root, _, fnames in os.walk(tmp):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, tmp).replace("\\", "/")
                        sz = os.path.getsize(fp)
                        files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                        parts = rel.split("/")
                        cur = ""
                        for i in range(len(parts) - 1):
                            cur = f"{cur}/{parts[i]}" if cur else parts[i]
                            dirs[cur.lower()] = cur
            elif target_lower.endswith(".rar"):
                extracted_ok = False
                try:
                    rarfile = importlib.import_module("rarfile")
                    with rarfile.RarFile(self.target_path, "r") as rf:
                        rf.extractall(tmp)
                        extracted_ok = True
                except Exception as rar_e:
                    logger.warning("rarfile échec: %s", rar_e)

                if not extracted_ok:
                    cmd_rar = shutil.which("7z") or shutil.which("unrar") or shutil.which("bsdtar")
                    if cmd_rar:
                        if "7z" in os.path.basename(cmd_rar):
                            subprocess.run([cmd_rar, "x", self.target_path, f"-o{tmp}", "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                        elif "unrar" in os.path.basename(cmd_rar):
                            subprocess.run([cmd_rar, "x", "-y", self.target_path, tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                        else:
                            subprocess.run([cmd_rar, "-xf", self.target_path, "-C", tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                        extracted_ok = True

                for root, _, fnames in os.walk(tmp):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, tmp).replace("\\", "/")
                        sz = os.path.getsize(fp)
                        files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                        parts = rel.split("/")
                        cur = ""
                        for i in range(len(parts) - 1):
                            cur = f"{cur}/{parts[i]}" if cur else parts[i]
                            dirs[cur.lower()] = cur
            else:
                # Tentative zipfile
                try:
                    with zipfile.ZipFile(self.target_path, "r") as zf:
                        zf.extractall(tmp)
                except Exception:
                    pass
                for root, _, fnames in os.walk(tmp):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, tmp).replace("\\", "/")
                        sz = os.path.getsize(fp)
                        files[rel.lower()] = VirtualFileEntry(path=rel, size=sz, extracted_disk_path=fp)
                        parts = rel.split("/")
                        cur = ""
                        for i in range(len(parts) - 1):
                            cur = f"{cur}/{parts[i]}" if cur else parts[i]
                            dirs[cur.lower()] = cur

            files, dirs = reanchor_index(files, dirs)
            index = ArchiveIndex(files=files, dirs=dirs, temp_dir=tmp, archive_path=self.target_path)

            info_xml = ""
            for k, entry in index.files.items():
                if k.endswith("fomod/info.xml"):
                    if entry.extracted_disk_path:
                        with open(entry.extracted_disk_path, "r", encoding="utf-8", errors="ignore") as f:
                            info_xml = f.read()
                    break

            cfg_xml = ""
            for k, entry in index.files.items():
                if k.endswith("fomod/moduleconfig.xml"):
                    if entry.extracted_disk_path:
                        with open(entry.extracted_disk_path, "r", encoding="utf-8", errors="ignore") as f:
                            cfg_xml = f.read()
                    break

            self.finished.emit(index, cfg_xml, info_xml)
        except Exception as e:
            logger.exception("Erreur extraction archive")
            self.error.emit(str(e))

# ==============================================================================
# 7. COMPOSANTS GRAPHIQUES & MODALES
# ==============================================================================


class CircularSpinnerWidget(QWidget):
    """Spinner circulaire animé identique au web (Screenshot 3)."""

    def __init__(self, size: int=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        from PyQt6.QtCore import QTimer
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
    """Overlay plein écran affiché lors du survol Drag & Drop (Screenshot 2)."""

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
        pen = QPen(QColor("#0284c7"), 3, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 6])
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(6, 6, -6, -6))


class LoadingOverlayWidget(QWidget):
    """Modal de progression plein écran avec spinner circulaire animé (Screenshot 3)."""

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

        # Spinner circulaire animé
        self.spinner = CircularSpinnerWidget(48)
        card_layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("Chargement du mod FOMOD")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_lbl)

        # Status box
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
        sub_lbl.setStyleSheet("font-size: 11px; color: #888888; border: none; background: transparent;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(sub_lbl)

        layout.addWidget(card)

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 204))  # 80% opacity


class IndicatorWidget(QWidget):
    """Indicateur visuel (Radio rond ou Checkbox carré) identique au web."""

    def __init__(self, is_single: bool, is_checked: bool, parent=None):
        super().__init__(parent)
        self.is_single = is_single
        self.is_checked = is_checked
        self.setFixedSize(18, 18)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        if self.is_single:
            if self.is_checked:
                painter.setPen(QPen(QColor("#0ea5e9"), 1.5))
                painter.setBrush(QBrush(QColor("#0ea5e9")))
                painter.drawEllipse(rect)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor("#ffffff")))
                painter.drawEllipse(rect.center(), 3, 3)
            else:
                painter.setPen(QPen(QColor("#555555"), 1.5))
                painter.setBrush(QBrush(QColor("#222222")))
                painter.drawEllipse(rect)
        else:
            if self.is_checked:
                painter.setPen(QPen(QColor("#0ea5e9"), 1.5))
                painter.setBrush(QBrush(QColor("#0ea5e9")))
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(QPen(QColor("#ffffff"), 1.8))
                painter.drawLine(rect.left() + 4, rect.top() + 8, rect.left() + 7, rect.bottom() - 4)
                painter.drawLine(rect.left() + 7, rect.bottom() - 4, rect.right() - 4, rect.top() + 5)
            else:
                painter.setPen(QPen(QColor("#555555"), 1.5))
                painter.setBrush(QBrush(QColor("#222222")))
                painter.drawRoundedRect(rect, 3, 3)

        painter.end()



# ==============================================================================
# INTERNATIONALISATION (i18n) AUTONOME (FR, EN, IT, ES)
# ==============================================================================

AVAILABLE_LANGUAGES = [
    ("fr", "Français", "🇫🇷"),
    ("en", "English", "🇬🇧"),
    ("it", "Italiano", "🇮🇹"),
    ("es", "Español", "🇪🇸"),
]

FR_STRINGS = {   'common': {   'activeFlags': 'flags actifs',
                  'apply': 'Appliquer',
                  'auto': 'Auto',
                  'cancel': 'Annuler',
                  'clickToSimulate': '(Cliquez pour simuler Skyrim)',
                  'close': 'Fermer',
                  'confirm': 'Confirmer',
                  'dataFolder': 'Data :',
                  'destination': 'Destination :',
                  'filesDetected': 'fichiers détectés',
                  'loading': 'Chargement...',
                  'multipleChoice': 'Choix multiple',
                  'notSet': '(non défini)',
                  'of': 'sur',
                  'singleChoice': 'Choix unique',
                  'step': 'Étape'},
    'error': {   'cannotLoad': "Impossible de charger l'archive",
                 'tip1': "Assurez-vous que l'archive contient bien un fichier fomod/ModuleConfig.xml.",
                 'tip2': 'Si votre archive est un fichier .RAR ou .7Z dans un format propriétaire très récent (ex: '
                         'RAR5), vous pouvez la convertir en .ZIP standard ou glisser le dossier décompressé.',
                 'tipsTitle': 'Conseils pour ouvrir votre mod :'},
    'header': {   'closeMod': '← Fermer le mod',
                  'closeModTooltip': "Fermer le mod en cours et revenir à l'écran d'accueil",
                  'flagsCount': '{count} flags actifs',
                  'skyrimEnv': 'Skyrim SE/AE',
                  'stepCounter': 'Étape {current} / {total}',
                  'title': "Simulateur d'Installateur FOMOD",
                  'waitingArchive': "Skyrim SE/AE • En attente d'archive"},
    'loading': {   'inProgress': 'Traitement en cours...',
                   'sub': "Extraction en mémoire et génération de l'installateur à 3 colonnes...",
                   'title': 'Chargement du mod FOMOD'},
    'modals': {   'dataDir': {   'apply': 'Enregistrer et Analyser',
                                 'browseFolder': '📁 Parcourir le disque...',
                                 'currentPath': 'Dossier sélectionné :',
                                 'desc': 'Le simulateur utilise la liste des fichiers existants (.esp, .esm, .esl, '
                                         ".dll) pour évaluer automatiquement les conditions d'installation FOMOD "
                                         '(fichiers requis/recommandés).',
                                 'detectedPlugins': 'Plugins et DLLs détectés',
                                 'loadPresets': 'Ou choisir un profil de chargement simulé :',
                                 'manualInput': 'Saisie manuelle (un fichier par ligne) :',
                                 'noFolderSelected': '(Aucun dossier sélectionné)',
                                 'title': 'Configuration du dossier Skyrim Data'},
                  'modInfo': {   'author': 'Auteur',
                                 'description': 'Description',
                                 'name': 'Nom',
                                 'title': 'Infos du mod',
                                 'version': 'Version',
                                 'website': 'Site Web'},
                  'openMod': {   'browseArchive': '📦 Parcourir une archive (.ZIP, .RAR, .7Z)',
                                 'browseFolder': '📂 Parcourir un dossier décompressé',
                                 'cbbeDesc': 'Fomod complexe complet (6 étapes, physique HDT/CBPC, drapeaux '
                                             'conditionnels, options exclusives et multiples)',
                                 'demoMods': 'Mods de démonstration réalistes intégrés',
                                 'fromComputer': 'Depuis votre ordinateur',
                                 'load': 'Charger',
                                 'smimDesc': 'Fomod étendu multi-options (matériaux, textures, meshes haute résolution '
                                             'pour éléments du décor)',
                                 'title': 'Ouvrir un FOMOD'},
                  'staging': {   'cleanInstall': 'Aucun avertissement. Installation propre.',
                                 'filesInstalled': 'Fichiers installés',
                                 'openFolder': 'Ouvrir le dossier généré',
                                 'stagingLog': 'Journal de staging',
                                 'title': 'Résultats de la simulation de Staging',
                                 'totalFiles': 'Fichiers :',
                                 'totalSize': 'Taille totale :',
                                 'writeSuccess': 'Fichiers écrits avec succès dans votre dossier local !'}},
    'preview': {   'clickToEnlarge': 'Cliquer pour afficher dans sa taille réelle',
                   'defaultSubtitle': 'Option de configuration du mod',
                   'defaultTitle': 'Aperçu FOMOD',
                   'enlarge': '🔍 Agrandir',
                   'instructionsTitle': 'Instructions & Description',
                   'noImage': 'Aucun aperçu disponible pour cette option.',
                   'tabDescription': "Description de l'option",
                   'tabInstructions': 'Instructions & Prérequis'},
    'sidebar': {   'chooseDataDir': 'Dossier Skyrim Data...',
                   'chooseStagingDir': 'Destination du Staging...',
                   'generateStaging': 'GÉNÉRER LE STAGING',
                   'modInfo': 'Infos du mod',
                   'openFomod': 'Ouvrir un FOMOD',
                   'openFomodTooltip': 'Ouvrir un FOMOD (.zip, dossier, ou démo)',
                   'sectionControls': 'ACTIONS & MOD',
                   'sectionStaging': 'SIMULATION DE STAGING',
                   'targetDesktop': 'Bureau (Desktop)',
                   'targetDownloads': 'Téléchargements'},
    'steps': {   'autoDetected': 'Dépendance détectée dans votre dossier Data',
                 'couldBeUsable': 'Pourrait être utilisable',
                 'finishStep': "TERMINER L'INSTALLATION",
                 'loadDemoAction': 'Charger le mod exemple CBBE',
                 'nextStep': 'CONTINUER →',
                 'noStepsFound': 'Aucune étape FOMOD trouvée.',
                 'notUsable': 'Inutilisable',
                 'prevStep': '← RETOUR',
                 'recommended': 'Recommandé',
                 'required': 'Requis'},
    'welcome': {   'dropTitle': 'Glissez-déposez votre archive ici',
                   'loadArchiveBtn': 'Charger une archive (ZIP, 7Z, RAR)',
                   'loadDemoBtn': 'Charger le mod démo CBBE',
                   'loadFolderBtn': 'Charger un dossier décompressé',
                   'noGameRequired': 'Aucune installation de Skyrim requise',
                   'selectLanguage': "Langue de l'application :",
                   'standaloneEngine': 'Moteur FOMOD 100% autonome',
                   'subtitle': 'Ouvrez ou glissez-déposez une archive de mod Skyrim pour explorer les étapes '
                               "d'installation, tester les conditions logiques et simuler le staging sans modifier vos "
                               'fichiers de jeu.',
                   'supportedFormats': 'Formats supportés : <span style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.ZIP</span>, <span style="color:#38bdf8; '
                                       'font-weight:600; font-family:\'Menlo\',monospace;">.7Z</span>, <span '
                                       'style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.RAR</span> ou dossier décompressé',
                   'title': "Simulateur d'Installateur FOMOD"}}

EN_STRINGS = {   'common': {   'activeFlags': 'active flags',
                  'apply': 'Apply',
                  'auto': 'Auto',
                  'cancel': 'Cancel',
                  'clickToSimulate': '(Click to simulate Skyrim)',
                  'close': 'Close',
                  'confirm': 'Confirm',
                  'dataFolder': 'Data:',
                  'destination': 'Destination:',
                  'filesDetected': 'files detected',
                  'loading': 'Loading...',
                  'multipleChoice': 'Multiple choice',
                  'notSet': '(not set)',
                  'of': 'of',
                  'singleChoice': 'Single choice',
                  'step': 'Step'},
    'error': {   'cannotLoad': 'Cannot load archive',
                 'tip1': 'Ensure the archive contains a fomod/ModuleConfig.xml file.',
                 'tip2': 'If your archive is a .RAR or .7Z in a very recent proprietary format (e.g. RAR5), you can '
                         'convert it to standard .ZIP or drag the uncompressed folder.',
                 'tipsTitle': 'Tips to open your mod:'},
    'header': {   'closeMod': '← Close mod',
                  'closeModTooltip': 'Close current mod and return to welcome screen',
                  'flagsCount': '{count} active flags',
                  'skyrimEnv': 'Skyrim SE/AE',
                  'stepCounter': 'Step {current} / {total}',
                  'title': 'FOMOD Installer Simulator',
                  'waitingArchive': 'Skyrim SE/AE • Waiting for archive'},
    'loading': {   'inProgress': 'Processing...',
                   'sub': 'In-memory extraction and 3-column installer generation...',
                   'title': 'Loading FOMOD mod'},
    'modals': {   'dataDir': {   'apply': 'Save and Analyze',
                                 'browseFolder': '📁 Browse disk...',
                                 'currentPath': 'Selected folder:',
                                 'desc': 'The simulator uses the list of existing files (.esp, .esm, .esl, .dll) to '
                                         'automatically evaluate FOMOD installation conditions (required/recommended '
                                         'files).',
                                 'detectedPlugins': 'Detected plugins and DLLs',
                                 'loadPresets': 'Or choose a simulated load order profile:',
                                 'manualInput': 'Manual input (one file per line):',
                                 'noFolderSelected': '(No folder selected)',
                                 'title': 'Skyrim Data Folder Configuration'},
                  'modInfo': {   'author': 'Author',
                                 'description': 'Description',
                                 'name': 'Name',
                                 'title': 'Mod Info',
                                 'version': 'Version',
                                 'website': 'Website'},
                  'openMod': {   'browseArchive': '📦 Browse an archive (.ZIP, .RAR, .7Z)',
                                 'browseFolder': '📂 Browse an uncompressed folder',
                                 'cbbeDesc': 'Full complex FOMOD (6 steps, HDT/CBPC physics, conditional flags, '
                                             'exclusive and multiple options)',
                                 'demoMods': 'Built-in realistic demo mods',
                                 'fromComputer': 'From your computer',
                                 'load': 'Load',
                                 'smimDesc': 'Extensive multi-option FOMOD (materials, textures, high-resolution '
                                             'meshes for world items)',
                                 'title': 'Open a FOMOD'},
                  'staging': {   'cleanInstall': 'No warnings. Clean installation.',
                                 'filesInstalled': 'Installed files',
                                 'openFolder': 'Open generated folder',
                                 'stagingLog': 'Staging log',
                                 'title': 'Staging Simulation Results',
                                 'totalFiles': 'Files:',
                                 'totalSize': 'Total size:',
                                 'writeSuccess': 'Files successfully written to your local folder!'}},
    'preview': {   'clickToEnlarge': 'Click to view full size',
                   'defaultSubtitle': 'Mod configuration option',
                   'defaultTitle': 'FOMOD Preview',
                   'enlarge': '🔍 Enlarge',
                   'instructionsTitle': 'Instructions & Description',
                   'noImage': 'No preview available for this option.',
                   'tabDescription': 'Option description',
                   'tabInstructions': 'Instructions & Prerequisites'},
    'sidebar': {   'chooseDataDir': 'Skyrim Data folder...',
                   'chooseStagingDir': 'Staging destination...',
                   'generateStaging': 'GENERATE STAGING',
                   'modInfo': 'Mod info',
                   'openFomod': 'Open a FOMOD',
                   'openFomodTooltip': 'Open a FOMOD (.zip, folder, or demo)',
                   'sectionControls': 'ACTIONS & MOD',
                   'sectionStaging': 'STAGING SIMULATION',
                   'targetDesktop': 'Desktop',
                   'targetDownloads': 'Downloads'},
    'steps': {   'autoDetected': 'Dependency detected in your Data folder',
                 'couldBeUsable': 'Could be usable',
                 'finishStep': 'FINISH INSTALLATION',
                 'loadDemoAction': 'Load sample mod CBBE',
                 'nextStep': 'CONTINUE →',
                 'noStepsFound': 'No FOMOD steps found.',
                 'notUsable': 'Not usable',
                 'prevStep': '← BACK',
                 'recommended': 'Recommended',
                 'required': 'Required'},
    'welcome': {   'dropTitle': 'Drag and drop your archive here',
                   'loadArchiveBtn': 'Load an archive (ZIP, 7Z, RAR)',
                   'loadDemoBtn': 'Load demo mod CBBE',
                   'loadFolderBtn': 'Load uncompressed folder',
                   'noGameRequired': 'No Skyrim installation required',
                   'selectLanguage': 'Application language:',
                   'standaloneEngine': '100% standalone FOMOD engine',
                   'subtitle': 'Open or drag-and-drop a Skyrim mod archive to explore installation steps, test logical '
                               'conditions, and simulate staging without altering your game files.',
                   'supportedFormats': 'Supported formats: <span style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.ZIP</span>, <span style="color:#38bdf8; '
                                       'font-weight:600; font-family:\'Menlo\',monospace;">.7Z</span>, <span '
                                       'style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.RAR</span> or uncompressed folder',
                   'title': 'FOMOD Installer Simulator'}}

IT_STRINGS = {   'common': {   'activeFlags': 'flag attivi',
                  'apply': 'Applica',
                  'auto': 'Auto',
                  'cancel': 'Annulla',
                  'clickToSimulate': '(Clicca per simulare Skyrim)',
                  'close': 'Chiudi',
                  'confirm': 'Conferma',
                  'dataFolder': 'Data:',
                  'destination': 'Destinazione:',
                  'filesDetected': 'file rilevati',
                  'loading': 'Caricamento...',
                  'multipleChoice': 'Scelta multipla',
                  'notSet': '(non impostato)',
                  'of': 'di',
                  'singleChoice': 'Scelta singola',
                  'step': 'Passaggio'},
    'error': {   'cannotLoad': "Impossibile caricare l'archivio",
                 'tip1': "Assicurati che l'archivio contenga un file fomod/ModuleConfig.xml.",
                 'tip2': "Se l'archivio è in formato .RAR o .7Z recente (es. RAR5), puoi convertirlo in .ZIP standard "
                         'o trascinare la cartella decompressa.',
                 'tipsTitle': 'Suggerimenti per aprire il tuo mod:'},
    'header': {   'closeMod': '← Chiudi mod',
                  'closeModTooltip': 'Chiudi il mod corrente e torna alla schermata iniziale',
                  'flagsCount': '{count} flag attivi',
                  'skyrimEnv': 'Skyrim SE/AE',
                  'stepCounter': 'Passaggio {current} / {total}',
                  'title': 'Simulatore di Installatore FOMOD',
                  'waitingArchive': 'Skyrim SE/AE • In attesa di archivio'},
    'loading': {   'inProgress': 'Elaborazione in corso...',
                   'sub': "Estrazione in memoria e generazione dell'installatore a 3 colonne...",
                   'title': 'Caricamento mod FOMOD'},
    'modals': {   'dataDir': {   'apply': 'Salva e Analizza',
                                 'browseFolder': '📁 Sfoglia disco...',
                                 'currentPath': 'Cartella selezionata:',
                                 'desc': "Il simulatore usa l'elenco dei file esistenti (.esp, .esm, .esl, .dll) per "
                                         'valutare automaticamente le condizioni di installazione FOMOD (file '
                                         'richiesti/consigliati).',
                                 'detectedPlugins': 'Plugin e DLL rilevati',
                                 'loadPresets': 'Oppure scegli un profilo di load order simulato:',
                                 'manualInput': 'Inserimento manuale (un file per riga):',
                                 'noFolderSelected': '(Nessuna cartella selezionata)',
                                 'title': 'Configurazione cartella Skyrim Data'},
                  'modInfo': {   'author': 'Autore',
                                 'description': 'Descrizione',
                                 'name': 'Nome',
                                 'title': 'Info sul mod',
                                 'version': 'Versione',
                                 'website': 'Sito Web'},
                  'openMod': {   'browseArchive': '📦 Sfoglia un archivio (.ZIP, .RAR, .7Z)',
                                 'browseFolder': '📂 Sfoglia cartella decompressa',
                                 'cbbeDesc': 'FOMOD complesso completo (6 passaggi, fisica HDT/CBPC, flag '
                                             'condizionali, opzioni esclusive e multiple)',
                                 'demoMods': 'Mod demo realistici integrati',
                                 'fromComputer': 'Dal tuo computer',
                                 'load': 'Carica',
                                 'smimDesc': 'FOMOD esteso multi-opzione (materiali, texture, mesh ad alta risoluzione '
                                             'per oggetti dello scenario)',
                                 'title': 'Apri un FOMOD'},
                  'staging': {   'cleanInstall': 'Nessun avviso. Installazione pulita.',
                                 'filesInstalled': 'File installati',
                                 'openFolder': 'Apri la cartella generata',
                                 'stagingLog': 'Registro di staging',
                                 'title': 'Risultati della simulazione di Staging',
                                 'totalFiles': 'File:',
                                 'totalSize': 'Dimensione totale:',
                                 'writeSuccess': 'File scritti con successo nella tua cartella locale!'}},
    'preview': {   'clickToEnlarge': 'Clicca per ingrandire a dimensione reale',
                   'defaultSubtitle': 'Opzione di configurazione del mod',
                   'defaultTitle': 'Anteprima FOMOD',
                   'enlarge': '🔍 Ingrandisci',
                   'instructionsTitle': 'Istruzioni e Descrizione',
                   'noImage': 'Nessuna anteprima disponibile per questa opzione.',
                   'tabDescription': 'Descrizione opzione',
                   'tabInstructions': 'Istruzioni e Prerequisiti'},
    'sidebar': {   'chooseDataDir': 'Cartella Skyrim Data...',
                   'chooseStagingDir': 'Destinazione Staging...',
                   'generateStaging': 'GENERA STAGING',
                   'modInfo': 'Info sul mod',
                   'openFomod': 'Apri un FOMOD',
                   'openFomodTooltip': 'Apri un FOMOD (.zip, cartella, o demo)',
                   'sectionControls': 'AZIONI & MOD',
                   'sectionStaging': 'SIMULAZIONE DI STAGING',
                   'targetDesktop': 'Scrivania (Desktop)',
                   'targetDownloads': 'Download'},
    'steps': {   'autoDetected': 'Dipendenza rilevata nella tua cartella Data',
                 'couldBeUsable': 'Potrebbe essere utilizzabile',
                 'finishStep': 'COMPLETA INSTALLAZIONE',
                 'loadDemoAction': 'Carica il mod di esempio CBBE',
                 'nextStep': 'CONTINUA →',
                 'noStepsFound': 'Nessun passaggio FOMOD trovato.',
                 'notUsable': 'Inutilizzabile',
                 'prevStep': '← INDIETRO',
                 'recommended': 'Consigliato',
                 'required': 'Richiesto'},
    'welcome': {   'dropTitle': 'Trascina il tuo archivio qui',
                   'loadArchiveBtn': 'Carica un archivio (ZIP, 7Z, RAR)',
                   'loadDemoBtn': 'Carica mod demo CBBE',
                   'loadFolderBtn': 'Carica cartella decompressa',
                   'noGameRequired': 'Nessuna installazione di Skyrim richiesta',
                   'selectLanguage': "Lingua dell'applicazione:",
                   'standaloneEngine': 'Motore FOMOD 100% autonomo',
                   'subtitle': 'Apri o trascina un archivio mod di Skyrim per esplorare i passaggi di installazione, '
                               'verificare le condizioni logiche e simulare lo staging senza modificare i file di '
                               'gioco.',
                   'supportedFormats': 'Formati supportati: <span style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.ZIP</span>, <span style="color:#38bdf8; '
                                       'font-weight:600; font-family:\'Menlo\',monospace;">.7Z</span>, <span '
                                       'style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.RAR</span> o cartella decompressa',
                   'title': 'Simulatore di Installatore FOMOD'}}

ES_STRINGS = {   'common': {   'activeFlags': 'flags activos',
                  'apply': 'Aplicar',
                  'auto': 'Auto',
                  'cancel': 'Cancelar',
                  'clickToSimulate': '(Haga clic para simular Skyrim)',
                  'close': 'Cerrar',
                  'confirm': 'Confirmar',
                  'dataFolder': 'Data:',
                  'destination': 'Destino:',
                  'filesDetected': 'archivos detectados',
                  'loading': 'Cargando...',
                  'multipleChoice': 'Opción múltiple',
                  'notSet': '(no definido)',
                  'of': 'de',
                  'singleChoice': 'Opción única',
                  'step': 'Paso'},
    'error': {   'cannotLoad': 'No se puede cargar el archivo',
                 'tip1': 'Asegúrese de que el archivo contenga un archivo fomod/ModuleConfig.xml.',
                 'tip2': 'Si su archivo es un .RAR o .7Z en un formato propietario muy reciente (p. ej., RAR5), puede '
                         'convertirlo a .ZIP estándar o arrastrar la carpeta descomprimida.',
                 'tipsTitle': 'Consejos para abrir su mod:'},
    'header': {   'closeMod': '← Cerrar mod',
                  'closeModTooltip': 'Cerrar el mod actual y volver a la pantalla de inicio',
                  'flagsCount': '{count} flags activos',
                  'skyrimEnv': 'Skyrim SE/AE',
                  'stepCounter': 'Paso {current} / {total}',
                  'title': 'Simulador de Instalador FOMOD',
                  'waitingArchive': 'Skyrim SE/AE • Esperando archivo'},
    'loading': {   'inProgress': 'Procesando...',
                   'sub': 'Extracción en memoria y generación del instalador de 3 columnas...',
                   'title': 'Cargando mod FOMOD'},
    'modals': {   'dataDir': {   'apply': 'Guardar y Analizar',
                                 'browseFolder': '📁 Examinar disco...',
                                 'currentPath': 'Carpeta seleccionada:',
                                 'desc': 'El simulador utiliza la lista de archivos existentes (.esp, .esm, .esl, '
                                         '.dll) para evaluar automáticamente las condiciones de instalación FOMOD '
                                         '(archivos requeridos/recomendados).',
                                 'detectedPlugins': 'Plugins y DLL detectados',
                                 'loadPresets': 'O elija un perfil de orden de carga simulado:',
                                 'manualInput': 'Entrada manual (un archivo por línea):',
                                 'noFolderSelected': '(Ninguna carpeta seleccionada)',
                                 'title': 'Configuración de la carpeta Skyrim Data'},
                  'modInfo': {   'author': 'Autor',
                                 'description': 'Descripción',
                                 'name': 'Nombre',
                                 'title': 'Info del mod',
                                 'version': 'Versión',
                                 'website': 'Sitio Web'},
                  'openMod': {   'browseArchive': '📦 Examinar un archivo (.ZIP, .RAR, .7Z)',
                                 'browseFolder': '📂 Examinar carpeta descomprimida',
                                 'cbbeDesc': 'FOMOD complejo completo (6 pasos, física HDT/CBPC, flags condicionales, '
                                             'opciones exclusivas y múltiples)',
                                 'demoMods': 'Mods de demostración realistas integrados',
                                 'fromComputer': 'Desde tu ordenador',
                                 'load': 'Cargar',
                                 'smimDesc': 'FOMOD extendido de múltiples opciones (materiales, texturas, mallas de '
                                             'alta resolución para objetos del entorno)',
                                 'title': 'Abrir un FOMOD'},
                  'staging': {   'cleanInstall': 'Sin advertencias. Instalación limpia.',
                                 'filesInstalled': 'Archivos instalados',
                                 'openFolder': 'Abrir carpeta generada',
                                 'stagingLog': 'Registro de staging',
                                 'title': 'Resultados de la simulación de Staging',
                                 'totalFiles': 'Archivos:',
                                 'totalSize': 'Tamaño total:',
                                 'writeSuccess': '¡Archivos escritos con éxito en su carpeta local!'}},
    'preview': {   'clickToEnlarge': 'Haga clic para ver en tamaño real',
                   'defaultSubtitle': 'Opción de configuración del mod',
                   'defaultTitle': 'Vista previa de FOMOD',
                   'enlarge': '🔍 Ampliar',
                   'instructionsTitle': 'Instrucciones y Descripción',
                   'noImage': 'No hay vista previa disponible para esta opción.',
                   'tabDescription': 'Descripción de la opción',
                   'tabInstructions': 'Instrucciones y Requisitos'},
    'sidebar': {   'chooseDataDir': 'Carpeta Skyrim Data...',
                   'chooseStagingDir': 'Destino de Staging...',
                   'generateStaging': 'GENERAR STAGING',
                   'modInfo': 'Info del mod',
                   'openFomod': 'Abrir un FOMOD',
                   'openFomodTooltip': 'Abrir un FOMOD (.zip, carpeta o demo)',
                   'sectionControls': 'ACCIONES Y MOD',
                   'sectionStaging': 'SIMULACIÓN DE STAGING',
                   'targetDesktop': 'Escritorio (Desktop)',
                   'targetDownloads': 'Descargas'},
    'steps': {   'autoDetected': 'Dependencia detectada en su carpeta Data',
                 'couldBeUsable': 'Podría ser utilizable',
                 'finishStep': 'FINALIZAR INSTALACIÓN',
                 'loadDemoAction': 'Cargar mod de ejemplo CBBE',
                 'nextStep': 'CONTINUAR →',
                 'noStepsFound': 'No se encontraron pasos FOMOD.',
                 'notUsable': 'Inutilizable',
                 'prevStep': '← ATRÁS',
                 'recommended': 'Recomendado',
                 'required': 'Requerido'},
    'welcome': {   'dropTitle': 'Arrastre y suelte su archivo aquí',
                   'loadArchiveBtn': 'Cargar un archivo (ZIP, 7Z, RAR)',
                   'loadDemoBtn': 'Cargar mod de demostración CBBE',
                   'loadFolderBtn': 'Cargar carpeta descomprimida',
                   'noGameRequired': 'No se requiere instalación de Skyrim',
                   'selectLanguage': 'Idioma de la aplicación:',
                   'standaloneEngine': 'Motor FOMOD 100% autónomo',
                   'subtitle': 'Abra o arrastre y suelte un archivo mod de Skyrim para explorar los pasos de '
                               'instalación, probar las condiciones lógicas y simular la preparación sin modificar sus '
                               'archivos de juego.',
                   'supportedFormats': 'Formatos compatibles: <span style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.ZIP</span>, <span style="color:#38bdf8; '
                                       'font-weight:600; font-family:\'Menlo\',monospace;">.7Z</span>, <span '
                                       'style="color:#38bdf8; font-weight:600; '
                                       'font-family:\'Menlo\',monospace;">.RAR</span> o carpeta descomprimida',
                   'title': 'Simulador de Instalador FOMOD'}}

TRANSLATIONS = {
    "fr": FR_STRINGS,
    "en": EN_STRINGS,
    "it": IT_STRINGS,
    "es": ES_STRINGS,
}

DEFAULT_LANGUAGE = "fr"
SETTINGS_KEY = "language"


class I18nManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18nManager, cls).__new__(cls)
            cls._instance._init_settings()
        return cls._instance

    def _init_settings(self):
        try:
            self.settings = QSettings("SkyrimTools", "FOMODSimulator")
            saved_lang = self.settings.value(SETTINGS_KEY, DEFAULT_LANGUAGE)
        except Exception:
            self.settings = None
            saved_lang = DEFAULT_LANGUAGE
        if saved_lang not in TRANSLATIONS:
            saved_lang = DEFAULT_LANGUAGE
        self._current_lang = saved_lang

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_code: str) -> bool:
        if lang_code in TRANSLATIONS and lang_code != self._current_lang:
            self._current_lang = lang_code
            if self.settings:
                try:
                    self.settings.setValue(SETTINGS_KEY, lang_code)
                except Exception:
                    pass
            return True
        elif lang_code in TRANSLATIONS and self.settings:
            try:
                self.settings.setValue(SETTINGS_KEY, lang_code)
            except Exception:
                pass
        return False

    @property
    def strings(self):
        return TRANSLATIONS.get(self._current_lang, TRANSLATIONS[DEFAULT_LANGUAGE])

    def get(self, *keys: str, default: str = "") -> str:
        curr = self.strings
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                fallback = TRANSLATIONS[DEFAULT_LANGUAGE]
                for fb_k in keys:
                    if isinstance(fallback, dict) and fb_k in fallback:
                        fallback = fallback[fb_k]
                    else:
                        return default
                return str(fallback)
        return str(curr) if curr is not None else default


def get_i18n() -> I18nManager:
    return I18nManager()


class OptionRowWidget(QFrame):
    """Ligne d'option FOMOD interactive."""

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
        self.on_select = on_select_callback if on_select_callback is not None else (on_select if on_select is not None else (lambda _opt: None))
        self.on_hover = on_hover_callback if on_hover_callback is not None else (on_hover if on_hover is not None else (lambda _opt: None))
        self.setObjectName("OptionRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.indicator = IndicatorWidget(is_single, is_selected)
        layout.addWidget(self.indicator, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.label = QLabel(option.name)
        layout.addWidget(self.label, 1)

        if matches_dep:
            badge = QLabel(get_i18n().get("common", "auto", default="Auto"))
            badge.setStyleSheet(
                "background-color: rgba(14, 165, 233, 0.15); border: none; color: #38bdf8; font-size: 9px; font-weight: bold; padding: 2px 6px; border-radius: 3px;"
            )
            layout.addWidget(badge)

        self._update_style()

    def _update_style(self, hovered: bool=False):
        bg = "#232b36" if self.is_selected else ("#28282e" if hovered else "transparent")
        text_color = "#38bdf8" if self.is_selected else ("#ffffff" if hovered else "#cccccc")
        weight = "bold" if self.is_selected else "normal"
        self.setStyleSheet(f"QFrame#OptionRow {{ background-color: {bg}; border: none; border-radius: 5px; }}")
        self.label.setStyleSheet(f"background: transparent; border: none; font-size: 12px; font-weight: {weight}; color: {text_color};")

    def enterEvent(self, event):
        self._update_style(hovered=True)
        self.on_hover(self.option)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style(hovered=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_select(self.option)
        super().mousePressEvent(event)


class OpenModModal(QDialog):
    """Modale 'Ouvrir un FOMOD'."""

    def __init__(self, parent=None, on_open_archive=None, on_open_folder=None, on_load_sample=None):
        super().__init__(parent)
        self.setWindowTitle("Ouvrir un FOMOD")
        self.setMinimumSize(520, 480)
        self.resize(560, 520)
        self.setStyleSheet("QDialog { background-color: #1a1a1d; color: #ffffff; border: 1px solid #2a2a2e; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr_row = QHBoxLayout()
        title_lbl = QLabel("📦  Ouvrir un FOMOD")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #888888; font-size: 16px; } QPushButton:hover { color: #ffffff; }")
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("background-color: #27272a; max-height: 1px; border: none;")
        layout.addWidget(div1)

        sec1_lbl = QLabel("DEPUIS VOTRE ORDINATEUR")
        sec1_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #71717a; background: transparent; border: none;")
        layout.addWidget(sec1_lbl)

        btn_archive = QPushButton()
        btn_archive.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_archive.setStyleSheet("QPushButton { background-color: #242428; border: none; border-radius: 6px; padding: 12px; text-align: left; } QPushButton:hover { background-color: #2c2c32; }")
        btn_arch_layout = QVBoxLayout(btn_archive)
        btn_arch_layout.setContentsMargins(4, 2, 4, 2)
        btn_arch_layout.setSpacing(4)

        arch_row = QHBoxLayout()
        arch_title = QLabel("📦 Parcourir une archive (.ZIP, .RAR, .7Z)")
        arch_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #fbbf24; background: transparent; border: none;")
        arch_badge = QLabel("Support complet")
        arch_badge.setStyleSheet("font-size: 10px; color: #4ade80; background-color: rgba(74, 222, 128, 0.15); border: none; border-radius: 3px; padding: 2px 6px;")
        arch_row.addWidget(arch_title)
        arch_row.addStretch()
        arch_row.addWidget(arch_badge)
        btn_arch_layout.addLayout(arch_row)

        arch_desc = QLabel("Sélectionnez directement votre archive téléchargée (.zip, .rar ou .7z).")
        arch_desc.setStyleSheet("font-size: 11px; color: #a1a1aa; background: transparent; border: none;")
        btn_arch_layout.addWidget(arch_desc)
        btn_archive.clicked.connect(lambda: (self.accept(), on_open_archive and on_open_archive()))
        layout.addWidget(btn_archive)

        btn_folder = QPushButton()
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.setStyleSheet("QPushButton { background-color: #242428; border: none; border-radius: 6px; padding: 12px; text-align: left; } QPushButton:hover { background-color: #2c2c32; }")
        btn_fold_layout = QVBoxLayout(btn_folder)
        btn_fold_layout.setContentsMargins(4, 2, 4, 2)
        btn_fold_layout.setSpacing(4)

        fold_row = QHBoxLayout()
        fold_title = QLabel("📂 Parcourir un dossier décompressé")
        fold_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8; background: transparent; border: none;")
        fold_badge = QLabel("Dossier local")
        fold_badge.setStyleSheet("font-size: 10px; color: #71717a; padding: 2px 4px; background: transparent; border: none;")
        fold_row.addWidget(fold_title)
        fold_row.addStretch()
        fold_row.addWidget(fold_badge)
        btn_fold_layout.addLayout(fold_row)

        fold_desc = QLabel("Sélectionnez directement votre dossier local contenant les fichiers du mod.")
        fold_desc.setStyleSheet("font-size: 11px; color: #a1a1aa; background: transparent; border: none;")
        btn_fold_layout.addWidget(fold_desc)
        btn_folder.clicked.connect(lambda: (self.accept(), on_open_folder and on_open_folder()))
        layout.addWidget(btn_folder)

        layout.addSpacing(6)
        sec2_lbl = QLabel("MODS DE DÉMONSTRATION RÉALISTES INTÉGRÉS")
        sec2_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #71717a; background: transparent; border: none;")
        layout.addWidget(sec2_lbl)

        btn_cbbe = QPushButton()
        btn_cbbe.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cbbe.setStyleSheet("QPushButton { background-color: #242428; border: none; border-radius: 6px; padding: 10px 12px; text-align: left; } QPushButton:hover { background-color: #2c2c32; }")
        cbbe_layout = QHBoxLayout(btn_cbbe)
        cbbe_layout.setContentsMargins(4, 2, 4, 2)
        cbbe_title = QLabel("CBBE - Caliente's Beautiful Bodies Enhancer SE")
        cbbe_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #ffffff; background: transparent; border: none;")
        cbbe_tag = QLabel("Charger →")
        cbbe_tag.setStyleSheet("font-size: 11px; color: #4ade80; font-weight: bold; background: transparent; border: none;")
        cbbe_layout.addWidget(cbbe_title)
        cbbe_layout.addStretch()
        cbbe_layout.addWidget(cbbe_tag)
        btn_cbbe.clicked.connect(lambda: (self.accept(), on_load_sample and on_load_sample("cbbe")))
        layout.addWidget(btn_cbbe)

        layout.addStretch()


class StagingResultModal(QDialog):
    """Modale de résultat de staging."""

    def __init__(self, result: StagingResult, staging_dir_path: str="Bureau (Desktop)", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Staging généré avec succès")
        self.setMinimumSize(780, 560)
        self.resize(860, 620)
        self.setStyleSheet("QDialog { background-color: #1a1a1d; color: #ffffff; border: 1px solid #2a2a2e; border-radius: 8px; }")
        self.result = result
        self.staging_dir_path = staging_dir_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        icon_lbl = QLabel("✓")
        icon_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #0ea5e9; background: transparent; border: none;")
        title_lbl = QLabel("Staging généré avec succès !")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #888888; font-size: 16px; } QPushButton:hover { color: #ffffff; }")
        close_btn.clicked.connect(self.accept)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        sub_info = QLabel(
            f"<b>{result.copied_count}</b> fichiers préparés &bull; "
            f"Taille totale : <b>{format_bytes(result.total_size)}</b> &bull; "
            f"Destination : <span style='color:#38bdf8;'>{staging_dir_path}</span>"
        )
        sub_info.setStyleSheet("font-size: 12px; color: #aaaaaa; background: transparent; border: none;")
        layout.addWidget(sub_info)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background-color: #161618; border-radius: 6px; }
            QTabBar::tab { background-color: #202024; color: #a1a1aa; padding: 6px 16px; margin-right: 4px; border-top-left-radius: 4px; border-top-right-radius: 4px; border: none; }
            QTabBar::tab:selected { background-color: #161618; color: #38bdf8; font-weight: bold; border: none; }
        """)

        tab_files = QWidget()
        tab_layout = QVBoxLayout(tab_files)
        tab_layout.setContentsMargins(8, 8, 8, 8)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Destination dans Data", "Taille", "Source Option"])
        tree.setStyleSheet("QTreeWidget { background-color: #161618; border: none; color: #f1f1f1; font-family: 'Menlo', monospace; font-size: 12px; } QHeaderView::section { background-color: #202024; color: #a1a1aa; padding: 6px 8px; border: none; border-bottom: 1px solid #27272a; font-weight: bold; font-size: 11px; }")
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        for item in result.items:
            leaf = QTreeWidgetItem([item.destination_path, format_bytes(item.size), item.matched_from_option])
            tree.addTopLevelItem(leaf)

        tab_layout.addWidget(tree)
        tabs.addTab(tab_files, "Fichiers installés")

        tab_log = QWidget()
        log_layout = QVBoxLayout(tab_log)
        log_edit = QTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setStyleSheet("background-color: #161618; border: none; color: #aaaaaa; font-family: 'Menlo', monospace; font-size: 11px;")
        log_edit.setText("\n".join(result.log) if result.log else "Aucun avertissement. Installation propre.")
        log_layout.addWidget(log_edit)
        tabs.addTab(tab_log, "Journal de staging")

        layout.addWidget(tabs)

        btn_bar = QHBoxLayout()
        export_zip_btn = QPushButton("📦 Exporter en archive ZIP")
        export_zip_btn.setStyleSheet("QPushButton { background-color: #2c2c32; border: none; color: #ffffff; font-size: 12px; font-weight: 600; padding: 8px 16px; border-radius: 5px; } QPushButton:hover { background-color: #383842; }")
        export_zip_btn.clicked.connect(self._export_zip)
        btn_bar.addWidget(export_zip_btn)

        btn_bar.addStretch()

        close_dialog_btn = QPushButton("Fermer")
        close_dialog_btn.setStyleSheet("QPushButton { background-color: #0ea5e9; color: #ffffff; font-weight: bold; font-size: 12px; padding: 8px 20px; border-radius: 5px; border: none; } QPushButton:hover { background-color: #0284c7; }")
        close_dialog_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_dialog_btn)

        layout.addLayout(btn_bar)

    def _export_zip(self):
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le mod ZIP", "Staging_Skyrim_Mod.zip", "Archive ZIP (*.zip)")
        if path:
            export_staging_to_zip(self.result, path)


class ModInfoDialog(QDialog):
    """Informations sur le mod (info.xml)."""

    def __init__(self, metadata: FomodMetadata, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Informations - {metadata.name}")
        self.setMinimumSize(520, 380)
        self.resize(560, 420)
        self.setStyleSheet("QDialog { background-color: #1a1a1d; color: #ffffff; border: 1px solid #2a2a2e; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title_lbl = QLabel(metadata.name)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #fbbf24; background: transparent; border: none;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        author_row = QHBoxLayout()
        auth_lbl = QLabel(f"<b>Auteur :</b> {metadata.author or 'Inconnu'}")
        auth_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent; border: none;")
        author_row.addWidget(auth_lbl)

        ver_lbl = QLabel(f"<b>Version :</b> {metadata.version or '1.0'}")
        ver_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; background: transparent; border: none;")
        author_row.addWidget(ver_lbl)
        author_row.addStretch()
        layout.addLayout(author_row)

        desc_box = QTextEdit()
        desc_box.setReadOnly(True)
        desc_box.setStyleSheet("background-color: #161618; border: none; color: #e4e4e7; font-size: 12px; padding: 10px; border-radius: 6px;")
        desc_box.setText(metadata.description or "(Aucune description disponible)")
        layout.addWidget(desc_box)

        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("QPushButton { background-color: #2c2c32; color: #ffffff; padding: 6px 18px; border-radius: 5px; border: none; } QPushButton:hover { background-color: #383842; }")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


class DataDirModal(QDialog):
    """Choisir le dossier Data de Skyrim."""

    def __init__(self, current_data_path: Optional[str], installed_plugins: Set[str], on_apply, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dossier Data de Skyrim")
        self.setMinimumSize(540, 400)
        self.resize(580, 420)
        self.setStyleSheet("QDialog { background-color: #1a1a1d; color: #ffffff; border: 1px solid #2a2a2e; border-radius: 8px; }")

        self.data_path = current_data_path or ""
        self.plugins = set(installed_plugins)
        self.on_apply = on_apply

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title_lbl = QLabel("📂  Dossier Data de Skyrim (Détection automatique)")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        path_box = QFrame()
        path_box.setStyleSheet("background-color: #161618; border: none; border-radius: 6px; padding: 8px;")
        path_layout = QVBoxLayout(path_box)
        path_layout.setContentsMargins(4, 2, 4, 2)
        self.path_val_lbl = QLabel(self.data_path or "(Aucun dossier sélectionné)")
        self.path_val_lbl.setStyleSheet("font-size: 12px; font-family: 'Menlo', monospace; color: #38bdf8; background: transparent; border: none;")
        path_layout.addWidget(self.path_val_lbl)
        layout.addWidget(path_box)

        btn_row = QHBoxLayout()
        pick_btn = QPushButton("📁 Parcourir le disque...")
        pick_btn.setStyleSheet("QPushButton { background-color: #2c2c32; border: none; color: #ffffff; font-size: 12px; padding: 6px 14px; border-radius: 5px; } QPushButton:hover { background-color: #383842; }")
        pick_btn.clicked.connect(self._pick_folder)
        btn_row.addWidget(pick_btn)

        sim_btn = QPushButton("⚡ Simuler plugins Skyrim (CBPC, SkyUI, skee64)")
        sim_btn.setStyleSheet("QPushButton { background-color: #0284c7; border: none; color: #ffffff; font-size: 12px; font-weight: bold; padding: 6px 14px; border-radius: 5px; } QPushButton:hover { background-color: #0ea5e9; }")
        sim_btn.clicked.connect(self._sim_plugins)
        btn_row.addWidget(sim_btn)
        layout.addLayout(btn_row)

        self.detected_lbl = QLabel("Plugins et DLLs détectés :")
        self.detected_lbl.setStyleSheet("font-size: 12px; color: #a1a1aa; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self.detected_lbl)

        self.plugins_text = QTextEdit()
        self.plugins_text.setReadOnly(True)
        self.plugins_text.setStyleSheet("background-color: #161618; border: none; color: #cccccc; font-family: 'Menlo', monospace; font-size: 11px; padding: 6px; border-radius: 5px;")
        self._update_display()
        layout.addWidget(self.plugins_text)

        close_btn = QPushButton("Valider & Fermer")
        close_btn.setStyleSheet("QPushButton { background-color: #0ea5e9; color: #ffffff; font-weight: bold; font-size: 12px; padding: 8px 20px; border-radius: 5px; border: none; } QPushButton:hover { background-color: #0284c7; }")
        close_btn.clicked.connect(self._apply)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier Skyrim Data")
        if folder:
            self.data_path = folder
            self.path_val_lbl.setText(folder)
            found = set()
            try:
                for _, _, files in os.walk(folder):
                    for f in files:
                        lower = f.lower()
                        if lower.endswith((".esp", ".esm", ".esl", ".dll", ".bsa", ".ba2")):
                            found.add(lower)
            except Exception as e:
                logger.error(f"Erreur scan dossier Data: {e}")
            self.plugins = found
            self._update_display()

    def _sim_plugins(self):
        self.data_path = "C:/Program Files/Steam/steamapps/common/Skyrim Special Edition/Data"
        self.path_val_lbl.setText(self.data_path)
        self.plugins = {
            "skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm", "dragonborn.esm",
            "skyui_se.esp", "cbpc.dll", "skee64.dll", "hdtsmp64.dll", "lanterns of skyrim ii.esm",
            "jks skyrim.esp", "elfx - exteriors.esp", "windhelm_braziers.esp", "gourmettables.esp",
        }
        self._update_display()

    def _update_display(self):
        plugins_list = sorted([p for p in self.plugins if p.endswith((".esp", ".esm", ".esl", ".dll", ".bsa", ".ba2"))])
        self.detected_lbl.setText(f"Plugins et DLLs détectés ({len(plugins_list)}) :")
        if plugins_list:
            self.plugins_text.setText("\n".join(plugins_list))
        else:
            self.plugins_text.setText("(Aucun plugin détecté)")

    def _apply(self):
        if self.on_apply:
            self.on_apply(self.data_path, self.plugins)
        self.accept()


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
        self.setStyleSheet("QDialog { background-color: #121214; border: 1px solid #27272a; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #121214;
                border: none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: transparent;
                width: 6px;
                height: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background-color: #2c2c32;
                border-radius: 3px;
            }
            QScrollBar::handle:hover {
                background-color: #383842;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: #121214; border: none;")
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
        res_info.setStyleSheet("color: #888888; font-size: 11px; background: transparent; border: none;")
        bottom_bar.addWidget(res_info)

        bottom_bar.addStretch()

        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c2c32;
                color: #ffffff;
                padding: 6px 18px;
                border-radius: 5px;
                border: none;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383842;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

# ==============================================================================
# 8. FENÊTRE PRINCIPALE DU SIMULATEUR FOMOD
# ==============================================================================


DARK_THEME_QSS = """
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
    border: none;
    border-radius: 8px;
}

/* Règle fondamentale : aucun contour ni fond par défaut sur les QLabel */
QLabel {
    background: transparent;
    border: none;
}

QFrame {
    border: none;
}

/* En-tête supérieur épuré sans contour */
QFrame#HeaderBar {
    background-color: #202024;
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
    background-color: #18181b;
    border: none;
    border-radius: 6px;
}

QFrame#OptionRow {
    background-color: transparent;
    border: none;
    border-radius: 5px;
}

/* Séparateur (Splitter) discret */
QSplitter::handle {
    background-color: #18181b;
}
QSplitter::handle:horizontal {
    width: 6px;
}
QSplitter::handle:horizontal:hover {
    background-color: rgba(14, 165, 233, 0.4);
}

/* Boutons */
QPushButton {
    background-color: #2a2a2e;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #35353b;
}
QPushButton:pressed {
    background-color: #202024;
}
QPushButton:disabled {
    background-color: #222225;
    color: #55555c;
    border: none;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background-color: #323238;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background-color: #45454e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background-color: #323238;
    min-width: 20px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #45454e;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

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
    background-color: #27272e;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #1e1e22;
    color: #a1a1aa;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #27272a;
    font-size: 11px;
    font-weight: bold;
}

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


def check_option_matches_installed_dependency(
    opt: FomodOption,
    installed_basenames: Set[str],
    active_flags: Optional[Dict[str, str]]=None,
) -> bool:
    """Vérifie si une option correspond à un mod / fichier présent dans Data."""
    if not installed_basenames:
        return False

    if is_option_recommended(opt, active_flags or {}, installed_basenames):
        return True

    if opt.dependencies and opt.dependencies.file_dependencies:
        for fd in opt.dependencies.file_dependencies:
            b = fd.file.replace("\\", "/").split("/")[-1].strip().lower()
            if b in installed_basenames:
                return True

    for f in opt.files:
        b = f.source.replace("\\", "/").split("/")[-1].strip().lower()
        if b.endswith((".esp", ".esm", ".esl")):
            for inst in installed_basenames:
                if len(inst) > 4 and (inst in b or b in inst):
                    return True

    return False


class MainWindow(QMainWindow):
    """Fenêtre principale du Simulateur FOMOD en PyQt6 avec fidélité visuelle stricte."""

    def __init__(self):
        super().__init__()
        self.i18n = get_i18n()
        app = QApplication.instance()
        if app and sys.platform == "darwin":
            app.setFont(QFont(".AppleSystemUIFont", 13))
        self.setWindowTitle(self.i18n.get("header", "title", default="Simulateur d'Installateur FOMOD"))
        self.resize(1340, 840)
        self.setMinimumSize(1000, 680)

        # État interne
        self.archive_index: ArchiveIndex = ArchiveIndex()
        self.metadata: FomodMetadata = FomodMetadata(
            name="Simulateur d'Installateur FOMOD",
            author="",
            version="1.0.0",
            website="",
            description="",
        )
        self.steps: List[FomodStep] = []
        self.required_files = []
        self.current_step_idx = 0
        self.selected_option_ids: Set[str] = set()
        self.active_flags: Dict[str, str] = {}
        self.active_preview_option: Optional[FomodOption] = None
        self.current_staging_result: Optional[StagingResult] = None
        self.installed_basenames: Set[str] = set()
        self.conditional_installs: List[ConditionalInstallPattern] = []

        # Chemins de staging et data
        self.data_dir_path: Optional[str] = None
        self.staging_dir_path: str = "Bureau (Desktop)"

        # Tree widget invisible maintenu pour rétro-compatibilité
        self.staging_tree = QTreeWidget()
        self.staging_tree.setHeaderLabels(["Destination dans Data", "Taille", "Source Option"])

        # Workers d'arrière-plan
        self._extract_worker: Optional[ArchiveExtractWorker] = None
        self._staging_worker: Optional[StagingWorker] = None

        self._init_ui()

    def resizeEvent(self, event):
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
        central.setStyleSheet("QWidget#RootWidget { background-color: #18181b; }")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. En-tête supérieur persistant
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
                background-color: #202020;
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
        lang_divider.setStyleSheet("background-color: #2e2e2e; max-height: 1px; border: none; margin-bottom: 2px;")
        card_layout.addWidget(lang_divider)

        # Badge circulaire avec icône 📦
        badge = QFrame()
        badge.setObjectName("WelcomeBadge")
        badge.setFixedSize(64, 64)
        badge.setStyleSheet("""
            QFrame#WelcomeBadge {
                background-color: #262626;
                border: 1px solid #3d3d3d;
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
        self.welcome_sub_lbl.setStyleSheet("font-size: 12px; color: #999999; border: none; line-height: 1.5; background: transparent;")
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
                background-color: #1f2428;
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
        self.welcome_drop_txt.setStyleSheet("font-size: 14px; font-weight: 600; color: #f1f1f1; border: none; background: transparent;")
        self.welcome_drop_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.welcome_drop_txt)

        self.welcome_fmt_txt = QLabel(self.i18n.get("welcome", "supportedFormats"))
        self.welcome_fmt_txt.setTextFormat(Qt.TextFormat.RichText)
        self.welcome_fmt_txt.setStyleSheet("font-size: 11px; color: #777777; border: none; background: transparent;")
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
        self.welcome_btn_folder.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none; text-decoration: underline;")
        self.welcome_btn_folder.clicked.connect(self._pick_folder_mod)
        sub_actions.addWidget(self.welcome_btn_folder)

        sep = QLabel("•")
        sep.setStyleSheet("color: #555555; border: none; background: transparent;")
        sub_actions.addWidget(sep)

        self.welcome_btn_demo = QPushButton("🧪  " + self.i18n.get("welcome", "loadDemoBtn"))
        self.welcome_btn_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_btn_demo.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none; text-decoration: underline;")
        self.welcome_btn_demo.clicked.connect(self.load_demo_mod)
        sub_actions.addWidget(self.welcome_btn_demo)

        card_layout.addLayout(sub_actions)

        # Ligne de séparation et pied de carte
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #2e2e2e; max-height: 1px; border: none; margin-top: 10px;")
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
                        border: 1px solid #38bdf8;
                        padding: 0 9px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #18181a;
                        color: #a1a1aa;
                        font-weight: 500;
                        font-size: 11px;
                        border-radius: 5px;
                        border: 1px solid #303036;
                        padding: 0 9px;
                    }
                    QPushButton:hover {
                        background-color: #27272a;
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
                f'<span style="font-weight:600; color:#dddddd;">{data_lbl}</span> <span style="color:#bbbbbb;">{os.path.basename(self.data_dir_path)}</span><br/><span style="color:#38bdf8; font-size:10px;">({count} {files_lbl})</span>'
            )
        else:
            not_set = i18n.get("common", "notSet", default="(non défini)") if i18n else "(non défini)"
            self.data_status_label.setText(
                f'<span style="font-weight:600; color:#dddddd;">{data_lbl}</span> <span style="font-style:italic; color:#bbbbbb;">{not_set}</span><br/><span style="color:#888888; font-size:10px;">{click_lbl}</span>'
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
            is_last = (total > 0 and self.current_step_idx == total - 1)
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
            total_steps = len(self.steps)
            step_num = self.current_step_idx + 1 if total_steps > 0 else 0
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
            self.title_label.setText(i18n.get("header", "title", default="Simulateur d'Installateur FOMOD") if i18n else "Simulateur d'Installateur FOMOD")
            self.btn_close.hide()
            self.pipe1.hide()
            self.step_counter_label.hide()
            self.pipe2.hide()
            self.env_badge_label.setText(i18n.get("header", "waitingArchive", default="Skyrim SE/AE • En attente d'archive") if i18n else "Skyrim SE/AE • En attente d'archive")
            self.env_badge_label.show()

    def _close_mod(self):
        self.cleanup_workers()
        self.steps.clear()
        default_name = self.i18n.get("header", "title", default="Simulateur d'Installateur FOMOD") if hasattr(self, "i18n") else "Simulateur d'Installateur FOMOD"
        self.metadata = FomodMetadata(name=default_name)
        self.selected_option_ids.clear()
        self.active_flags.clear()
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
                background-color: #2b2b2b;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #383838; color: #ffffff; }
        """)
        self.btn_close.clicked.connect(self._close_mod)
        right_box.addWidget(self.btn_close)

        self.pipe1 = QLabel("|")
        self.pipe1.setStyleSheet("color: #555555; background: transparent; border: none;")
        right_box.addWidget(self.pipe1)

        self.step_counter_label = QLabel("Étape 1 / 5")
        self.step_counter_label.setStyleSheet("color: #888888; font-family: 'Menlo', monospace; font-size: 11px; background: transparent; border: none;")
        right_box.addWidget(self.step_counter_label)

        self.pipe2 = QLabel("|")
        self.pipe2.setStyleSheet("color: #555555; background: transparent; border: none;")
        right_box.addWidget(self.pipe2)

        self.env_badge_label = QLabel(self.i18n.get("header", "waitingArchive"))
        self.env_badge_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent; border: none;")
        right_box.addWidget(self.env_badge_label)

        self.pipe3 = QLabel("|")
        self.pipe3.setStyleSheet("color: #555555; background: transparent; border: none;")
        right_box.addWidget(self.pipe3)

        # Menu déroulant de changement de langue
        self.header_lang_combo = QComboBox()
        self.header_lang_combo.setFixedHeight(24)
        self.header_lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for code, label, flag in AVAILABLE_LANGUAGES:
            self.header_lang_combo.addItem(f"{flag} {label}", code)
        self.header_lang_combo.setStyleSheet("""
            QComboBox {
                background-color: #202024;
                color: #f1f1f1;
                border: 1px solid #383840;
                border-radius: 4px;
                padding: 0 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #0ea5e9;
                background-color: #28282e;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e24;
                color: #e4e4e7;
                selection-background-color: #0ea5e9;
                selection-color: #ffffff;
                border: 1px solid #383840;
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
        col.setStyleSheet("QFrame#LeftColFrame { background-color: #202023; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top_box = QVBoxLayout()
        top_box.setSpacing(8)

        self.btn_open_fomod = QPushButton("📦  Ouvrir un FOMOD")
        self.btn_open_fomod.setFixedHeight(46)
        self.btn_open_fomod.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_fomod.setStyleSheet("""
            QPushButton {
                background-color: #fbbf24;
                color: #18181b;
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

        self.btn_mod_info = QPushButton("ℹ️  Infos du mod")
        self.btn_mod_info.setFixedHeight(34)
        self.btn_mod_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mod_info.setStyleSheet("""
            QPushButton {
                background-color: #2c2c32;
                color: #dddddd;
                font-size: 12px;
                font-weight: 500;
                border-radius: 5px;
                border: none;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #383840; color: #ffffff; }
        """)
        self.btn_mod_info.clicked.connect(self._show_mod_info_dialog)
        top_box.addWidget(self.btn_mod_info)

        self.btn_choose_data = QPushButton("📁  Choisir le dossier Data")
        self.btn_choose_data.setFixedHeight(34)
        self.btn_choose_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_data.setStyleSheet("""
            QPushButton {
                background-color: #2c2c32;
                color: #dddddd;
                font-size: 12px;
                font-weight: 500;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #383840; color: #ffffff; }
        """)
        self.btn_choose_data.clicked.connect(self._open_data_dir_modal)
        top_box.addWidget(self.btn_choose_data)

        self.data_status_label = QLabel()
        self.data_status_label.setTextFormat(Qt.TextFormat.RichText)
        self.data_status_label.setText(
            '<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="font-style:italic; color:#bbbbbb;">(non défini)</span><br/><span style="color:#888888; font-size:10px;">(Cliquez pour simuler Skyrim)</span>'
        )
        self.data_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data_status_label.setStyleSheet("font-size: 11px; line-height: 1.3; background: transparent; border: none;")
        top_box.addWidget(self.data_status_label)

        layout.addLayout(top_box)
        layout.addStretch()

        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(8)

        self.btn_choose_dest = QPushButton("📁  Choisir le dossier")
        self.btn_choose_dest.setFixedHeight(34)
        self.btn_choose_dest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_dest.setStyleSheet("""
            QPushButton {
                background-color: #2c2c32;
                color: #dddddd;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #383840; color: #ffffff; }
        """)
        self.btn_choose_dest.clicked.connect(self._pick_staging_destination)
        bottom_box.addWidget(self.btn_choose_dest)

        dest_card = QFrame()
        dest_card.setStyleSheet("background-color: #161618; border: none; border-radius: 5px; padding: 6px;")
        dest_layout = QVBoxLayout(dest_card)
        dest_layout.setContentsMargins(4, 2, 4, 2)
        dest_layout.setSpacing(2)

        self.dest_hdr = QLabel(self.i18n.get("common", "destination", default="Destination :"))
        self.dest_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dest_hdr.setStyleSheet("color: #888888; font-size: 10px; background: transparent; border: none;")
        dest_layout.addWidget(self.dest_hdr)

        self.dest_path_label = QLabel(self.staging_dir_path)
        self.dest_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dest_path_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500; font-family: 'Menlo', monospace; background: transparent; border: none;")
        dest_layout.addWidget(self.dest_path_label)
        bottom_box.addWidget(dest_card)

        self.btn_generate_staging = QPushButton("GÉNÉRER LE STAGING")
        self.btn_generate_staging.setFixedHeight(40)
        self.btn_generate_staging.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate_staging.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
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

    def _create_center_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("CenterColFrame")
        col.setStyleSheet("QFrame#CenterColFrame { background-color: #202023; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        step_header = QFrame()
        step_header.setObjectName("StepHeader")
        step_header.setStyleSheet("QFrame#StepHeader { border-bottom: 1px solid #27272c; background-color: transparent; }")
        step_header_layout = QHBoxLayout(step_header)
        step_header_layout.setContentsMargins(14, 12, 14, 12)

        self.step_title_label = QLabel("Silhouette & Version du corps")
        self.step_title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff; border: none; background: transparent;")
        step_header_layout.addWidget(self.step_title_label)

        step_header_layout.addStretch()

        self.step_index_label = QLabel("1 / 5")
        self.step_index_label.setStyleSheet("color: #a1a1aa; font-family: 'Menlo', monospace; font-size: 11px; border: none; background: transparent;")
        step_header_layout.addWidget(self.step_index_label)
        layout.addWidget(step_header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_area.viewport().setStyleSheet("background-color: #202023; border: none;")
        self.groups_widget = QWidget()
        self.groups_widget.setStyleSheet("background-color: #202023; border: none;")
        self.groups_layout = QVBoxLayout(self.groups_widget)
        self.groups_layout.setContentsMargins(12, 12, 12, 12)
        self.groups_layout.setSpacing(10)
        self.scroll_area.setWidget(self.groups_widget)
        layout.addWidget(self.scroll_area, 1)

        nav_bar = QFrame()
        nav_bar.setObjectName("NavBar")
        nav_bar.setStyleSheet("QFrame#NavBar { border-top: 1px solid #27272c; background-color: #202023; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; }")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(12, 12, 12, 12)
        nav_layout.setSpacing(10)

        self.btn_prev = QPushButton("RETOUR")
        self.btn_prev.setFixedHeight(38)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #2c2c32;
                color: #dddddd;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.5px;
                border-radius: 5px;
                border: none;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #383840; }
            QPushButton:disabled {
                background-color: #1e1e22;
                color: #52525b;
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
                background-color: #0284c7;
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

    def _create_right_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("RightColFrame")
        col.setStyleSheet("QFrame#RightColFrame { background-color: #202023; border: none; border-radius: 6px; }")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.right_sec_title = QLabel("📖  " + self.i18n.get("preview", "instructionsTitle", default="INSTRUCTIONS & DESCRIPTION").upper())
        self.right_sec_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; letter-spacing: 0.5px; background: transparent; border: none;")
        layout.addWidget(self.right_sec_title)

        self.preview_desc_label = QLabel("Description de l'option...")
        self.preview_desc_label.setWordWrap(True)
        self.preview_desc_label.setStyleSheet("color: #f4f4f5; font-size: 13px; line-height: 1.5; border: none; background: transparent;")
        layout.addWidget(self.preview_desc_label)

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

        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_image_label.setToolTip("Cliquer pour afficher dans sa taille réelle")
        self.preview_image_label.mousePressEvent = lambda _e: self._open_image_preview_modal()
        preview_img_frame.mousePressEvent = lambda _e: self._open_image_preview_modal()
        img_layout.addWidget(self.preview_image_label)

        layout.addWidget(preview_img_frame)
        layout.addStretch()
        return col

    def auto_select_options_for_environment(self, preserve_manual: bool=False):
        """Scanne intelligemment les options et coche les patches/options recommandées."""
        if not self.steps:
            return

        if not preserve_manual:
            self.selected_option_ids.clear()
            self.active_flags.clear()

            for step in self.steps:
                for grp in step.groups:
                    is_single = grp.type in (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)
                    if is_single:
                        chosen = None
                        for opt in grp.options:
                            if is_option_recommended(opt, self.active_flags, self.installed_basenames):
                                chosen = opt
                                break
                        if not chosen:
                            for opt in grp.options:
                                if opt.is_default:
                                    chosen = opt
                                    break
                        if not chosen and grp.type == GroupType.SelectExactlyOne and grp.options:
                            chosen = grp.options[0]
                        if chosen:
                            self.selected_option_ids.add(chosen.id)
                            for k, v in chosen.flags.items():
                                self.active_flags[k] = v
                    else:
                        for opt in grp.options:
                            if is_option_recommended(opt, self.active_flags, self.installed_basenames):
                                self.selected_option_ids.add(opt.id)
                                for k, v in opt.flags.items():
                                    self.active_flags[k] = v
                            elif check_option_matches_installed_dependency(opt, self.installed_basenames, self.active_flags):
                                self.selected_option_ids.add(opt.id)
                                for k, v in opt.flags.items():
                                    self.active_flags[k] = v
                            elif opt.is_default:
                                self.selected_option_ids.add(opt.id)
                                for k, v in opt.flags.items():
                                    self.active_flags[k] = v
        else:
            for step in self.steps:
                for grp in step.groups:
                    is_single = grp.type in (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)
                    if is_single:
                        has_matching_dep = None
                        for opt in grp.options:
                            if check_option_matches_installed_dependency(opt, self.installed_basenames, self.active_flags):
                                has_matching_dep = opt
                                break
                        if has_matching_dep:
                            for opt in grp.options:
                                self.selected_option_ids.discard(opt.id)
                            self.selected_option_ids.add(has_matching_dep.id)
                            for k, v in has_matching_dep.flags.items():
                                self.active_flags[k] = v
                    else:
                        for opt in grp.options:
                            if check_option_matches_installed_dependency(opt, self.installed_basenames, self.active_flags):
                                self.selected_option_ids.add(opt.id)
                                for k, v in opt.flags.items():
                                    self.active_flags[k] = v

    def load_demo_mod(self, _mod_id: str="cbbe"):
        logger.info("Chargement du mod démo : %s", _mod_id)
        try:
            index, cfg_xml, info_xml = get_demo_mod()
            self.archive_index = index
            self.metadata = parse_info_xml(info_xml)
            mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)

            if mod_name:
                self.metadata.name = mod_name
            self.steps = steps
            self.required_files = req_files
            self.conditional_installs = cond_installs
            self.current_step_idx = 0
            self.auto_select_options_for_environment(preserve_manual=False)

            self._render_current_step()
            self._trigger_background_staging()
            self.central_stack.setCurrentIndex(1)
            self._update_header()
        except Exception as e:
            logger.error(f"Erreur chargement mod démo : {e}")

    def _render_current_step(self):
        """Affiche les options de l'étape courante dans la colonne centrale."""
        total_steps = len(self.steps)
        step_num = self.current_step_idx + 1 if total_steps > 0 else 0

        self.step_counter_label.setText(
            self.i18n.get("header", "stepCounter", default="Étape {current} / {total}").format(
                current=step_num, total=total_steps
            )
        )
        self.step_index_label.setText(f"{step_num} / {total_steps}")

        # Activation / Désactivation des boutons Précédent & Suivant
        self.btn_prev.setEnabled(self.current_step_idx > 0)
        self.btn_next.setEnabled(self.current_step_idx < total_steps - 1)
        self.btn_prev.setText(self.i18n.get("steps", "prevStep", default="← RETOUR"))
        self.btn_next.setText(
            self.i18n.get("steps", "finishStep", default="TERMINER")
            if self.current_step_idx == total_steps - 1
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
            grp_box.setStyleSheet("QFrame#GroupCard { background-color: #1a1a1d; border: none; border-radius: 6px; }")
            grp_layout = QVBoxLayout(grp_box)
            grp_layout.setContentsMargins(12, 10, 12, 10)
            grp_layout.setSpacing(6)

            # En-tête du groupe
            grp_hdr = QHBoxLayout()
            grp_name = QLabel(grp.name)
            grp_name.setStyleSheet("font-size: 12px; font-weight: bold; color: #e4e4e7; border: none; background: transparent;")
            grp_hdr.addWidget(grp_name)
            grp_hdr.addStretch()

            is_single = grp.type in (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)
            choice_lbl = self.i18n.get("common", "singleChoice") if is_single else self.i18n.get("common", "multipleChoice")
            grp_type_lbl = QLabel(choice_lbl)
            grp_type_lbl.setStyleSheet("font-size: 10px; color: #a1a1aa; border: none; background: transparent;")
            grp_hdr.addWidget(grp_type_lbl)
            grp_layout.addLayout(grp_hdr)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("background-color: #26262a; max-height: 1px; border: none; margin-bottom: 2px;")
            grp_layout.addWidget(div)

            # Options du groupe
            for opt in grp.options:
                if first_option is None:
                    first_option = opt

                is_sel = opt.id in self.selected_option_ids
                matches_dep = check_option_matches_installed_dependency(
                    opt, self.installed_basenames, self.active_flags
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

    def _on_hover_option(self, option: FomodOption):
        self.active_preview_option = option
        self.preview_desc_label.setText(option.description or "(Aucune description disponible pour cette option)")

        pixmap = get_preview_pixmap_for_path(
            option.image_path,
            option.name,
            option.description,
            self.archive_index,
        )
        scaled = pixmap.scaled(
            540, 338,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_image_label.setPixmap(scaled)
        self.preview_image_label.setFixedSize(scaled.width(), scaled.height())

    def _on_select_option(self, option: FomodOption, group: FomodGroup):
        is_single = group.type in (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)

        if is_single:
            for opt in group.options:
                self.selected_option_ids.discard(opt.id)
            self.selected_option_ids.add(option.id)
        else:
            if option.id in self.selected_option_ids:
                self.selected_option_ids.remove(option.id)
            else:
                self.selected_option_ids.add(option.id)

        self.active_flags.clear()
        for step in self.steps:
            for grp in step.groups:
                for opt in grp.options:
                    if opt.id in self.selected_option_ids:
                        for k, v in opt.flags.items():
                            self.active_flags[k] = v

        self._render_current_step()
        self._on_hover_option(option)
        self._trigger_background_staging()

    def _next_step(self):
        if self.current_step_idx < len(self.steps) - 1:
            self.current_step_idx += 1
            self._render_current_step()
        else:
            self._on_generate_staging()

    def _prev_step(self):
        if self.current_step_idx > 0:
            self.current_step_idx -= 1
            self._render_current_step()

    def _trigger_background_staging(self):
        selected_opts = []
        for step in self.steps:
            for grp in step.groups:
                for opt in grp.options:
                    if opt.id in self.selected_option_ids:
                        selected_opts.append(opt)

        if self._staging_worker and self._staging_worker.isRunning():
            try:
                self._staging_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._staging_worker.wait(1000)

        self._staging_worker = StagingWorker(
            selected_options=selected_opts,
            required_files=self.required_files,
            archive_index=self.archive_index,
            conditional_installs=self.conditional_installs,
            active_flags=self.active_flags,
            installed_basenames=self.installed_basenames,
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
        try:
            selected_opts = []
            for step in self.steps:
                for grp in step.groups:
                    for opt in grp.options:
                        if opt.id in self.selected_option_ids:
                            selected_opts.append(opt)

            res = build_staging(
                selected_opts,
                self.required_files,
                self.archive_index,
                self.conditional_installs,
                self.active_flags,
                self.installed_basenames,
            )
            self.current_staging_result = res

            if os.path.exists(self.staging_dir_path):
                try:
                    arch_path = self.archive_index.archive_path if self.archive_index else None
                    export_staging_to_directory(res, self.staging_dir_path, arch_path)
                except Exception as e:
                    logger.error(f"Erreur copie directe staging : {e}")

            modal = StagingResultModal(res, self.staging_dir_path, self)
            modal.exec()
        except Exception as e:
            logger.exception("Erreur génération staging")
            QMessageBox.critical(self, "Erreur Staging", f"Une erreur est survenue lors de la génération du staging :\n{e}")

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
                f'<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="color:#bbbbbb;">{os.path.basename(path)}</span><br/><span style="color:#38bdf8; font-size:10px;">({len(plugins)} fichiers détectés)</span>'
            )
        else:
            self.data_status_label.setText(
                '<span style="font-weight:600; color:#dddddd;">Data :</span> <span style="font-style:italic; color:#bbbbbb;">(non défini)</span><br/><span style="color:#888888; font-size:10px;">(Cliquez pour simuler Skyrim)</span>'
            )
        if self.steps:
            self.auto_select_options_for_environment(preserve_manual=True)
            self._trigger_background_staging()
        self._render_current_step()

    def _pick_staging_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de destination du Staging")
        if folder:
            self.staging_dir_path = folder
            self.dest_path_label.setText(folder)

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
                        if entry.extracted_disk_path and os.path.exists(entry.extracted_disk_path):
                            with open(entry.extracted_disk_path, "r", encoding="utf-8", errors="ignore") as fh:
                                cfg_xml = fh.read()
                        break

            if not cfg_xml:
                QMessageBox.warning(
                    self,
                    "ModuleConfig.xml introuvable",
                    "L'archive a été décompressée mais aucun fichier 'fomod/ModuleConfig.xml' n'a été détecté.\n"
                    "Assurez-vous qu'il s'agit bien d'un mod au format FOMOD."
                )
                return

            mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)
            if not steps:
                QMessageBox.information(
                    self,
                    "Information FOMOD",
                    "Le fichier ModuleConfig.xml a été détecté mais aucune étape d'installation (installStep) n'a été trouvée."
                )

            self.archive_index = index
            self.metadata = parse_info_xml(info_xml) if info_xml else FomodMetadata(name="Mod FOMOD")
            if mod_name:
                self.metadata.name = mod_name
            self.steps = steps
            self.required_files = req_files
            self.conditional_installs = cond_installs
            self.current_step_idx = 0
            self.auto_select_options_for_environment(preserve_manual=False)

            self._render_current_step()
            self._trigger_background_staging()
            self.central_stack.setCurrentIndex(1)
            self._update_header()

        except Exception as e:
            self.loading_overlay.hide()
            logger.exception("Erreur lors de l'analyse du mod FOMOD")
            QMessageBox.critical(self, "Erreur de traitement", f"Impossible d'analyser le mod :\n{e}")

    def _open_image_preview_modal(self):
        if self.active_preview_option:
            pix = get_preview_pixmap_for_path(
                self.active_preview_option.image_path,
                self.active_preview_option.name,
                self.active_preview_option.description,
                self.archive_index,
            )
            modal = ImagePreviewModal(pix, self.active_preview_option.name, self)
            modal.exec()

    def cleanup_workers(self):
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

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)


def setup_logging():
    log_level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    setup_logging()
    logger.info("Démarrage du Simulateur FOMOD v1.0 (PyQt6)")

    app = QApplication(sys.argv)
    if sys.platform == "darwin":
        app.setFont(QFont(".AppleSystemUIFont", 13))
    app.setStyle("Fusion")
    app.setApplicationName("FOMOD Simulator")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SkyrimTools")
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()

    if len(sys.argv) > 1:
        target_path = sys.argv[1]
        if os.path.exists(target_path):
            logger.info(f"Ouverture directe via CLI : {target_path}")
            window._load_archive(target_path)
        else:
            logger.warning(f"Fichier inexistant : {target_path}")

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
