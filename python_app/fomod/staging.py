import os
import re
import shutil
import zipfile
import logging
from typing import List, Dict, Tuple, Optional, Set
from .types import (
    ArchiveIndex,
    FomodOption,
    FomodFileItem,
    FomodFolderItem,
    StagingItem,
    StagingResult,
    ConditionalInstallPattern,
)
from .parser import norm, find_file_in_index, find_folder_in_index, evaluate_dependencies

logger = logging.getLogger(__name__)


def resolve_file_destination(raw_dst: str, src_path: str) -> str:
    """Calcule le chemin de destination normalisé pour un fichier extrait via FOMOD.
    Corrige spécifiquement le cas où destination="Plugin.esp" avec source="00 Core/Plugin.esp"."""
    clean_dst = norm(raw_dst).strip("/")
    file_name = src_path.split("/")[-1] if "/" in src_path else src_path

    if not clean_dst:
        return file_name

    clean_dst_lower = clean_dst.lower()
    file_name_lower = file_name.lower()

    # 1. Si la destination spécifiée se termine déjà par le nom du fichier
    if clean_dst_lower == file_name_lower or clean_dst_lower.endswith("/" + file_name_lower):
        return clean_dst

    # 2. Si la destination se termine par une extension de fichier explicite (.esp, .dds, .nif, etc.)
    if re.search(r"\.[a-zA-Z0-9_-]{2,6}$", clean_dst):
        return clean_dst

    # 3. Sinon c'est un répertoire cible
    return norm(f"{clean_dst}/{file_name}")


