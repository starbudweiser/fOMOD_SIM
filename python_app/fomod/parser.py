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

    # 3. Correspondance par suffixe, sur des segments entiers (« mod.esp » ne trouve pas « mymod.esp »)
    suffix_cands: List[VirtualFileEntry] = []
    suffix_slash_key = "/" + key
    for rel_key, entry in index.files.items():
        if "__macosx" in rel_key:
            continue
        if rel_key.endswith(suffix_slash_key) or key.endswith("/" + rel_key):
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


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".dds", ".tga", ".webp", ".gif")


def find_image_in_index(index: ArchiveIndex, src: str) -> Optional[VirtualFileEntry]:
    """Comme find_file_in_index, mais tolère une extension d'image différente de celle déclarée
    (installeur qui annonce « .png » alors que l'archive contient « .jpg »)."""
    entry = find_file_in_index(index, src)
    if entry is not None or not src:
        return entry
    key = norm(src).lower()
    stem = key.rsplit(".", 1)[0] if "." in key.split("/")[-1] else key
    for ext in IMAGE_EXTS:
        alt = find_file_in_index(index, stem + ext)
        if alt is not None:
            return alt
    return None


def find_folder_in_index(index: ArchiveIndex, src: str) -> Optional[str]:
    """Retrouve un dossier de l'archive (casse d'origine). Une source vide désigne la racine du mod."""
    raw_key = norm(src)
    if not raw_key:
        return ""
    key = raw_key.lower()

    # 1. Correspondance exacte
    if key in index.dirs and "__macosx" not in key:
        return index.dirs[key]

    # 2. Dossier implicite (archives sans entrées de dossier) : déduit des chemins de fichiers
    prefix = key + "/"
    for rel_key, entry in index.files.items():
        if rel_key.startswith(prefix) and "__macosx" not in rel_key:
            return entry.path[: len(raw_key)]

    # 3. Correspondance par suffixe sur des segments entiers
    slash_key = "/" + key
    cands: List[str] = []
    for rel_key, orig in index.dirs.items():
        if "__macosx" in rel_key:
            continue
        if rel_key.endswith(slash_key) or key.endswith("/" + rel_key):
            cands.append(orig)
    if cands:
        cands.sort(key=len)
        return cands[0]

    # 4. Correspondance sans préfixes numériques (« 01 Textures » ↔ « Textures »)
    key_bn = strip_num_prefix(key)
    prefix_cands: List[str] = []
    for rel_key, orig in index.dirs.items():
        if "__macosx" in rel_key:
            continue
        same_parent = rel_key.rpartition("/")[0] == key.rpartition("/")[0]
        if same_parent and strip_num_prefix(rel_key) == key_bn:
            prefix_cands.append(orig)
    if prefix_cands:
        prefix_cands.sort(key=len)
        return prefix_cands[0]

    return None


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def _attr(el: ET.Element, *names: str, default: Optional[str] = None) -> Optional[str]:
    """Lit un attribut sans tenir compte de la casse de son nom."""
    lowered = {k.lower(): v for k, v in el.attrib.items()}
    for n in names:
        v = lowered.get(n.lower())
        if v is not None:
            return v
    return default


def _children(el: ET.Element, *names: str) -> List[ET.Element]:
    wanted = {n.lower() for n in names}
    return [c for c in el if _local(c.tag) in wanted]


def _child(el: ET.Element, *names: str) -> Optional[ET.Element]:
    found = _children(el, *names)
    return found[0] if found else None


def parse_dependencies_node(node: ET.Element) -> FomodDependencies:
    """Analyse récursive d'un bloc de dépendances (<dependencies>, <visible>, <moduleDependencies>…).
    Le nœud lui-même porte l'opérateur ; ses enfants sont les conditions."""
    operator = _attr(node, "operator", default="And") or "And"
    file_deps: List[FileDependency] = []
    flag_deps: List[FlagDependency] = []
    nested_deps: List[FomodDependencies] = []
    assumed = 0

    for child in node:
        tag = _local(child.tag)
        if tag == "filedependency":
            f = _attr(child, "file", default="") or ""
            st = _attr(child, "state", default="Active") or "Active"
            if f:
                file_deps.append(FileDependency(file=f, state=st))
        elif tag == "flagdependency":
            fl = _attr(child, "flag", default="") or ""
            val = _attr(child, "value", default="") or ""
            if fl:
                flag_deps.append(FlagDependency(flag=fl, value=val))
        elif tag == "dependencies":
            nested_deps.append(parse_dependencies_node(child))
        elif tag.endswith("dependency"):
            # gameDependency, fommDependency, foseDependency… : non simulables, supposées satisfaites
            assumed += 1

    return FomodDependencies(
        operator=operator,
        file_dependencies=file_deps,
        flag_dependencies=flag_deps,
        nested_dependencies=nested_deps,
        assumed_true=assumed,
    )


