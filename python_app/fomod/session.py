"""Session d'installation FOMOD : état des sélections, flags, visibilité des étapes et règles des groupes.

Reproduit le déroulé d'un installeur (Mod Organizer 2 / Vortex) :
- une étape n'est affichée que si sa condition <visible> est vraie avec les flags posés par les
  options cochées dans les étapes visibles qui la précèdent ;
- seules les options des étapes visibles sont installées et posent des flags ;
- chaque groupe respecte son type (SelectExactlyOne, SelectAtMostOne, SelectAtLeastOne, SelectAny,
  SelectAll) et chaque option son type effectif (Required, Recommended, Optional, NotUsable,
  CouldBeUsable).
"""
from typing import Dict, List, Optional, Set, Tuple

from .parser import compute_option_type, evaluate_dependencies, is_option_recommended, option_matches_installed
from .staging import build_staging
from .types import (
    ArchiveIndex,
    ConditionalInstallPattern,
    FomodFileItem,
    FomodFolderItem,
    FomodGroup,
    FomodOption,
    FomodStep,
    GroupType,
    StagingResult,
)

SINGLE_CHOICE = (GroupType.SelectExactlyOne, GroupType.SelectAtMostOne)


class InstallSession:
    def __init__(
        self,
        steps: List[FomodStep],
        required_files: Optional[List[FomodFileItem | FomodFolderItem]] = None,
        conditional_installs: Optional[List[ConditionalInstallPattern]] = None,
        installed_basenames: Optional[Set[str]] = None,
    ):
        self.steps = steps
        self.required_files = required_files or []
        self.conditional_installs = conditional_installs or []
        self.installed_basenames: Set[str] = set(installed_basenames or ())
        self.selected: Set[str] = set()
        self._touched_steps: Set[int] = set()
        self.reset_defaults()

    # ------------------------------------------------------------------ flags et visibilité

    def _step_visible_with(self, idx: int, flags: Dict[str, str]) -> bool:
        return evaluate_dependencies(self.steps[idx].visibility, self.installed_basenames, flags)

    def _walk(self, until: Optional[int] = None) -> Tuple[Dict[str, str], List[int]]:
        """Parcourt les étapes dans l'ordre et renvoie (flags, étapes visibles) avant l'étape `until`."""
        flags: Dict[str, str] = {}
        visible: List[int] = []
        stop = len(self.steps) if until is None else until
        for i in range(stop):
            if not self._step_visible_with(i, flags):
                continue
            visible.append(i)
            for opt in self._step_options(i):
                if opt.id in self.selected:
                    flags.update(opt.flags)
        return flags, visible

    def _step_options(self, idx: int) -> List[FomodOption]:
        return [o for g in self.steps[idx].groups for o in g.options]

    def flags_before(self, idx: int) -> Dict[str, str]:
        return self._walk(idx)[0]

    @property
    def active_flags(self) -> Dict[str, str]:
        return self._walk()[0]

    def visible_step_indices(self) -> List[int]:
        return self._walk()[1]

    def is_step_visible(self, idx: int) -> bool:
        return self._step_visible_with(idx, self.flags_before(idx))

    def step_index_of(self, option_id: str) -> int:
        for i, step in enumerate(self.steps):
            if any(o.id == option_id for g in step.groups for o in g.options):
                return i
        return -1

    # ------------------------------------------------------------------ types d'options

    def option_type(self, opt: FomodOption, step_idx: Optional[int] = None) -> str:
        if step_idx is None:
            step_idx = self.step_index_of(opt.id)
        flags = self.flags_before(step_idx) if step_idx >= 0 else self.active_flags
        return compute_option_type(opt, self.installed_basenames, flags)

    def is_locked(self, opt: FomodOption, group: FomodGroup, step_idx: Optional[int] = None) -> bool:
        """Option non modifiable : requise, inutilisable ou groupe « tout sélectionner »."""
        t = self.option_type(opt, step_idx).lower()
        return group.type == GroupType.SelectAll or t in ("required", "notusable")

    # ------------------------------------------------------------------ sélections par défaut

    def _defaults_for_group(self, group: FomodGroup, flags: Dict[str, str]) -> Set[str]:
        types = {o.id: compute_option_type(o, self.installed_basenames, flags).lower() for o in group.options}
        usable = [o for o in group.options if types[o.id] != "notusable"]
        required = [o for o in usable if types[o.id] == "required"]
        recommended = [
            o for o in usable
            if types[o.id] == "recommended" or is_option_recommended(o, self.installed_basenames, flags)
        ]
        # Options justifiées par le dossier Data d'abord : dans un choix unique, le patch du mod
        # détecté passe devant la recommandation générique de l'auteur
        recommended.sort(key=lambda o: not option_matches_installed(o, self.installed_basenames, flags))

        if group.type == GroupType.SelectAll:
            return {o.id for o in group.options}
        if group.type == GroupType.SelectExactlyOne:
            pick = (required or recommended or usable or group.options)[:1]
            return {o.id for o in pick}
        if group.type == GroupType.SelectAtMostOne:
            return {o.id for o in (required or recommended)[:1]}
        if group.type == GroupType.SelectAtLeastOne:
            chosen = required + [o for o in recommended if o not in required]
            return {o.id for o in (chosen or usable[:1] or group.options[:1])}
        # SelectAny
        return {o.id for o in required + [o for o in recommended if o not in required]}

    def _init_step(self, idx: int, flags: Dict[str, str]) -> None:
        for g in self.steps[idx].groups:
            for o in g.options:
                self.selected.discard(o.id)
            self.selected |= self._defaults_for_group(g, flags)

    def reset_defaults(self) -> None:
        """Sélections par défaut de toutes les étapes, dans l'ordre, chacune avec les flags
        produits par les étapes visibles précédentes."""
        self.selected.clear()
        self._touched_steps.clear()
        self._refresh_untouched(after=-1)

    def _refresh_untouched(self, after: int) -> None:
        """Recalcule les sélections par défaut des étapes situées après `after` que l'utilisateur
        n'a pas modifiées, avec les flags à jour (un choix peut changer types et visibilité)."""
        flags = self.flags_before(after + 1) if after >= 0 else {}
        for i in range(after + 1, len(self.steps)):
            if i not in self._touched_steps:
                self._init_step(i, flags)
            if self._step_visible_with(i, flags):
                for opt in self._step_options(i):
                    if opt.id in self.selected:
                        flags.update(opt.flags)

    def set_installed_basenames(self, basenames: Set[str]) -> None:
        self.installed_basenames = set(basenames)
        self.reset_defaults()

    # ------------------------------------------------------------------ interaction

    def toggle(self, opt: FomodOption, group: FomodGroup) -> bool:
        """Clic sur une option. Renvoie False si le clic est refusé par les règles du groupe."""
        step_idx = self.step_index_of(opt.id)
        t = self.option_type(opt, step_idx).lower()
        if group.type == GroupType.SelectAll or t == "required":
            return False
        if t == "notusable" and opt.id not in self.selected:
            return False

        ids = {o.id for o in group.options}
        chosen = self.selected & ids
        if group.type == GroupType.SelectExactlyOne:
            if opt.id in chosen:
                return False
            self.selected -= ids
            self.selected.add(opt.id)
        elif group.type == GroupType.SelectAtMostOne:
            was = opt.id in chosen
            self.selected -= ids
            if not was:
                self.selected.add(opt.id)
        elif group.type == GroupType.SelectAtLeastOne:
            if opt.id in chosen:
                if len(chosen) == 1:
                    return False
                self.selected.discard(opt.id)
            else:
                self.selected.add(opt.id)
        else:  # SelectAny
            if opt.id in chosen:
                self.selected.discard(opt.id)
            else:
                self.selected.add(opt.id)
        self._touched_steps.add(step_idx)
        self._refresh_untouched(after=step_idx)
        return True

    def is_selected(self, opt: FomodOption) -> bool:
        return opt.id in self.selected

    # ------------------------------------------------------------------ résultat

    def selected_options(self) -> List[FomodOption]:
        """Options cochées des étapes visibles, dans l'ordre d'installation."""
        visible = self.visible_step_indices()
        return [o for i in visible for o in self._step_options(i) if o.id in self.selected]

    def forced_items(self) -> List[Tuple[FomodFileItem | FomodFolderItem, str]]:
        """Fichiers alwaysInstall / installIfUsable des options non cochées des étapes visibles."""
        out: List[Tuple[FomodFileItem | FomodFolderItem, str]] = []
        for i in self.visible_step_indices():
            flags = self.flags_before(i)
            for opt in self._step_options(i):
                if opt.id in self.selected:
                    continue
                usable = compute_option_type(opt, self.installed_basenames, flags).lower() != "notusable"
                for item in [*opt.files, *opt.folders]:
                    if item.always_install or (item.install_if_usable and usable):
                        out.append((item, opt.name))
        return out

    def build_staging(self, archive_index: ArchiveIndex) -> StagingResult:
        return build_staging(
            selected_options=self.selected_options(),
            required_files=self.required_files,
            archive_index=archive_index,
            conditional_installs=self.conditional_installs,
            active_flags=self.active_flags,
            installed_basenames=self.installed_basenames,
            forced_items=self.forced_items(),
        )
