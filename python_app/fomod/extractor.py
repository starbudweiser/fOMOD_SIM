import os
import io
import re
import zipfile
import tarfile
import subprocess
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional, Callable, List
from .types import ArchiveIndex, VirtualFileEntry
from .parser import norm

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".dds", ".webp", ".gif")


def reanchor_index(
    files_map: Dict[str, VirtualFileEntry],
    dirs_map: Dict[str, str],
) -> Tuple[Dict[str, VirtualFileEntry], Dict[str, str]]:
    """Détecte si l'archive ou le dossier est encapsulé dans un dossier racine parent
    (ex: NomDuMod_v1.0/fomod/ModuleConfig.xml)
    et réaligne tous les chemins à la racine du FOMOD."""
    root_prefix = ""

    # 1. Recherche de fomod/moduleconfig.xml dans un sous-dossier
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
            is_dir=entry.is_dir,
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


def is_essential_file(path_lower: str) -> bool:
    """Détermine si un fichier doit être décompressé en mémoire (XML FOMOD, images, plugins, INIs)."""
    bn = path_lower.split("/")[-1]
    if bn in ("moduleconfig.xml", "info.xml"):
        return True
    if bn.endswith(IMAGE_EXTENSIONS):
        return True
    if bn.endswith((".esp", ".esm", ".esl", ".ini", ".txt")):
        return True
    if "fomod/" in path_lower:
        return True
    return False



def decode_xml_text(data: bytes) -> str:
    """Décode du texte XML en gérant UTF-8 avec/sans BOM, UTF-16 et Latin-1."""
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("latin-1", errors="replace")