def parse_condition_container(node: Optional[ET.Element]) -> Optional[FomodDependencies]:
    """<visible> ou <pattern> peuvent contenir les conditions directement ou via un <dependencies>."""
    if node is None:
        return None
    if _local(node.tag) == "dependencies":
        return parse_dependencies_node(node)
    inner = _children(node, "dependencies")
    has_direct = any(_local(c.tag).endswith("dependency") for c in node)
    if len(inner) == 1 and not has_direct:
        return parse_dependencies_node(inner[0])
    return parse_dependencies_node(node)


FLAG_FALSE = ("", "inactive", "false", "missing", "0", "off", "none", "no", "disabled")
FLAG_TRUE = ("active", "true", "1", "on", "yes", "enabled")


def check_flag_value(curr_val: Optional[str], expected_val: str) -> bool:
    """Évalue la concordance d'un flag FOMOD (comparaison exacte d'abord, puis équivalences
    usuelles On/True/Active…). Un flag non défini vaut la chaîne vide."""
    curr = (curr_val or "").strip()
    exp = (expected_val or "").strip()
    if curr == exp:
        return True
    cl, el = curr.lower(), exp.lower()
    if cl == el:
        return True
    if el in FLAG_FALSE:
        return cl in FLAG_FALSE
    if el in FLAG_TRUE:
        return cl in FLAG_TRUE
    return False


def evaluate_dependencies(
    deps: Optional[FomodDependencies],
    installed_basenames: Set[str],
    active_flags: Dict[str, str],
) -> bool:
    """Évalue récursivement si les dépendances FOMOD sont satisfaites.
    Les plugins présents dans le dossier Data sont considérés comme actifs."""
    if not deps:
        return True

    results: List[bool] = [True] * deps.assumed_true

    for fd in deps.file_dependencies:
        base = fd.file.replace("\\", "/").strip().split("/")[-1].lower()
        present = base in installed_basenames
        st = (fd.state or "Active").strip().lower()
        if st in ("active", "present", "installed", "true"):
            results.append(present)
        elif st in ("missing", "absent", "false"):
            results.append(not present)
        elif st == "inactive":
            # Présent mais désactivé : impossible à distinguer, les plugins présents sont supposés actifs
            results.append(False)
        else:
            results.append(present)

    for flag_dep in deps.flag_dependencies:
        results.append(check_flag_value(active_flags.get(flag_dep.flag), flag_dep.value))

    for nested in deps.nested_dependencies:
        results.append(evaluate_dependencies(nested, installed_basenames, active_flags))

    if not results:
        return True

    op = (deps.operator or "And").strip().lower()
    if op == "or":
        return any(results)
    if op == "not":
        return not any(results)
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


RE_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>", re.I)


def load_xml_root(xml_text: str) -> ET.Element:
    """Parse un XML FOMOD tolérant : BOM, déclaration d'encodage (UTF-16…) déjà décodée,
    caractères de contrôle parasites ; supprime les espaces de noms des balises."""
    cleaned = xml_text.lstrip("﻿").replace("\x00", "")
    # La déclaration <?xml encoding="UTF-16"?> est fausse une fois le texte décodé : on la retire
    cleaned = RE_XML_DECL.sub("", cleaned, count=1).strip()
    cleaned = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    # Esperluettes nues (« Tops & Bottoms ») : fréquentes dans les FOMOD écrits à la main
    cleaned = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", cleaned)
    root = ET.fromstring(cleaned)
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _ordered(elements: List[ET.Element], container: Optional[ET.Element]) -> List[ET.Element]:
    """Applique l'attribut order (Explicit | Ascending | Descending) du conteneur.
    Sans attribut, l'ordre du document est conservé (comportement de Mod Organizer 2)."""
    order = (_attr(container, "order", default="") or "").strip().lower() if container is not None else ""
    if order == "ascending":
        return sorted(elements, key=lambda e: (_attr(e, "name", default="") or "").casefold())
    if order == "descending":
        return sorted(elements, key=lambda e: (_attr(e, "name", default="") or "").casefold(), reverse=True)
    return elements


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes")


