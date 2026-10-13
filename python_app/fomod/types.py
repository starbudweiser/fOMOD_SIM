from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum


class GroupType(str, Enum):
    SelectExactlyOne = "SelectExactlyOne"
    SelectAtLeastOne = "SelectAtLeastOne"
    SelectAtMostOne = "SelectAtMostOne"
    SelectAny = "SelectAny"
    SelectAll = "SelectAll"


@dataclass
class FomodFileItem:
    source: str
    destination: str
    priority: int = 0
    # alwaysInstall : installé même si l'option n'est pas cochée (étape visible)
    always_install: bool = False
    # installIfUsable : installé même non coché, sauf si l'option est « NotUsable »
    install_if_usable: bool = False


@dataclass
class FomodFolderItem:
    source: str
    destination: str
    priority: int = 0
    always_install: bool = False
    install_if_usable: bool = False


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
    # Conditions non simulables (version du jeu, de FOMM, de SKSE…) : considérées satisfaites
    assumed_true: int = 0


@dataclass
class TypeDescriptorPattern:
    dependencies: FomodDependencies
    type_name: str = "Optional"  # 'Recommended' | 'Optional' | 'Required' | 'NotUsable' | 'CouldBeUsable'


@dataclass
class TypeDescriptor:
    default_type: str = "Optional"
    patterns: List[TypeDescriptorPattern] = field(default_factory=list)


@dataclass
class ConditionalInstallPattern:
    dependencies: FomodDependencies
    files: List[FomodFileItem] = field(default_factory=list)
    folders: List[FomodFolderItem] = field(default_factory=list)


@dataclass
class FomodOption:
    id: str
    name: str
    description: str = ""
    image_path: Optional[str] = None
    files: List[FomodFileItem] = field(default_factory=list)
    folders: List[FomodFolderItem] = field(default_factory=list)
    flags: Dict[str, str] = field(default_factory=dict)
    dependencies: Optional[FomodDependencies] = None
    type_descriptor: Optional[TypeDescriptor] = None
    is_default: bool = False
    # Masters des plugins de l'option hors jeu de base et hors mod (voir plugins.annotate_option_masters)
    required_masters: Set[str] = field(default_factory=set)


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
    # Condition <visible> de l'étape (None = toujours visible)
    visibility: Optional[FomodDependencies] = None


@dataclass
class FomodMetadata:
    name: str = "Mod Skyrim"
    author: str = ""
    version: str = "1.0.0"
    website: str = ""
    description: str = ""


@dataclass
class VirtualFileEntry:
    path: str
    is_dir: bool = False
    size: int = 0
    data: Optional[bytes] = None
    extracted_disk_path: Optional[str] = None
    # Nom exact du membre dans l'archive (pour une lecture différée, ex. aperçu d'une texture)
    member: Optional[str] = None


@dataclass
class ArchiveIndex:
    files: Dict[str, VirtualFileEntry] = field(default_factory=dict)  # lower_path -> entry
    dirs: Dict[str, str] = field(default_factory=dict)  # lower_path -> original_path
    archive_path: Optional[str] = None
    temp_dir: Optional[str] = None
    _basename_map: Optional[Dict[str, List[VirtualFileEntry]]] = field(default=None, init=False, repr=False)

    @property
    def basename_map(self) -> Dict[str, List[VirtualFileEntry]]:
        if self._basename_map is None:
            bm: Dict[str, List[VirtualFileEntry]] = {}
            for rel_key, entry in self.files.items():
                if "__macosx" in rel_key:
                    continue
                b = rel_key.split("/")[-1]
                if b not in bm:
                    bm[b] = []
                bm[b].append(entry)
            for lst in bm.values():
                lst.sort(key=lambda x: len(x.path))
            self._basename_map = bm
        return self._basename_map

    def clear_cache(self) -> None:
        self._basename_map = None


@dataclass
class StagingItem:
    source_path: str
    destination_path: str
    type: str  # 'file' | 'folder'
    size: int
    matched_from_option: str
    data: Optional[bytes] = None
    priority: int = 0
    extracted_disk_path: Optional[str] = None
    # Membre de l'archive à lire à l'export quand le contenu n'a pas été chargé à l'indexation
    member: Optional[str] = None


@dataclass
class StagingResult:
    items: List[StagingItem]
    total_size: int
    copied_count: int
    missing_count: int
    log: List[str]
