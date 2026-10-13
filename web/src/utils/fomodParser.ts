import {
  FomodStep,
  FomodGroup,
  FomodOption,
  FomodFileItem,
  FomodFolderItem,
  FomodMetadata,
  FomodDependencies,
  FileDependency,
  FlagDependency,
  DependencyOperator,
  GroupType,
  ArchiveIndex,
  VirtualFileEntry,
  TypeDescriptor,
  TypeDescriptorPattern,
  ConditionalInstallPattern,
} from '../types/fomod';

export function norm(p: string | null | undefined): string {
  if (!p) return '';
  return p
    .replace(/\\/g, '/')
    .trim()
    .replace(/^(\.\/)+/, '')
    .replace(/^\/+|\/+$/g, '');
}

export function stripNumPrefix(name: string): string {
  const base = name.split('/').pop() || name;
  return base.replace(/^\d+\s*[_-]*\s*/, '').toLowerCase();
}

export function isGenericLabel(s: string): boolean {
  if (!s) return true;
  const t = s.trim().toLowerCase();
  const generics = new Set([
    'option', 'options', 'groupe', 'group', 'general', 'misc', 'various',
    'default', 'step', 'étape', 'etape', 'choose', 'selection', 'select',
    'unp', 'cbbe', 'bodytype', 'type',
  ]);
  if (generics.has(t)) return true;
  if (t.startsWith('step ') || t.startsWith('étape ') || t.startsWith('etape ')) return true;
  if (t.length <= 3) return true;
  return false;
}