def _parse_file_list(container: Optional[ET.Element]) -> List[FomodFileItem | FomodFolderItem]:
    """Lit les <file>/<folder> d'un conteneur <files> ou <requiredInstallFiles>.
    Destination absente = même chemin que la source (schéma FOMOD) ; destination vide = racine."""
    items: List[FomodFileItem | FomodFolderItem] = []
    if container is None:
        return items
    for el in container.iter():
        tag = _local(el.tag)
        if tag not in ("file", "folder"):
            continue
        raw_src = _attr(el, "source", default=None)
        if raw_src is None:
            continue
        src = norm(raw_src)
        raw_dst = _attr(el, "destination", default=None)
        dst = src if raw_dst is None else norm(raw_dst)
        try:
            prio = int((_attr(el, "priority", default="0") or "0").strip())
        except ValueError:
            prio = 0
        kwargs = dict(
            source=src,
            destination=dst,
            priority=prio,
            always_install=_truthy(_attr(el, "alwaysInstall")),
            install_if_usable=_truthy(_attr(el, "installIfUsable")),
        )
        if tag == "file":
            if src:
                items.append(FomodFileItem(**kwargs))
        else:
            # Un dossier source vide désigne la racine du mod
            items.append(FomodFolderItem(**kwargs))
    return items


def _parse_type_descriptor(pl_el: ET.Element) -> Optional[TypeDescriptor]:
    td_el = _child(pl_el, "typeDescriptor")
    if td_el is None:
        return None
    dt_el = _child(td_el, "dependencyType")
    if dt_el is not None:
        def_el = _child(dt_el, "defaultType")
        def_name = (_attr(def_el, "name", default="Optional") if def_el is not None else "Optional") or "Optional"
        patterns: List[TypeDescriptorPattern] = []
        pats = _child(dt_el, "patterns")
        for pat_el in _children(pats, "pattern") if pats is not None else []:
            deps = parse_condition_container(_child(pat_el, "dependencies")) or FomodDependencies()
            t_el = _child(pat_el, "type")
            t_name = (_attr(t_el, "name", default="Optional") if t_el is not None else "Optional") or "Optional"
            patterns.append(TypeDescriptorPattern(dependencies=deps, type_name=t_name))
        return TypeDescriptor(default_type=def_name, patterns=patterns)
    t_el = _child(td_el, "type")
    if t_el is not None:
        return TypeDescriptor(default_type=_attr(t_el, "name", default="Optional") or "Optional", patterns=[])
    return None


