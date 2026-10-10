import re
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Set, Tuple
from .types import (
    FomodStep,
    FomodGroup,
    FomodOption,
    FomodFileItem,
    FomodFolderItem,
    FomodMetadata,
    FomodDependencies,
    FileDependency,
    FlagDependency,
    GroupType,
    ArchiveIndex,
    VirtualFileEntry,
    TypeDescriptor,
    TypeDescriptorPattern,
    ConditionalInstallPattern,
)

logger = logging.getLogger(__name__)

RE_NORM_DOT_SLASH = re.compile(r"^(\.\/)+")
RE_NORM_SLASHES = re.compile(r"^\/+|\/+$")
RE_STRIP_NUM = re.compile(r"^\d+\s*[_-]*\s*")
RE_HUMANIZE = re.compile(r"[_\-.]+")
RE_IMAGE_EXT = re.compile(r"\.(jpe?g|png|bmp|webp|gif|dds|tga)$", re.I)


def norm(p: Optional[str]) -> str:
    """Normalise un chemin : backslashes en slashes, supprime les './' et '/' de tête et fin."""
    if not p:
        return ""
    s = p.replace("\\", "/").strip()
    s = RE_NORM_DOT_SLASH.sub("", s)
    s = RE_NORM_SLASHES.sub("", s)
    return s


def strip_num_prefix(name: str) -> str:
    base = name.split("/")[-1] if "/" in name else name
    return RE_STRIP_NUM.sub("", base).lower()


def is_generic_label(s: str) -> bool:
    if not s:
        return True
    t = s.strip().lower()
    generics = {
        "option", "options", "groupe", "group", "general", "misc", "various",
        "default", "step", "étape", "etape", "choose", "selection", "select",
        "unp", "cbbe", "bodytype", "type",
    }
    if t in generics:
        return True
    if t.startswith("step ") or t.startswith("étape ") or t.startswith("etape "):
        return True
    if len(t) <= 3:
        return True
    return False


def humanize_token(tok: str) -> str:
    t = RE_HUMANIZE.sub(" ", tok).strip()
    return " ".join(w.capitalize() for w in t.split())


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
        if hasattr(index, "basename_map"):
            base_cands = index.basename_map.get(base)
            if base_cands:
                return base_cands[0]
        else:
            base_slash = "/" + base
            fallback_cands: List[VirtualFileEntry] = []
            for rel_key, entry in index.files.items():
                if "__macosx" in rel_key:
                    continue
                if rel_key == base or rel_key.endswith(base_slash):
                    fallback_cands.append(entry)
            if fallback_cands:
                fallback_cands.sort(key=lambda x: len(x.path))
                return fallback_cands[0]

    # 5. Correspondance souple en ignorant les préfixes numériques
    key_stripped = strip_num_prefix(key)
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        rel_stripped = strip_num_prefix(rel_key)
        if rel_stripped == key_stripped or rel_stripped.endswith("/" + key_stripped):
            return entry

    return None


def find_folder_in_index(index: ArchiveIndex, src: str) -> Optional[str]:
    raw_key = norm(src)
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
    for rel_key in index.files.keys():
        if "__macosx" in rel_key:
            continue
        if rel_key.startswith(key + "/") or ("/" + key + "/") in rel_key:
            idx = rel_key.find(key)
            return rel_key[: idx + len(key)]

    return None


def parse_dependencies_node(node: ET.Element) -> FomodDependencies:
    """Analyse récursive d'un bloc <dependencies>."""
    operator = node.attrib.get("operator", "And")
    file_deps: List[FileDependency] = []
    flag_deps: List[FlagDependency] = []
    nested_deps: List[FomodDependencies] = []

    for child in node:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        tag_lower = tag.lower()

        if tag_lower == "filedependency":
            f = child.attrib.get("file") or child.attrib.get("File") or ""
            st = child.attrib.get("state") or child.attrib.get("State") or "Active"
            if f:
                file_deps.append(FileDependency(file=f, state=st))
        elif tag_lower == "flagdependency":
            fl = child.attrib.get("flag") or child.attrib.get("Flag") or ""
            val = child.attrib.get("value") or child.attrib.get("Value") or ""
            if fl:
                flag_deps.append(FlagDependency(flag=fl, value=val))
        elif tag_lower == "dependencies":
            nested_deps.append(parse_dependencies_node(child))

    return FomodDependencies(
        operator=operator,
        file_dependencies=file_deps,
        flag_dependencies=flag_deps,
        nested_dependencies=nested_deps,
    )