def build_staging(
    selected_options: List[FomodOption],
    required_files: List[FomodFileItem | FomodFolderItem],
    archive_index: ArchiveIndex,
    conditional_installs: Optional[List[ConditionalInstallPattern]] = None,
    active_flags: Optional[Dict[str, str]] = None,
    installed_basenames: Optional[Set[str]] = None,
) -> StagingResult:
    """Simule la copie et l'installation de tous les fichiers FOMOD sélectionnés,
    y compris les requiredInstallFiles et les conditionalFileInstalls."""
    log: List[str] = []
    items_map: Dict[str, StagingItem] = {}  # target_lower -> item
    copied = 0
    missing = 0
    total_size = 0

    c_flags = active_flags or {}
    c_basenames = installed_basenames or set()

    def process_node(tag: str, raw_src: str, raw_dst: str, opt_name: str, priority: int = 0):
        nonlocal copied, missing, total_size

        src = norm(raw_src)
        src_file = find_file_in_index(archive_index, src)
        src_dir = find_folder_in_index(archive_index, src)

        def copy_folder_files(dir_path: str) -> int:
            nonlocal copied, total_size
            sub_copied = 0
            dir_lower = dir_path.lower().rstrip("/")
            dir_lower_slash = dir_lower + "/"

            for key, entry in archive_index.files.items():
                if entry.is_dir or "__macosx" in key:
                    continue

                matched = False
                relative_inside = ""

                if key.startswith(dir_lower_slash):
                    matched = True
                    relative_inside = entry.path[len(dir_path):].lstrip("/")
                elif ("/" + dir_lower_slash) in key:
                    idx = key.find("/" + dir_lower_slash)
                    matched = True
                    matched_prefix_len = idx + 1 + len(dir_path)
                    relative_inside = entry.path[matched_prefix_len:].lstrip("/")

                if matched:
                    clean_dst = norm(raw_dst).strip("/")
                    if clean_dst:
                        target = norm(f"{clean_dst}/{relative_inside}") if relative_inside else clean_dst
                    else:
                        target = relative_inside or entry.path.split("/")[-1]

                    target_lower = target.lower()
                    existing = items_map.get(target_lower)
                    if existing is not None and priority < existing.priority:
                        # Priorité inférieure, ignorer
                        continue

                    sz = entry.size or (len(entry.data) if entry.data else 1024)
                    if existing is None:
                        copied += 1
                        total_size += sz
                    else:
                        total_size += sz - existing.size

                    sub_copied += 1
                    log.append(f"  [+ fichier] {entry.path} -> {target} (prio: {priority})")

                    items_map[target_lower] = StagingItem(
                        source_path=entry.path,
                        destination_path=target,
                        type="file",
                        size=sz,
                        matched_from_option=opt_name,
                        data=entry.data,
                        priority=priority,
                        extracted_disk_path=entry.extracted_disk_path,
                    )
            return sub_copied

        if tag == "file":
            if src_file:
                clean_dst = resolve_file_destination(raw_dst, src_file.path)
                target_lower = clean_dst.lower()
                existing = items_map.get(target_lower)
                if existing is not None and priority < existing.priority:
                    log.append(f"  [ignoré] {src_file.path} -> {clean_dst} (prio {priority} < {existing.priority})")
                    return

                sz = src_file.size or (len(src_file.data) if src_file.data else 1024)
                if existing is None:
                    copied += 1
                    total_size += sz
                else:
                    total_size += sz - existing.size

                log.append(f"  [+ fichier] {src_file.path} -> {clean_dst} (prio: {priority})")
                items_map[target_lower] = StagingItem(
                    source_path=src_file.path,
                    destination_path=clean_dst,
                    type="file",
                    size=sz,
                    matched_from_option=opt_name,
                    data=src_file.data,
                    priority=priority,
                    extracted_disk_path=src_file.extracted_disk_path,
                )
            elif src_dir:
                sub_copied = copy_folder_files(src_dir)
                log.append(f"  [+ dossier] {src_dir} -> {raw_dst or '.'} ({sub_copied} fichiers)")
            else:
                missing += 1
                log.append(f"  [manquant] (fichier) {src}")
        else:
            # tag == 'folder'
            if src_dir:
                sub_copied = copy_folder_files(src_dir)
                log.append(f"  [+ dossier] {src_dir} -> {raw_dst or '.'} ({sub_copied} fichiers)")
            elif src_file:
                clean_dst = resolve_file_destination(raw_dst, src_file.path)
                target_lower = clean_dst.lower()
                existing = items_map.get(target_lower)
                if existing is not None and priority < existing.priority:
                    return

                sz = src_file.size or (len(src_file.data) if src_file.data else 1024)
                if existing is None:
                    copied += 1
                    total_size += sz
                else:
                    total_size += sz - existing.size

                log.append(f"  [+ fichier] {src_file.path} -> {clean_dst} (prio: {priority})")
                items_map[target_lower] = StagingItem(
                    source_path=src_file.path,
                    destination_path=clean_dst,
                    type="file",
                    size=sz,
                    matched_from_option=opt_name,
                    data=src_file.data,
                    priority=priority,
                    extracted_disk_path=src_file.extracted_disk_path,
                )
            else:
                missing += 1
                log.append(f"  [manquant] (dossier) {src}")

    # 1. Fichiers requis
    if required_files:
        log.append("[Fichiers Requis (requiredInstallFiles)]")
        for req in required_files:
            tag = "file" if isinstance(req, FomodFileItem) else "folder"
            process_node(tag, req.source, req.destination, "Requis", priority=req.priority)

    # 2. Options sélectionnées
    for opt in selected_options:
        log.append(f"\n[{opt.name}]")
        for f in opt.files:
            process_node("file", f.source, f.destination, opt.name, priority=f.priority)
        for fld in opt.folders:
            process_node("folder", fld.source, fld.destination, opt.name, priority=fld.priority)

    # 3. Installations conditionnelles (conditionalFileInstalls)
    if conditional_installs:
        log.append("\n[Installations Conditionnelles (conditionalFileInstalls)]")
        for idx, pat in enumerate(conditional_installs):
            if evaluate_dependencies(pat.dependencies, c_basenames, c_flags):
                for f in pat.files:
                    process_node("file", f.source, f.destination, f"Conditionnel #{idx+1}", priority=f.priority)
                for fld in pat.folders:
                    process_node("folder", fld.source, fld.destination, f"Conditionnel #{idx+1}", priority=fld.priority)

    items_list = list(items_map.values())
    items_list.sort(key=lambda x: x.destination_path.lower())

    return StagingResult(
        items=items_list,
        total_size=total_size,
        copied_count=copied,
        missing_count=missing,
        log=log,
    )


def export_staging_to_directory(staging_result: StagingResult, target_dir: str):
    """Écrit physiquement les fichiers du staging simulé vers un répertoire de destination."""
    os.makedirs(target_dir, exist_ok=True)
    for item in staging_result.items:
        dest_full = os.path.join(target_dir, item.destination_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest_full), exist_ok=True)
        if item.data:
            with open(dest_full, "wb") as fh:
                fh.write(item.data)
        elif item.extracted_disk_path and os.path.isfile(item.extracted_disk_path):
            try:
                shutil.copy2(item.extracted_disk_path, dest_full)
            except Exception as e:
                logger.warning(f"Erreur copie disque {item.extracted_disk_path} -> {dest_full}: {e}")
                with open(dest_full, "wb") as fh:
                    fh.write(b"")
        else:
            with open(dest_full, "wb") as fh:
                fh.write(b"")


def export_staging_to_zip(staging_result: StagingResult, zip_path: str):
    """Génère une archive .ZIP propre du staging prêt à être installé."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in staging_result.items:
            data = item.data if item.data else b""
            zf.writestr(item.destination_path, data)