def extract_directory(
    folder_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Indexe un dossier local de mod."""
    if progress_cb:
        progress_cb(f"Indexation du dossier {os.path.basename(folder_path)}...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    total_files = 0

    for current_root, dirs, files in os.walk(folder_path):
        for f in files:
            full_path = os.path.join(current_root, f)
            rel_path = norm(os.path.relpath(full_path, folder_path))

            if "__macosx" in rel_path.lower() or rel_path.endswith(".DS_Store") or rel_path == ".DS_Store":
                continue

            lower = rel_path.lower()
            try:
                sz = os.path.getsize(full_path)
                data = None
                if is_essential_file(lower):
                    with open(full_path, "rb") as fh:
                        data = fh.read()
            except Exception as e:
                logger.warning(f"Impossible de lire le fichier {full_path} : {e}")
                continue

            files_map[lower] = VirtualFileEntry(
                path=rel_path,
                is_dir=False,
                size=sz,
                data=data,
                extracted_disk_path=full_path,
            )

            bn = lower.split("/")[-1]
            if bn == "moduleconfig.xml" and data:
                module_config_xml = decode_xml_text(data)
            elif bn == "info.xml" and data:
                info_xml = decode_xml_text(data)

            parts = rel_path.split("/")
            cur = ""
            for i in range(len(parts) - 1):
                cur = f"{cur}/{parts[i]}" if cur else parts[i]
                dirs_map[cur.lower()] = cur

            total_files += 1
            if total_files % 50 == 0 and progress_cb:
                progress_cb(f"Indexation : {total_files} fichiers analysés...")

    new_files, new_dirs = reanchor_index(files_map, dirs_map)

    if not module_config_xml:
        for k, v in new_files.items():
            if k.endswith("moduleconfig.xml"):
                if v.data:
                    module_config_xml = decode_xml_text(v.data)
                    break
                elif v.extracted_disk_path and os.path.exists(v.extracted_disk_path):
                    try:
                        with open(v.extracted_disk_path, "rb") as fh:
                            module_config_xml = decode_xml_text(fh.read())
                        break
                    except Exception as e:
                        logger.warning(f"Impossible de lire moduleconfig.xml : {e}")

    if not info_xml:
        for k, v in new_files.items():
            if k.endswith("info.xml"):
                if v.data:
                    info_xml = decode_xml_text(v.data)
                    break
                elif v.extracted_disk_path and os.path.exists(v.extracted_disk_path):
                    try:
                        with open(v.extracted_disk_path, "rb") as fh:
                            info_xml = decode_xml_text(fh.read())
                        break
                    except Exception as e:
                        logger.warning(f"Impossible de lire info.xml : {e}")

    return ArchiveIndex(files=new_files, dirs=new_dirs, archive_path=folder_path), module_config_xml, info_xml


def extract_zip(
    archive_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Extrait une archive ZIP de manière optimisée sans saturer la RAM."""
    if progress_cb:
        progress_cb(f"Ouverture de l'archive ZIP {os.path.basename(archive_path)}...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    with zipfile.ZipFile(archive_path, "r") as zf:
        infolist = zf.infolist()
        total = len(infolist)

        for idx, item in enumerate(infolist):
            raw_path = item.filename
            if "__MACOSX" in raw_path or raw_path.endswith(".DS_Store") or raw_path == ".DS_Store":
                continue

            normalized = norm(raw_path)
            lower = normalized.lower()

            if item.is_dir():
                dirs_map[lower] = normalized
            else:
                # Ne charger les données en mémoire que pour les fichiers essentiels
                data = None
                if is_essential_file(lower):
                    try:
                        data = zf.read(item)
                    except Exception as e:
                        logger.warning(f"Erreur lecture zip {raw_path}: {e}")

                files_map[lower] = VirtualFileEntry(
                    path=normalized,
                    is_dir=False,
                    size=item.file_size,
                    data=data,
                )

                bn = lower.split("/")[-1]
                if bn == "moduleconfig.xml" and data:
                    module_config_xml = decode_xml_text(data)
                elif bn == "info.xml" and data:
                    info_xml = decode_xml_text(data)

                parts = normalized.split("/")
                cur = ""
                for i in range(len(parts) - 1):
                    cur = f"{cur}/{parts[i]}" if cur else parts[i]
                    dirs_map[cur.lower()] = cur

            if idx % 50 == 0 and progress_cb:
                progress_cb(f"Indexation ZIP : {idx}/{total} éléments...")

    new_files, new_dirs = reanchor_index(files_map, dirs_map)
    return ArchiveIndex(files=new_files, dirs=new_dirs, archive_path=archive_path), module_config_xml, info_xml


def extract_tar(
    archive_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Extrait une archive TAR / TAR.GZ / TAR.BZ2."""
    if progress_cb:
        progress_cb(f"Ouverture de l'archive TAR {os.path.basename(archive_path)}...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    with tarfile.open(archive_path, "r:*") as tf:
        members = tf.getmembers()
        for idx, m in enumerate(members):
            raw_path = m.name
            if "__MACOSX" in raw_path or raw_path.endswith(".DS_Store"):
                continue

            normalized = norm(raw_path)
            lower = normalized.lower()

            if m.isdir():
                dirs_map[lower] = normalized
            elif m.isfile():
                data = None
                if is_essential_file(lower):
                    fh = tf.extractfile(m)
                    data = fh.read() if fh else None

                files_map[lower] = VirtualFileEntry(
                    path=normalized,
                    is_dir=False,
                    size=m.size,
                    data=data,
                )

                bn = lower.split("/")[-1]
                if bn == "moduleconfig.xml" and data:
                    module_config_xml = decode_xml_text(data)
                elif bn == "info.xml" and data:
                    info_xml = decode_xml_text(data)

                parts = normalized.split("/")
                cur = ""
                for i in range(len(parts) - 1):
                    cur = f"{cur}/{parts[i]}" if cur else parts[i]
                    dirs_map[cur.lower()] = cur

    new_files, new_dirs = reanchor_index(files_map, dirs_map)
    return ArchiveIndex(files=new_files, dirs=new_dirs), module_config_xml, info_xml


def extract_7z_with_cli(
    archive_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Extraction via utilitaire CLI 7z, unrar ou bsdtar sans saturer la RAM."""
    cli_cmd = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
    if not cli_cmd:
        cli_cmd = shutil.which("unrar") or shutil.which("bsdtar") or shutil.which("tar")

    if not cli_cmd:
        raise RuntimeError("Aucun outil 7z, unrar ou tar/bsdtar disponible sur le système.")

    if progress_cb:
        progress_cb(f"Extraction via utilitaire système ({os.path.basename(cli_cmd)})...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    tmp_extract = tempfile.mkdtemp(prefix="fomod_extracted_")
    cmd_name = os.path.basename(cli_cmd).lower()

    try:
        if "7z" in cmd_name:
            cmd = [cli_cmd, "x", archive_path, f"-o{tmp_extract}", "-y"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        elif "unrar" in cmd_name:
            cmd = [cli_cmd, "x", "-y", archive_path, tmp_extract]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            # bsdtar / tar
            cmd = [cli_cmd, "-xf", archive_path, "-C", tmp_extract]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        # Scanner les fichiers extraits dans tmp_extract
        for root, _, fnames in os.walk(tmp_extract):
            for fn in fnames:
                full_p = os.path.join(root, fn)
                rel_p = norm(os.path.relpath(full_p, tmp_extract))
                if "__macosx" in rel_p.lower() or rel_p.endswith(".DS_Store"):
                    continue

                lower = rel_p.lower()
                try:
                    sz = os.path.getsize(full_p)
                    data = None
                    if is_essential_file(lower):
                        with open(full_p, "rb") as fh:
                            data = fh.read()

                    files_map[lower] = VirtualFileEntry(
                        path=rel_p,
                        size=sz,
                        data=data,
                        extracted_disk_path=full_p,
                    )

                    bn = fn.lower()
                    if bn == "moduleconfig.xml" and data:
                        module_config_xml = decode_xml_text(data)
                    elif bn == "info.xml" and data:
                        info_xml = decode_xml_text(data)

                    parts = rel_p.split("/")
                    cur = ""
                    for i in range(len(parts) - 1):
                        cur = f"{cur}/{parts[i]}" if cur else parts[i]
                        dirs_map[cur.lower()] = cur
                except Exception as e:
                    logger.warning(f"Erreur lecture fichier extrait CLI {full_p}: {e}")

        # Si module_config_xml n'a pas été trouvé lors du premier passage
        if not module_config_xml:
            for root, _, fnames in os.walk(tmp_extract):
                for fn in fnames:
                    if fn.lower() == "moduleconfig.xml":
                        fp = os.path.join(root, fn)
                        try:
                            with open(fp, "rb") as fh:
                                module_config_xml = decode_xml_text(fh.read())
                        except Exception as e:
                            logger.warning(f"Erreur lecture moduleconfig.xml : {e}")
                        break
                if module_config_xml:
                    break

        new_files, new_dirs = reanchor_index(files_map, dirs_map)
        return ArchiveIndex(files=new_files, dirs=new_dirs, temp_dir=tmp_extract), module_config_xml, info_xml
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction CLI : {e}")
        raise


def extract_7z(
    archive_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Extrait une archive 7Z de manière sûre sans décompresser toute la mémoire d'un coup."""
    if progress_cb:
        progress_cb(f"Analyse de l'archive 7Z {os.path.basename(archive_path)}...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    # Tentative avec py7zr
    try:
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode="r") as sz:
            # 1. Lister les fichiers sans décompresser les giga-octets de textures/meshes
            file_infos = sz.list()
            targets_to_extract: List[str] = []

            for item in file_infos:
                raw_path = item.filename
                if "__MACOSX" in raw_path or raw_path.endswith(".DS_Store"):
                    continue
                normalized = norm(raw_path)
                lower = normalized.lower()

                if item.is_directory:
                    dirs_map[lower] = normalized
                    continue

                files_map[lower] = VirtualFileEntry(
                    path=normalized,
                    is_dir=False,
                    size=item.uncompressed,
                    data=None,
                )

                bn = lower.split("/")[-1]
                parts = normalized.split("/")
                cur = ""
                for i in range(len(parts) - 1):
                    cur = f"{cur}/{parts[i]}" if cur else parts[i]
                    dirs_map[cur.lower()] = cur

                # On ne cible que les fichiers critiques (FOMOD xml et images d'illustration)
                if is_essential_file(lower):
                    targets_to_extract.append(item.filename)

            # 2. Décompresser uniquement les cibles requises
            if targets_to_extract:
                if progress_cb:
                    progress_cb("Chargement des configurations FOMOD et aperçus...")
                try:
                    read_dict = sz.read(targets=targets_to_extract)
                    for raw_path, bio in read_dict.items():
                        norm_p = norm(raw_path)
                        lower = norm_p.lower()
                        data = bio.read()
                        if lower in files_map:
                            files_map[lower].data = data

                        bn = lower.split("/")[-1]
                        if bn == "moduleconfig.xml":
                            module_config_xml = decode_xml_text(data)
                        elif bn == "info.xml":
                            info_xml = decode_xml_text(data)
                except Exception as e:
                    logger.warning(f"Erreur extraction ciblée 7z : {e}")

            new_files, new_dirs = reanchor_index(files_map, dirs_map)
            return ArchiveIndex(files=new_files, dirs=new_dirs), module_config_xml, info_xml

    except Exception as py7zr_err:
        logger.warning(f"Échec de l'extraction py7zr ({py7zr_err}), tentative via fallback...")
        try:
            return extract_7z_with_cli(archive_path, progress_cb)
        except Exception:
            try:
                return extract_zip(archive_path, progress_cb)
            except Exception:
                raise RuntimeError(
                    f"Impossible d'ouvrir l'archive 7Z '{os.path.basename(archive_path)}'. "
                    f"Erreur : {py7zr_err}"
                )


def extract_rar(
    archive_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Extrait une archive RAR de manière sécurisée avec fallbacks multiples (rarfile, 7z, unrar, bsdtar)."""
    if progress_cb:
        progress_cb(f"Analyse de l'archive RAR {os.path.basename(archive_path)}...")

    files_map: Dict[str, VirtualFileEntry] = {}
    dirs_map: Dict[str, str] = {}
    module_config_xml = ""
    info_xml = ""

    # 1. Tentative avec rarfile (si disponible et unrar configuré)
    try:
        import rarfile
        with rarfile.RarFile(archive_path, "r") as rf:
            for item in rf.infolist():
                raw_path = item.filename
                if "__MACOSX" in raw_path or raw_path.endswith(".DS_Store"):
                    continue
                normalized = norm(raw_path)
                lower = normalized.lower()

                if item.isdir():
                    dirs_map[lower] = normalized
                    continue

                data = None
                if is_essential_file(lower):
                    try:
                        data = rf.read(item)
                    except Exception as e:
                        logger.warning(f"Erreur lecture rarfile pour {raw_path}: {e}")

                files_map[lower] = VirtualFileEntry(
                    path=normalized,
                    is_dir=False,
                    size=item.file_size,
                    data=data,
                )

                bn = lower.split("/")[-1]
                if bn == "moduleconfig.xml" and data:
                    module_config_xml = decode_xml_text(data)
                elif bn == "info.xml" and data:
                    info_xml = decode_xml_text(data)

                parts = normalized.split("/")
                cur = ""
                for i in range(len(parts) - 1):
                    cur = f"{cur}/{parts[i]}" if cur else parts[i]
                    dirs_map[cur.lower()] = cur

            new_files, new_dirs = reanchor_index(files_map, dirs_map)
            return ArchiveIndex(files=new_files, dirs=new_dirs), module_config_xml, info_xml
    except Exception as rarfile_err:
        logger.info(f"rarfile non utilisable ({rarfile_err}), tentative par CLI système...")

    # 2. Tentative avec les outils système (7z, unrar, bsdtar)
    try:
        return extract_7z_with_cli(archive_path, progress_cb)
    except Exception as cli_err:
        logger.warning(f"Échec extraction CLI RAR: {cli_err}")

    # 3. Tentative zipfile au cas où ce soit un zip renommé en .rar
    try:
        return extract_zip(archive_path, progress_cb)
    except Exception:
        pass

    raise RuntimeError(
        f"Impossible d'ouvrir l'archive RAR '{os.path.basename(archive_path)}'.\n"
        "Pour ouvrir les fichiers .rar sous macOS/Linux/Windows, installez l'utilitaire 7-Zip ou UnRAR "
        "(ex: 'brew install p7zip' ou 'pip install rarfile'). "
        "Vous pouvez également convertir l'archive au format .ZIP standard."
    )


def extract_archive(
    file_or_dir_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[ArchiveIndex, str, str]:
    """Détecteur universel pour dossier, ZIP, 7Z, RAR, TAR, etc."""
    p = Path(file_or_dir_path)
    if not p.exists():
        raise FileNotFoundError(f"Chemin introuvable : {file_or_dir_path}")

    if p.is_dir():
        return extract_directory(str(p), progress_cb)

    ext = p.suffix.lower()
    if ext == ".zip":
        return extract_zip(str(p), progress_cb)
    elif ext in (".tar", ".gz", ".bz2", ".tgz"):
        return extract_tar(str(p), progress_cb)
    elif ext == ".7z":
        return extract_7z(str(p), progress_cb)
    elif ext == ".rar":
        return extract_rar(str(p), progress_cb)
    else:
        # Tenter zip en premier
        try:
            return extract_zip(str(p), progress_cb)
        except Exception:
            try:
                return extract_7z(str(p), progress_cb)
            except Exception:
                return extract_tar(str(p), progress_cb)