def check_flag_value(curr_val: Optional[str], expected_val: str) -> bool:
    """Évalue la concordance d'un flag FOMOD.
    Gère le fait qu'un flag non défini est considéré 'inactive'/'false'."""
    curr = (curr_val or "").strip().lower()
    exp = (expected_val or "").strip().lower()

    if exp in ("inactive", "false", "missing", "0", "off", "none"):
        return curr in ("", "inactive", "false", "missing", "0", "off", "none")
    elif exp in ("active", "true", "1", "on"):
        return curr in ("active", "true", "1", "on")
    else:
        return curr == exp


def evaluate_dependencies(
    deps: Optional[FomodDependencies],
    installed_basenames: Set[str],
    active_flags: Dict[str, str],
) -> bool:
    """Évalue récursivement si les dépendances FOMOD sont satisfaites."""
    if not deps:
        return True

    results: List[bool] = []

    for fd in deps.file_dependencies:
        raw_f = fd.file.replace("\\", "/").strip()
        base = raw_f.split("/")[-1].lower()
        present = base in installed_basenames
        st = (fd.state or "Active").strip().lower()
        if st in ("active", "present", "installed", "true"):
            results.append(present)
        elif st in ("inactive", "missing", "absent", "false"):
            results.append(not present)
        else:
            results.append(present)

    for flag_dep in deps.flag_dependencies:
        curr_val = active_flags.get(flag_dep.flag)
        results.append(check_flag_value(curr_val, flag_dep.value))

    for nested in deps.nested_dependencies:
        results.append(evaluate_dependencies(nested, installed_basenames, active_flags))

    if not results:
        return True

    op = (deps.operator or "And").strip().lower()
    if op == "or":
        return any(results)
    elif op == "not":
        return not any(results)
    else:  # "and"
        return all(results)


def compute_option_type(
    opt: FomodOption,
    installed_basenames: Set[str],
    active_flags: Dict[str, str],
) -> str:
    """Calcule le type effectif d'une option ('Recommended', 'Optional', 'Required', 'NotUsable', 'CouldBeUsable')."""
    if opt.type_descriptor:
        for pat in opt.type_descriptor.patterns:
            if evaluate_dependencies(pat.dependencies, installed_basenames, active_flags):
                return pat.type_name
        return opt.type_descriptor.default_type

    if opt.dependencies:
        if evaluate_dependencies(opt.dependencies, installed_basenames, active_flags):
            return "Recommended"
        return "Optional"

    return "Recommended" if opt.is_default else "Optional"


def is_option_recommended(
    opt: FomodOption,
    installed_basenames: Set[str],
    active_flags: Dict[str, str],
) -> bool:
    """Détermine si une option ou patch doit être auto-cochée."""
    eff_type = compute_option_type(opt, installed_basenames, active_flags)
    eff_lower = eff_type.lower()
    if eff_lower in ("recommended", "required", "highlight"):
        return True
    if eff_lower == "notusable":
        return False

    # Dépendance de fichier directe explicite
    if opt.dependencies:
        has_file_dep = bool(opt.dependencies.file_dependencies) or any(
            d.file_dependencies for d in opt.dependencies.nested_dependencies
        )
        if evaluate_dependencies(opt.dependencies, installed_basenames, active_flags):
            if has_file_dep:
                return True
        elif has_file_dep:
            return False

    # Détection intelligente heuristique si installed_basenames est fourni
    if installed_basenames:
        all_items = opt.files + [FomodFileItem(source=fo.source, destination=fo.destination) for fo in opt.folders]
        for item in all_items:
            fn = item.source.split("/")[-1].lower()
            if "patch" in fn:
                for inst in installed_basenames:
                    clean_inst = inst.rsplit(".", 1)[0]
                    if len(clean_inst) >= 4 and clean_inst in fn.replace(" ", "").replace("-", "").replace("_", ""):
                        return True

    return opt.is_default