def _element_text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_module_config_xml(
    xml_text: str,
) -> Tuple[str, List[FomodStep], List[FomodFileItem | FomodFolderItem], List[ConditionalInstallPattern]]:
    """Analyse ModuleConfig.xml et renvoie (nom_module, étapes, fichiers_requis, conditional_installs).
    Suit le schéma ModConfig 5.0 (installSteps > installStep > optionalFileGroups > group > plugins
    > plugin) et tolère les variantes rencontrées dans les mods réels."""
    if not xml_text or not xml_text.strip():
        logger.warning("Texte XML vide ou absent pour ModuleConfig.xml")
        return "Mod sans configuration FOMOD", [], [], []

    try:
        root = load_xml_root(xml_text)
    except Exception as e:
        logger.exception("Erreur de parsing XML dans ModuleConfig.xml")
        raise ValueError(f"Erreur de syntaxe XML : {e}")

    module_name = _element_text(_child(root, "moduleName"))
    if not module_name:
        for child in root.iter():
            if _local(child.tag) == "modulename" and _element_text(child):
                module_name = _element_text(child)
                break
    if not module_name:
        module_name = _attr(root, "name", default="Mod Skyrim") or "Mod Skyrim"

    # Fichiers requis
    required_files: List[FomodFileItem | FomodFolderItem] = []
    for req_node in [c for c in root.iter() if _local(c.tag) == "requiredinstallfiles"]:
        required_files.extend(_parse_file_list(req_node))

    # Étapes, dans l'ordre demandé par <installSteps order="…">
    steps_container = _child(root, "installSteps")
    if steps_container is not None:
        step_elements = _ordered(_children(steps_container, "installStep"), steps_container)
    else:
        step_elements = [c for c in root.iter() if _local(c.tag) in ("installstep", "step")]

    steps: List[FomodStep] = []
    for step_idx, step_el in enumerate(step_elements):
        step_name = (_attr(step_el, "name", default="") or "").strip() or _element_text(_child(step_el, "name"))
        if not step_name:
            step_name = f"Étape {step_idx + 1}"

        visibility = parse_condition_container(_child(step_el, "visible"))

        groups_container = _child(step_el, "optionalFileGroups")
        if groups_container is not None:
            group_elements = _ordered(_children(groups_container, "group"), groups_container)
        else:
            group_elements = [c for c in step_el.iter() if _local(c.tag) in ("group", "optionalfilegroup")]

        groups: List[FomodGroup] = []
        for grp_idx, grp_el in enumerate(group_elements):
            group_name = (_attr(grp_el, "name", default="") or "").strip() or _element_text(_child(grp_el, "name"))
            if not group_name:
                group_name = f"Groupe {grp_idx + 1}"

            raw_type = (_attr(grp_el, "type", default="SelectAny") or "SelectAny").strip()
            grp_type = next((gt for gt in GroupType if gt.value.lower() == raw_type.lower()), GroupType.SelectAny)

            plugins_container = _child(grp_el, "plugins")
            if plugins_container is not None:
                plugin_elements = _ordered(_children(plugins_container, "plugin"), plugins_container)
            else:
                plugin_elements = [c for c in grp_el.iter() if _local(c.tag) in ("plugin", "option")]

            options: List[FomodOption] = []
            for pl_idx, pl_el in enumerate(plugin_elements):
                opt_name = (_attr(pl_el, "name", default="") or "").strip()
                if not opt_name:
                    opt_name = _element_text(_child(pl_el, "name", "text"))

                desc = _element_text(_child(pl_el, "description"))
                image_path = extract_element_image(_child(pl_el, "image")) or extract_element_image(pl_el)

                items = _parse_file_list(_child(pl_el, "files"))
                files = [i for i in items if isinstance(i, FomodFileItem)]
                folders = [i for i in items if isinstance(i, FomodFolderItem)]

                if not opt_name:
                    first = (files or folders or [None])[0]
                    opt_name = first.source.split("/")[-1] if first else f"Option {pl_idx + 1}"

                # Flags : <flag name="X">valeur</flag> (la valeur est le texte de la balise)
                flags: Dict[str, str] = {}
                cf = _child(pl_el, "conditionFlags")
                for fl_el in _children(cf, "flag") if cf is not None else []:
                    fname = _attr(fl_el, "name")
                    if fname:
                        fval = fl_el.text.strip() if fl_el.text is not None else (_attr(fl_el, "value", default="") or "")
                        flags[fname] = fval

                type_desc_obj = _parse_type_descriptor(pl_el)
                # Dépendances directes sur le plugin (hors schéma, rencontrées dans de vieux FOMOD)
                deps = parse_condition_container(_child(pl_el, "dependencies"))

                td_default = type_desc_obj.default_type.lower() if type_desc_obj else ""
                is_def = td_default in ("recommended", "required")

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

            groups.append(FomodGroup(id=f"step_{step_idx}_grp_{grp_idx}", name=group_name, type=grp_type, options=options))

        steps.append(FomodStep(id=f"step_{step_idx}", name=step_name, groups=groups, visibility=visibility))

    # conditionalFileInstalls
    conditional_installs: List[ConditionalInstallPattern] = []
    for c_node in [c for c in root.iter() if _local(c.tag) == "conditionalfileinstalls"]:
        pats = _child(c_node, "patterns")
        for pat_el in _children(pats, "pattern") if pats is not None else []:
            pat_deps = parse_condition_container(_child(pat_el, "dependencies")) or FomodDependencies()
            items = _parse_file_list(_child(pat_el, "files"))
            conditional_installs.append(
                ConditionalInstallPattern(
                    dependencies=pat_deps,
                    files=[i for i in items if isinstance(i, FomodFileItem)],
                    folders=[i for i in items if isinstance(i, FomodFolderItem)],
                )
            )

    return module_name, steps, required_files, conditional_installs


def parse_info_xml(xml_text: str) -> FomodMetadata:
    """Analyse info.xml pour extraire les métadonnées (nom, auteur, version, description, website)."""
    try:
        root = load_xml_root(xml_text)

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