export function humanizeToken(tok: string): string {
  const t = tok.replace(/[_\-.]+/g, ' ').trim();
  return t
    .split(' ')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

export function extractElementImage(el: Element | null | undefined): string | undefined {
  if (!el) return undefined;

  // 1. Direct attributes on the element itself (e.g. <plugin image="..." Path="..." />)
  for (const attr of ['image', 'imagepath', 'imagePath', 'Path', 'path', 'file', 'File', 'src', 'Src', 'preview', 'previewImage']) {
    const val = el.getAttribute(attr);
    if (val && val.trim()) return norm(val);
  }

  // 2. Immediate or nested children tags (image, Image, headerImage, HeaderImage, previewImage)
  const childNodes = el.querySelectorAll('image, Image, IMAGE, headerImage, HeaderImage, previewImage, PreviewImage');
  for (let i = 0; i < childNodes.length; i++) {
    const ch = childNodes[i];
    for (const attr of ['path', 'Path', 'file', 'File', 'src', 'Src', 'url', 'Url', 'name', 'Name']) {
      const val = ch.getAttribute(attr);
      if (val && val.trim()) return norm(val);
    }
    if (ch.textContent && ch.textContent.trim()) {
      const txt = ch.textContent.trim();
      if (txt.match(/\.(jpe?g|png|bmp|webp|gif|dds)$/i) || txt.includes('/') || txt.includes('\\')) {
        return norm(txt);
      }
    }
  }

  return undefined;
}

function withUrl(entry: VirtualFileEntry): VirtualFileEntry {
  if (!entry.url && entry.blob) {
    try {
      entry.url = URL.createObjectURL(entry.blob);
    } catch {
      // URL d'objet indisponible (environnement sans DOM)
    }
  }
  return entry;
}

// Recherche insensible à la casse dans l'index, avec variantes de préfixes FOMOD.
// Les correspondances par suffixe portent sur des segments entiers (« mod.esp » ne trouve pas « mymod.esp »).
export function findFileInIndex(index: ArchiveIndex, src: string): VirtualFileEntry | null {
  const rawKey = norm(src);
  if (!rawKey) return null;
  const key = rawKey.toLowerCase();

  // 1. Correspondance exacte, puis variantes de préfixes fréquentes
  const variations = [
    key,
    key.replace(/^fomod\//, ''),
    key.replace(/^images\//, ''),
    key.replace(/^fomod\/images\//, 'images/'),
    `fomod/${key}`,
    `images/${key}`,
    `fomod/images/${key}`,
  ];
  for (const v of variations) {
    const f = index.files.get(v);
    if (f && !v.includes('__macosx')) return withUrl(f);
  }

  // 2. Suffixe sur segments entiers, dans les deux sens
  const suffixCands: VirtualFileEntry[] = [];
  const slashKey = '/' + key;
  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (relKey.endsWith(slashKey) || key.endsWith('/' + relKey)) suffixCands.push(entry);
  }
  if (suffixCands.length > 0) {
    suffixCands.sort((a, b) => a.path.length - b.path.length);
    return withUrl(suffixCands[0]);
  }

  // 3. Même nom de fichier ailleurs dans l'archive
  const base = key.split('/').pop() || '';
  if (base) {
    const baseCands: VirtualFileEntry[] = [];
    for (const [relKey, entry] of index.files.entries()) {
      if (relKey.includes('__macosx')) continue;
      if (relKey === base || relKey.endsWith('/' + base)) baseCands.push(entry);
    }
    if (baseCands.length > 0) {
      baseCands.sort((a, b) => a.path.length - b.path.length);
      return withUrl(baseCands[0]);
    }
  }

  // 4. Préfixes numériques ignorés (« 00 Core/x.esp » ↔ « Core/x.esp »)
  const keyStripped = stripNumPrefix(key);
  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    const relStripped = stripNumPrefix(relKey);
    if (relStripped === keyStripped || relStripped.endsWith('/' + keyStripped)) return withUrl(entry);
  }

  return null;
}

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.bmp', '.dds', '.tga', '.webp', '.gif'];

/** Comme findFileInIndex, mais tolère une extension d'image différente de celle déclarée. */
export function findImageInIndex(index: ArchiveIndex, src: string | undefined): VirtualFileEntry | null {
  if (!src) return null;
  const direct = findFileInIndex(index, src);
  if (direct) return direct;
  const key = norm(src).toLowerCase();
  const last = key.split('/').pop() || '';
  const stem = last.includes('.') ? key.slice(0, key.lastIndexOf('.')) : key;
  for (const ext of IMAGE_EXTS) {
    const alt = findFileInIndex(index, stem + ext);
    if (alt) return alt;
  }
  return null;
}

/** Retrouve un dossier de l'archive (casse d'origine). Une source vide désigne la racine du mod. */
export function findFolderInIndex(index: ArchiveIndex, src: string): string | null {
  const rawKey = norm(src);
  if (!rawKey) return '';
  const key = rawKey.toLowerCase();

  // 1. Correspondance exacte
  const exact = index.dirs.get(key);
  if (exact !== undefined && !key.includes('__macosx')) return exact;

  // 2. Dossier implicite déduit des chemins de fichiers
  const prefix = key + '/';
  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.startsWith(prefix) && !relKey.includes('__macosx')) return entry.path.slice(0, rawKey.length);
  }

  // 3. Suffixe sur segments entiers
  const cands: string[] = [];
  for (const [relKey, orig] of index.dirs.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (relKey.endsWith('/' + key) || key.endsWith('/' + relKey)) cands.push(orig);
  }
  if (cands.length > 0) {
    cands.sort((a, b) => a.length - b.length);
    return cands[0];
  }

  // 4. Préfixes numériques ignorés, à parent identique
  const keyBn = stripNumPrefix(key);
  const parentOf = (k: string) => (k.includes('/') ? k.slice(0, k.lastIndexOf('/')) : '');
  const prefixCands: string[] = [];
  for (const [relKey, orig] of index.dirs.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (parentOf(relKey) === parentOf(key) && stripNumPrefix(relKey) === keyBn) prefixCands.push(orig);
  }
  if (prefixCands.length > 0) {
    prefixCands.sort((a, b) => a.length - b.length);
    return prefixCands[0];
  }

  return null;
}

// ---------------------------------------------------------------- lecture XML : utilitaires

const lname = (el: Element) => el.localName.toLowerCase();

function childrenOf(el: Element | null | undefined, ...names: string[]): Element[] {
  if (!el) return [];
  const wanted = new Set(names.map(n => n.toLowerCase()));
  return Array.from(el.children).filter(c => wanted.has(lname(c)));
}

function childOf(el: Element | null | undefined, ...names: string[]): Element | null {
  return childrenOf(el, ...names)[0] || null;
}

/** Lit un attribut sans tenir compte de la casse de son nom. */
function attr(el: Element | null | undefined, name: string): string | null {
  if (!el) return null;
  const direct = el.getAttribute(name);
  if (direct !== null) return direct;
  const lower = name.toLowerCase();
  for (const a of Array.from(el.attributes)) {
    if (a.name.toLowerCase() === lower) return a.value;
  }
  return null;
}

function descendants(root: Element, ...names: string[]): Element[] {
  const wanted = new Set(names.map(n => n.toLowerCase()));
  return Array.from(root.getElementsByTagName('*')).filter(e => wanted.has(lname(e)));
}

// ---------------------------------------------------------------- dépendances

