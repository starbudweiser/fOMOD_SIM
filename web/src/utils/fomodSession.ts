/**
 * Session d'installation FOMOD (portage de python_app/fomod/session.py).
 *
 * - une étape n'est affichée que si sa condition <visible> est vraie avec les flags posés par les
 *   options cochées des étapes visibles qui la précèdent ;
 * - seules les options des étapes visibles sont installées et posent des flags ;
 * - chaque groupe respecte son type et chaque option son type effectif
 *   (Required, Recommended, Optional, NotUsable, CouldBeUsable).
 *
 * Fonctions pures : l'état est un Set d'identifiants d'options cochées, plus l'ensemble des étapes
 * modifiées à la main (leurs choix ne sont plus recalculés automatiquement).
 */
import {
  ConditionalInstallPattern,
  FomodFileItem,
  FomodFolderItem,
  FomodGroup,
  FomodOption,
  FomodStep,
} from '../types/fomod';
import { computeOptionType, evaluateDependencies, isOptionRecommended, optionMatchesInstalled } from './fomodParser';

export interface SessionState {
  selected: Set<string>;
  touchedSteps: Set<number>;
}

const stepOptions = (step: FomodStep): FomodOption[] => step.groups.flatMap(g => g.options);

function stepVisibleWith(step: FomodStep, installed: Set<string>, flags: Record<string, string>): boolean {
  return evaluateDependencies(step.visibility, installed, flags);
}

/** Parcourt les étapes dans l'ordre : flags et étapes visibles avant l'étape `until`. */
function walk(
  steps: FomodStep[],
  selected: Set<string>,
  installed: Set<string>,
  until: number = steps.length
): { flags: Record<string, string>; visible: number[] } {
  const flags: Record<string, string> = {};
  const visible: number[] = [];
  for (let i = 0; i < until && i < steps.length; i++) {
    if (!stepVisibleWith(steps[i], installed, flags)) continue;
    visible.push(i);
    for (const opt of stepOptions(steps[i])) {
      if (selected.has(opt.id)) Object.assign(flags, opt.flags);
    }
  }
  return { flags, visible };
}

export const flagsBefore = (steps: FomodStep[], selected: Set<string>, installed: Set<string>, idx: number) =>
  walk(steps, selected, installed, idx).flags;

export const activeFlags = (steps: FomodStep[], selected: Set<string>, installed: Set<string>) =>
  walk(steps, selected, installed).flags;

export const visibleStepIndices = (steps: FomodStep[], selected: Set<string>, installed: Set<string>) =>
  walk(steps, selected, installed).visible;

export function stepIndexOf(steps: FomodStep[], optionId: string): number {
  return steps.findIndex(s => s.groups.some(g => g.options.some(o => o.id === optionId)));
}

export function optionType(
  steps: FomodStep[],
  selected: Set<string>,
  installed: Set<string>,
  opt: FomodOption
): string {
  const idx = stepIndexOf(steps, opt.id);
  const flags = idx >= 0 ? flagsBefore(steps, selected, installed, idx) : activeFlags(steps, selected, installed);
  return computeOptionType(opt, installed, flags);
}

/** Option non modifiable : requise, inutilisable ou groupe « tout sélectionner ». */
export function isLocked(
  steps: FomodStep[],
  selected: Set<string>,
  installed: Set<string>,
  opt: FomodOption,
  group: FomodGroup
): boolean {
  const t = optionType(steps, selected, installed, opt).toLowerCase();
  return group.type === 'SelectAll' || t === 'required' || t === 'notusable';
}

function defaultsForGroup(group: FomodGroup, installed: Set<string>, flags: Record<string, string>): string[] {
  const types = new Map(group.options.map(o => [o.id, computeOptionType(o, installed, flags).toLowerCase()]));
  const usable = group.options.filter(o => types.get(o.id) !== 'notusable');
  const required = usable.filter(o => types.get(o.id) === 'required');
  const recommended = usable.filter(
    o => types.get(o.id) === 'recommended' || isOptionRecommended(o, installed, flags)
  );
  // Options justifiées par le dossier Data d'abord : dans un choix unique, le patch du mod détecté
  // passe devant la recommandation générique de l'auteur (tri stable)
  const matched = new Set(recommended.filter(o => optionMatchesInstalled(o, installed, flags)));
  recommended.sort((a, b) => Number(!matched.has(a)) - Number(!matched.has(b)));
  const union = [...required, ...recommended.filter(o => !required.includes(o))];

  switch (group.type) {
    case 'SelectAll':
      return group.options.map(o => o.id);
    case 'SelectExactlyOne': {
      const pick = (required.length ? required : recommended.length ? recommended : usable.length ? usable : group.options)[0];
      return pick ? [pick.id] : [];
    }
    case 'SelectAtMostOne': {
      const pick = (required.length ? required : recommended)[0];
      return pick ? [pick.id] : [];
    }
    case 'SelectAtLeastOne': {
      const chosen = union.length ? union : (usable.length ? usable : group.options).slice(0, 1);
      return chosen.map(o => o.id);
    }
    default:
      return union.map(o => o.id);
  }
}