def parse_module_config_xml(
    xml_text: str,
) -> Tuple[str, List[FomodStep], List[FomodFileItem | FomodFolderItem], List[ConditionalInstallPattern]]:
    """Analyse ModuleConfig.xml et renvoie (nom_module, étapes, fichiers_requis, conditional_installs)."""
    if not xml_text or not xml_text.strip():
        logger.warning("Texte XML vide ou absent pour ModuleConfig.xml")
        return "Mod sans configuration FOMOD", [], [], []

    try:
        cleaned = xml_text.strip().lstrip("\ufeff")
        root = ET.fromstring(cleaned)
        # SUPPRESSION UNIVERSELLE DES NAMESPACES XML
        for el in root.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
    except Exception as e:
        logger.exception("Erreur de parsing XML dans ModuleConfig.xml")
        raise ValueError(f"Erreur de syntaxe XML : {e}")

    # Recherche du nom de module
    module_name = ""
    for child in root.iter():
        tag = child.tag.lower()
        if tag == "modulename" and child.text and child.text.strip():
            module_name = child.text.strip()
            break
    if not module_name:
        module_name = root.attrib.get("name", "Mod Skyrim")

    # Fichiers requis (requiredInstallFiles)
    required_files: List[FomodFileItem | FomodFolderItem] = []
    for req_node in root.findall(".//requiredInstallFiles"):
        for fn in req_node.findall(".//file"):
            s = norm(fn.attrib.get("source") or fn.attrib.get("Source"))
            d = norm(fn.attrib.get("destination") or fn.attrib.get("Destination"))
            p = int(fn.attrib.get("priority", "0") or fn.attrib.get("Priority", "0") or "0")
            if s:
                required_files.append(FomodFileItem(source=s, destination=d, priority=p))
        for fld in req_node.findall(".//folder"):
            s = norm(fld.attrib.get("source") or fld.attrib.get("Source"))
            d = norm(fld.attrib.get("destination") or fld.attrib.get("Destination"))
            p = int(fld.attrib.get("priority", "0") or fld.attrib.get("Priority", "0") or "0")
            if s:
                required_files.append(FomodFolderItem(source=s, destination=d, priority=p))

    # Étapes (installStep / step)
    all_steps = root.findall(".//installStep") or root.findall(".//step")
    steps: List[FomodStep] = []

    for step_idx, step_el in enumerate(all_steps):
        step_name = step_el.attrib.get("name", "").strip()
        if not step_name:
            for child in step_el:
                if child.tag.lower() == "name" and child.text:
                    step_name = child.text.strip()
                    break
        if not step_name:
            step_name = f"Étape {step_idx + 1}"

        # Groupes dans l'étape (dédupliqués)
        raw_groups = step_el.findall(".//group") or step_el.findall(".//optionalFileGroup")
        seen_grps = set()
        group_elements = []
        for g in raw_groups:
            if g not in seen_grps:
                seen_grps.add(g)
                group_elements.append(g)

        groups: List[FomodGroup] = []
        for grp_idx, grp_el in enumerate(group_elements):
            group_name = grp_el.attrib.get("name", "").strip()
            if not group_name:
                for child in grp_el:
                    if child.tag.lower() == "name" and child.text:
                        group_name = child.text.strip()
                        break
            if not group_name:
                group_name = f"Groupe {grp_idx + 1}"

            raw_type = grp_el.attrib.get("type", "SelectExactlyOne")
            grp_type = GroupType.SelectExactlyOne
            for gt in GroupType:
                if gt.value.lower() == raw_type.lower():
                    grp_type = gt
                    break

            # Options / Plugins (dédupliqués)
            raw_plugins = grp_el.findall(".//plugin") or grp_el.findall(".//option")
            seen_pls = set()
            plugin_elements = []
            for p in raw_plugins:
                if p not in seen_pls:
                    seen_pls.add(p)
                    plugin_elements.append(p)

            options: List[FomodOption] = []
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

                # Extraction universelle de l'image de preview
                image_path = extract_element_image(pl_el)

                # Fichiers de l'option
                files: List[FomodFileItem] = []
                for fn in pl_el.findall(".//file"):
                    s = norm(fn.attrib.get("source") or fn.attrib.get("Source"))
                    d = norm(fn.attrib.get("destination") or fn.attrib.get("Destination"))
                    prio = int(fn.attrib.get("priority", "0") or fn.attrib.get("Priority", "0") or "0")
                    if s:
                        files.append(FomodFileItem(source=s, destination=d, priority=prio))

                # Dossiers de l'option
                folders: List[FomodFolderItem] = []
                for fld in pl_el.findall(".//folder"):
                    s = norm(fld.attrib.get("source") or fld.attrib.get("Source"))
                    d = norm(fld.attrib.get("destination") or fld.attrib.get("Destination"))
                    prio = int(fld.attrib.get("priority", "0") or fld.attrib.get("Priority", "0") or "0")
                    if s:
                        folders.append(FomodFolderItem(source=s, destination=d, priority=prio))

                if not opt_name:
                    if files:
                        opt_name = files[0].source.split("/")[-1]
                    elif folders:
                        opt_name = folders[0].source.split("/")[-1]
                    else:
                        opt_name = f"Option {pl_idx + 1}"

                # Flags
                flags: Dict[str, str] = {}
                for fl_el in pl_el.findall(".//conditionFlags/flag"):
                    fn = fl_el.attrib.get("name")
                    fv = fl_el.attrib.get("value", "true")
                    if fn:
                        flags[fn] = fv

                # Dépendances et TypeDescriptor complet
                type_desc_obj: Optional[TypeDescriptor] = None
                deps: Optional[FomodDependencies] = None

                td_el = pl_el.find(".//typeDescriptor")
                if td_el is not None:
                    dt_el = td_el.find(".//dependencyType")
                    if dt_el is not None:
                        def_type_el = dt_el.find(".//defaultType")
                        def_name = def_type_el.attrib.get("name", "Optional") if def_type_el is not None else "Optional"
                        patterns: List[TypeDescriptorPattern] = []
                        for pat_el in dt_el.findall(".//patterns/pattern"):
                            d_el = pat_el.find(".//dependencies")
                            pat_deps = parse_dependencies_node(d_el) if d_el is not None else FomodDependencies()
                            t_el = pat_el.find(".//type")
                            t_name = t_el.attrib.get("name", "Optional") if t_el is not None else "Optional"
                            patterns.append(TypeDescriptorPattern(dependencies=pat_deps, type_name=t_name))
                        type_desc_obj = TypeDescriptor(default_type=def_name, patterns=patterns)
                    else:
                        t_el = td_el.find(".//type")
                        if t_el is not None:
                            t_name = t_el.attrib.get("name", "Optional")
                            type_desc_obj = TypeDescriptor(default_type=t_name, patterns=[])

                direct_dep_el = pl_el.find(".//dependencies")
                if direct_dep_el is not None:
                    deps = parse_dependencies_node(direct_dep_el)

                # Calcul is_default
                is_def = False
                if type_desc_obj and type_desc_obj.default_type.lower() in ("recommended", "required"):
                    is_def = True
                elif pl_idx == 0 and grp_type in (GroupType.SelectExactlyOne, GroupType.SelectAtLeastOne):
                    is_def = True

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
                        type_descriptor=type_desc_obj,
                        is_default=is_def,
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

    # Déduplication des étapes identiques
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

    # Analyse complète de conditionalFileInstalls
    conditional_installs: List[ConditionalInstallPattern] = []
    for c_node in root.findall(".//conditionalFileInstalls"):
        for pat_el in c_node.findall(".//patterns/pattern"):
            dep_el = pat_el.find(".//dependencies")
            pat_deps = parse_dependencies_node(dep_el) if dep_el is not None else FomodDependencies()
            c_files: List[FomodFileItem] = []
            c_folders: List[FomodFolderItem] = []
            files_container = pat_el.find(".//files")
            if files_container is not None:
                for fn in files_container.findall(".//file"):
                    s = norm(fn.attrib.get("source") or fn.attrib.get("Source"))
                    d = norm(fn.attrib.get("destination") or fn.attrib.get("Destination"))
                    p = int(fn.attrib.get("priority", "0") or fn.attrib.get("Priority", "0") or "0")
                    if s:
                        c_files.append(FomodFileItem(source=s, destination=d, priority=p))
                for fld in files_container.findall(".//folder"):
                    s = norm(fld.attrib.get("source") or fld.attrib.get("Source"))
                    d = norm(fld.attrib.get("destination") or fld.attrib.get("Destination"))
                    p = int(fld.attrib.get("priority", "0") or fld.attrib.get("Priority", "0") or "0")
                    if s:
                        c_folders.append(FomodFolderItem(source=s, destination=d, priority=p))
            conditional_installs.append(ConditionalInstallPattern(dependencies=pat_deps, files=c_files, folders=c_folders))

    return module_name, unique_steps, required_files, conditional_installs


def parse_info_xml(xml_text: str) -> FomodMetadata:
    """Analyse info.xml pour extraire les métadonnées (nom, auteur, version, description, website)."""
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

        name = get_text(["Name", "ModName", "Title"]) or "Mod Skyrim"
        author = get_text(["Author", "Authors"]) or "Inconnu"
        version = get_text(["Version"]) or "1.0.0"
        website = get_text(["Website", "URL", "Homepage", "Link"]) or ""
        desc = get_text(["Description", "Summary", "Details"]) or "(Aucune description disponible)"

        return FomodMetadata(
            name=name,
            author=author,
            version=version,
            website=website,
            description=desc,
        )
    except Exception:
        logger.exception("Erreur lors de la lecture d'info.xml")
        return FomodMetadata(
            name="Mod Skyrim",
            author="Inconnu",
            version="1.0.0",
            website="",
            description="(Impossible de lire info.xml)",
        )