export function parseDependenciesNode(node: Element): FomodDependencies {
  const opRaw = (attr(node, 'operator') || 'And').trim().toLowerCase();
  const operator: DependencyOperator = opRaw === 'or' ? 'Or' : opRaw === 'not' ? 'Not' : 'And';
  const fileDependencies: FileDependency[] = [];
  const flagDependencies: FlagDependency[] = [];
  const nestedDependencies: FomodDependencies[] = [];
  let assumedTrue = 0;

  for (const child of Array.from(node.children)) {
    const tag = lname(child);
    if (tag === 'filedependency') {
      const file = attr(child, 'file') || '';
      const state = (attr(child, 'state') || 'Active') as FileDependency['state'];
      if (file) fileDependencies.push({ file: norm(file), state });
    } else if (tag === 'flagdependency') {
      const flag = attr(child, 'flag') || '';
      if (flag) flagDependencies.push({ flag, value: attr(child, 'value') || '' });
    } else if (tag === 'dependencies') {
      nestedDependencies.push(parseDependenciesNode(child));
    } else if (tag.endsWith('dependency')) {
      // gameDependency, fommDependency, foseDependency… : non simulables, supposées satisfaites
      assumedTrue++;
    }
  }

  return { operator, fileDependencies, flagDependencies, nestedDependencies, assumedTrue };
}

/** <visible> ou <pattern> contiennent les conditions directement ou via un <dependencies>. */
export function parseConditionContainer(node: Element | null | undefined): FomodDependencies | undefined {
  if (!node) return undefined;
  if (lname(node) === 'dependencies') return parseDependenciesNode(node);
  const inner = childrenOf(node, 'dependencies');
  const hasDirect = Array.from(node.children).some(c => lname(c).endsWith('dependency'));
  if (inner.length === 1 && !hasDirect) return parseDependenciesNode(inner[0]);
  return parseDependenciesNode(node);
}

const FLAG_FALSE = ['', 'inactive', 'false', 'missing', '0', 'off', 'none', 'no', 'disabled'];
const FLAG_TRUE = ['active', 'true', '1', 'on', 'yes', 'enabled'];

/** Comparaison exacte d'abord, puis équivalences usuelles On/True/Active. Flag non défini = chaîne vide. */
export function checkFlagValue(currVal: string | undefined, expectedVal: string): boolean {
  const c = (currVal || '').trim();
  const e = (expectedVal || '').trim();
  if (c === e) return true;
  const cl = c.toLowerCase();
  const el = e.toLowerCase();
  if (cl === el) return true;
  if (FLAG_FALSE.includes(el)) return FLAG_FALSE.includes(cl);
  if (FLAG_TRUE.includes(el)) return FLAG_TRUE.includes(cl);
  return false;
}

/** Les plugins présents dans le dossier Data sont considérés comme actifs. */
export function evaluateDependencies(
  deps: FomodDependencies | undefined,
  installedBasenames: Set<string>,
  activeFlags: Record<string, string>
): boolean {
  if (!deps) return true;
  const results: boolean[] = Array(deps.assumedTrue || 0).fill(true);

  for (const fd of deps.fileDependencies) {
    const base = fd.file.replace(/\\/g, '/').split('/').pop()?.trim().toLowerCase() || '';
    const present = installedBasenames.has(base);
    const st = (fd.state || 'Active').toLowerCase();
    if (st === 'missing') results.push(!present);
    else if (st === 'inactive') results.push(false);
    else results.push(present);
  }
  for (const flagDep of deps.flagDependencies) {
    results.push(checkFlagValue(activeFlags[flagDep.flag], flagDep.value));
  }
  for (const nested of deps.nestedDependencies) {
    results.push(evaluateDependencies(nested, installedBasenames, activeFlags));
  }

  if (results.length === 0) return true;
  const op = deps.operator.toLowerCase();
  if (op === 'or') return results.some(Boolean);
  if (op === 'not') return !results.some(Boolean);
  return results.every(Boolean);
}

export function computeOptionType(
  opt: FomodOption,
  installedBasenames: Set<string>,
  activeFlags: Record<string, string>
): string {
  if (!opt.typeDescriptor) {
    return 'Optional';
  }

  if (typeof opt.typeDescriptor === 'string') {
    return opt.typeDescriptor;
  }

  const td = opt.typeDescriptor;
  for (const pat of td.patterns) {
    if (evaluateDependencies(pat.dependencies, installedBasenames, activeFlags)) {
      return pat.typeName;
    }
  }

  return td.defaultType;
}