/** Recalcule les choix par défaut des étapes après `after` que l'utilisateur n'a pas modifiées. */
function refreshUntouched(
  steps: FomodStep[],
  state: SessionState,
  installed: Set<string>,
  after: number
): SessionState {
  const selected = new Set(state.selected);
  const flags = after >= 0 ? walk(steps, selected, installed, after + 1).flags : {};
  for (let i = after + 1; i < steps.length; i++) {
    if (!state.touchedSteps.has(i)) {
      for (const g of steps[i].groups) {
        g.options.forEach(o => selected.delete(o.id));
        defaultsForGroup(g, installed, flags).forEach(id => selected.add(id));
      }
    }
    if (stepVisibleWith(steps[i], installed, flags)) {
      for (const opt of stepOptions(steps[i])) {
        if (selected.has(opt.id)) Object.assign(flags, opt.flags);
      }
    }
  }
  return { selected, touchedSteps: state.touchedSteps };
}

/** Sélections par défaut de toutes les étapes, chacune avec les flags des étapes visibles précédentes. */
export function initialState(steps: FomodStep[], installed: Set<string>): SessionState {
  return refreshUntouched(steps, { selected: new Set(), touchedSteps: new Set() }, installed, -1);
}

/** Clic sur une option. Renvoie le nouvel état, ou null si le clic est refusé par les règles du groupe. */
export function toggleOption(
  steps: FomodStep[],
  state: SessionState,
  installed: Set<string>,
  opt: FomodOption,
  group: FomodGroup
): SessionState | null {
  const stepIdx = stepIndexOf(steps, opt.id);
  const t = optionType(steps, state.selected, installed, opt).toLowerCase();
  if (group.type === 'SelectAll' || t === 'required') return null;
  if (t === 'notusable' && !state.selected.has(opt.id)) return null;

  const selected = new Set(state.selected);
  const ids = group.options.map(o => o.id);
  const chosen = ids.filter(id => selected.has(id));
  const isOn = selected.has(opt.id);

  switch (group.type) {
    case 'SelectExactlyOne':
      if (isOn) return null;
      ids.forEach(id => selected.delete(id));
      selected.add(opt.id);
      break;
    case 'SelectAtMostOne':
      ids.forEach(id => selected.delete(id));
      if (!isOn) selected.add(opt.id);
      break;
    case 'SelectAtLeastOne':
      if (isOn) {
        if (chosen.length === 1) return null;
        selected.delete(opt.id);
      } else {
        selected.add(opt.id);
      }
      break;
    default:
      if (isOn) selected.delete(opt.id);
      else selected.add(opt.id);
  }

  const touchedSteps = new Set(state.touchedSteps);
  touchedSteps.add(stepIdx);
  return refreshUntouched(steps, { selected, touchedSteps }, installed, stepIdx);
}

/** Options cochées des étapes visibles, dans l'ordre d'installation. */
export function selectedOptions(steps: FomodStep[], selected: Set<string>, installed: Set<string>): FomodOption[] {
  return visibleStepIndices(steps, selected, installed).flatMap(i =>
    stepOptions(steps[i]).filter(o => selected.has(o.id))
  );
}

/** Fichiers alwaysInstall / installIfUsable des options non cochées des étapes visibles. */
export function forcedItems(
  steps: FomodStep[],
  selected: Set<string>,
  installed: Set<string>
): { item: FomodFileItem | FomodFolderItem; isFolder: boolean; optionName: string }[] {
  const out: { item: FomodFileItem | FomodFolderItem; isFolder: boolean; optionName: string }[] = [];
  for (const i of visibleStepIndices(steps, selected, installed)) {
    const flags = flagsBefore(steps, selected, installed, i);
    for (const opt of stepOptions(steps[i])) {
      if (selected.has(opt.id)) continue;
      const usable = computeOptionType(opt, installed, flags).toLowerCase() !== 'notusable';
      opt.files.forEach(f => {
        if (f.alwaysInstall || (f.installIfUsable && usable)) out.push({ item: f, isFolder: false, optionName: opt.name });
      });
      opt.folders.forEach(f => {
        if (f.alwaysInstall || (f.installIfUsable && usable)) out.push({ item: f, isFolder: true, optionName: opt.name });
      });
    }
  }
  return out;
}

export type { ConditionalInstallPattern };