export function isOptionRecommended(
  opt: FomodOption,
  installedBasenames: Set<string>,
  activeFlags: Record<string, string>
): boolean {
  const computed = computeOptionType(opt, installedBasenames, activeFlags).toLowerCase();
  if (computed === 'recommended' || computed === 'required') {
    return true;
  }

  if (opt.dependencies && opt.dependencies.fileDependencies.length > 0) {
    if (evaluateDependencies(opt.dependencies, installedBasenames, activeFlags)) {
      return true;
    }
  }

  if (installedBasenames.size > 0) {
    for (const f of opt.files) {
      const b = f.source.replace(/\\/g, '/').split('/').pop()?.trim().toLowerCase() || '';
      if (b.endsWith('.esp') || b.endsWith('.esm') || b.endsWith('.esl')) {
        for (const inst of installedBasenames) {
          if (inst.length > 4 && (inst.includes(b) || b.includes(inst))) {
            return true;
          }
        }
      }
    }
  }

  return false;
}


export function sanitizeXml(xml: string): string {
  if (!xml) return '';
  let clean = xml.replace(/^﻿/, '').replace(/\u0000/g, '');
  // La déclaration <?xml encoding="UTF-16"?> est fausse une fois le texte décodé
  clean = clean.replace(/^\s*<\?xml[^>]*\?>/i, '<?xml version="1.0" encoding="UTF-8"?>');
  clean = clean.replace(/[\u0001-\u0008\u000B\u000C\u000E-\u001F]/g, '');
  // Esperluettes nues (« Tops & Bottoms »)
  clean = clean.replace(/&(?!([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)/g, '&amp;');
  return clean;
}

/** Attribut order (Explicit | Ascending | Descending) ; sans attribut, l'ordre du document est conservé (MO2). */
function ordered(elements: Element[], container: Element | null): Element[] {
  const order = (attr(container, 'order') || '').trim().toLowerCase();
  if (order !== 'ascending' && order !== 'descending') return elements;
  const sorted = [...elements].sort((a, b) =>
    (attr(a, 'name') || '').localeCompare(attr(b, 'name') || '', undefined, { sensitivity: 'base' })
  );
  return order === 'descending' ? sorted.reverse() : sorted;
}

const truthy = (v: string | null) => ['true', '1', 'yes'].includes((v || '').trim().toLowerCase());

/** <file>/<folder> d'un conteneur. Destination absente = même chemin que la source ; vide = racine. */
function parseFileList(container: Element | null): (FomodFileItem | FomodFolderItem)[] {
  const out: (FomodFileItem | FomodFolderItem)[] = [];
  if (!container) return out;
  for (const el of descendants(container, 'file', 'folder')) {
    const rawSrc = attr(el, 'source');
    if (rawSrc === null) continue;
    const source = norm(rawSrc);
    const rawDst = attr(el, 'destination');
    const destination = rawDst === null ? source : norm(rawDst);
    const priority = parseInt(attr(el, 'priority') || '0', 10) || 0;
    const item = {
      source,
      destination,
      priority,
      alwaysInstall: truthy(attr(el, 'alwaysInstall')),
      installIfUsable: truthy(attr(el, 'installIfUsable')),
    };
    if (lname(el) === 'file') {
      if (source) out.push(item);
    } else {
      out.push({ ...item, isFolder: true });
    }
  }
  return out;
}

export const isFolderItem = (i: FomodFileItem | FomodFolderItem): boolean => (i as FomodFolderItem).isFolder === true;

function parseTypeDescriptor(plEl: Element): TypeDescriptor | undefined {
  const tdEl = childOf(plEl, 'typeDescriptor');
  if (!tdEl) return undefined;
  const dtEl = childOf(tdEl, 'dependencyType');
  if (dtEl) {
    const defaultType = attr(childOf(dtEl, 'defaultType'), 'name') || 'Optional';
    const patterns: TypeDescriptorPattern[] = childrenOf(childOf(dtEl, 'patterns'), 'pattern').map(patEl => ({
      dependencies: parseConditionContainer(childOf(patEl, 'dependencies')),
      typeName: attr(childOf(patEl, 'type'), 'name') || 'Optional',
    }));
    return { defaultType, patterns };
  }
  const tEl = childOf(tdEl, 'type');
  return tEl ? { defaultType: attr(tEl, 'name') || 'Optional', patterns: [] } : undefined;
}

const textOf = (el: Element | null) => el?.textContent?.trim() || '';

/**
 * Analyse ModuleConfig.xml selon le schéma ModConfig 5.0 (installSteps > installStep >
 * optionalFileGroups > group > plugins > plugin), avec tolérance aux variantes rencontrées.
 */
export function parseModuleConfigXml(xmlText: string): {
  moduleName: string;
  moduleHeaderImage?: string;
  steps: FomodStep[];
  requiredInstallFiles: (FomodFileItem | FomodFolderItem)[];
  conditionalFileInstalls: ConditionalInstallPattern[];
} {
  const cleanedXml = sanitizeXml(xmlText);
  const parser = new DOMParser();
  let doc: Document = parser.parseFromString(cleanedXml, 'application/xml');
  if (doc.querySelector('parsererror')) {
    console.warn('Erreur XML standard, tentative en mode HTML permissif...');
    doc = parser.parseFromString(cleanedXml, 'text/html');
  }
  const root = doc.documentElement;

  const moduleName =
    textOf(childOf(root, 'moduleName')) || textOf(descendants(root, 'moduleName')[0] || null) || attr(root, 'name') || 'Mod Skyrim';
  const moduleHeaderImage = extractElementImage(childOf(root, 'moduleImage') || descendants(root, 'moduleImage', 'headerImage')[0]);

  const requiredInstallFiles = descendants(root, 'requiredInstallFiles').flatMap(n => parseFileList(n));

  const stepsContainer = childOf(root, 'installSteps');
  const stepElements = stepsContainer
    ? ordered(childrenOf(stepsContainer, 'installStep'), stepsContainer)
    : descendants(root, 'installStep');

  const steps: FomodStep[] = stepElements.map((stepEl, stepIdx) => {
    const stepName = (attr(stepEl, 'name') || '').trim() || textOf(childOf(stepEl, 'name')) || `Étape ${stepIdx + 1}`;
    const visibility = parseConditionContainer(childOf(stepEl, 'visible'));

    const groupsContainer = childOf(stepEl, 'optionalFileGroups');
    const groupElements = groupsContainer
      ? ordered(childrenOf(groupsContainer, 'group'), groupsContainer)
      : descendants(stepEl, 'group', 'optionalFileGroup');

    const groups: FomodGroup[] = groupElements.map((grpEl, grpIdx) => {
      const groupName = (attr(grpEl, 'name') || '').trim() || textOf(childOf(grpEl, 'name')) || `Groupe ${grpIdx + 1}`;
      const rawType = (attr(grpEl, 'type') || 'SelectAny').trim().toLowerCase();
      const type: GroupType =
        (['SelectExactlyOne', 'SelectAtLeastOne', 'SelectAtMostOne', 'SelectAny', 'SelectAll'] as GroupType[]).find(
          t => t.toLowerCase() === rawType
        ) || 'SelectAny';

      const pluginsContainer = childOf(grpEl, 'plugins');
      const pluginElements = pluginsContainer
        ? ordered(childrenOf(pluginsContainer, 'plugin'), pluginsContainer)
        : descendants(grpEl, 'plugin', 'option');

      const options: FomodOption[] = pluginElements.map((plEl, plIdx) => {
        const items = parseFileList(childOf(plEl, 'files'));
        const files = items.filter(i => !isFolderItem(i));
        const folders = items.filter(isFolderItem);

        let optName = (attr(plEl, 'name') || '').trim() || textOf(childOf(plEl, 'name', 'text'));
        if (!optName) {
          const first = files[0] || folders[0];
          optName = first ? first.source.split('/').pop() || `Option ${plIdx + 1}` : `Option ${plIdx + 1}`;
        }

        // Flags : <flag name="X">valeur</flag> — la valeur est le texte de la balise
        const flags: Record<string, string> = {};
        for (const flEl of childrenOf(childOf(plEl, 'conditionFlags'), 'flag')) {
          const fname = attr(flEl, 'name');
          if (fname) flags[fname] = flEl.textContent !== null && flEl.textContent !== '' ? flEl.textContent.trim() : attr(flEl, 'value') || '';
        }

        return {
          id: `step-${stepIdx}-grp-${grpIdx}-opt-${plIdx}`,
          name: optName,
          description: textOf(childOf(plEl, 'description')),
          imagePath: extractElementImage(childOf(plEl, 'image')) || extractElementImage(plEl),
          files,
          folders,
          flags,
          // Dépendances directes sur le plugin (hors schéma, vieux FOMOD)
          dependencies: parseConditionContainer(childOf(plEl, 'dependencies')),
          typeDescriptor: parseTypeDescriptor(plEl),
        };
      });

      const grpHeaderImage = extractElementImage(childOf(grpEl, 'image', 'headerImage'));
      return { id: `step-${stepIdx}-grp-${grpIdx}`, name: groupName, type, options, headerImage: grpHeaderImage, imagePath: grpHeaderImage };
    });

    const stepHeaderImage = extractElementImage(childOf(stepEl, 'image', 'headerImage'));
    return {
      id: `step-${stepIdx}`,
      name: stepName,
      derivedLabel: deriveStepLabel(stepName, groups, `Étape ${stepIdx + 1}`),
      groups,
      visibility,
      headerImage: stepHeaderImage,
      imagePath: stepHeaderImage,
    };
  });

  const conditionalFileInstalls: ConditionalInstallPattern[] = [];
  for (const cNode of descendants(root, 'conditionalFileInstalls')) {
    for (const patEl of childrenOf(childOf(cNode, 'patterns'), 'pattern')) {
      const items = parseFileList(childOf(patEl, 'files'));
      conditionalFileInstalls.push({
        dependencies: parseConditionContainer(childOf(patEl, 'dependencies')),
        files: items.filter(i => !isFolderItem(i)),
        folders: items.filter(isFolderItem),
      });
    }
  }

  if (steps.length === 0 && requiredInstallFiles.length > 0) {
    // Mod sans étapes : une étape de confirmation pour installer les fichiers requis
    steps.push({
      id: 'step_default',
      name: 'Installation du Mod',
      derivedLabel: 'Options de base',
      groups: [
        {
          id: 'grp_default',
          name: 'Composants du mod',
          type: 'SelectAll',
          options: [
            {
              id: 'opt_default',
              name: 'Installer les fichiers par défaut',
              description: 'Ce mod est configuré pour une installation automatique sans options personnalisées supplémentaires.',
              files: [],
              folders: [],
              flags: {},
              typeDescriptor: 'Required',
            },
          ],
        },
      ],
    });
  }

  return { moduleName, moduleHeaderImage, steps, requiredInstallFiles, conditionalFileInstalls };
}

export function deriveStepLabel(stepName: string, groups: FomodGroup[], fallback: string): string {
  if (stepName && !isGenericLabel(stepName)) {
    return stepName.trim();
  }

  for (const g of groups) {
    if (g.name && !isGenericLabel(g.name)) {
      return g.name.trim();
    }
  }

  // Count source folders
  const counts = new Map<string, number>();
  for (const g of groups) {
    for (const opt of g.options) {
      for (const item of [...opt.files, ...opt.folders]) {
        const top = item.source.split('/')[0];
        if (top) {
          counts.set(top, (counts.get(top) || 0) + 1);
        }
      }
    }
  }

  let mostCommonTop: string | null = null;
  let maxCount = 0;
  for (const [top, count] of counts.entries()) {
    if (count > maxCount) {
      maxCount = count;
      mostCommonTop = top;
    }
  }

  const firstOptName = groups[0]?.options[0]?.name;
  if (mostCommonTop && !isGenericLabel(mostCommonTop)) {
    const humanized = humanizeToken(mostCommonTop);
    if (firstOptName) return `${humanized} • ${firstOptName}`;
    return humanized;
  }

  if (firstOptName) return firstOptName;
  return fallback;
}

export function parseInfoXml(xmlText: string): FomodMetadata {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(sanitizeXml(xmlText), 'application/xml');

    const getText = (tags: string[]): string => {
      for (const tag of tags) {
        const el = doc.querySelector(tag);
        if (el && el.textContent?.trim()) {
          return el.textContent.trim();
        }
      }
      return '';
    };

    const name = getText(['Name', 'name', 'ModName', 'modname', 'Title', 'title']) || 'Mod Skyrim';
    const author = getText(['Author', 'author', 'Authors', 'authors']) || 'Inconnu';
    const version = getText(['Version', 'version']) || '1.0.0';
    const website = getText(['Website', 'website', 'URL', 'url', 'Homepage', 'homepage', 'Link', 'link']) || '';
    const description =
      getText(['Description', 'description', 'Summary', 'summary', 'Details', 'details']) ||
      '(Aucune description)';

    return { name, author, version, website, description };
  } catch {
    return {
      name: 'Mod Skyrim',
      author: 'Inconnu',
      version: '1.0.0',
      website: '',
      description: '(Impossible de lire info.xml)',
    };
  }
}
