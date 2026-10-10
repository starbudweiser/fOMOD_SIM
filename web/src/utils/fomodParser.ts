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

// Case-insensitive lookup in ArchiveIndex with rich prefix and name normalization
export function findFileInIndex(index: ArchiveIndex, src: string): VirtualFileEntry | null {
  if (!src) return null;
  const rawKey = norm(src);
  if (!rawKey) return null;
  const key = rawKey.toLowerCase();

  // 1. Direct exact match
  if (index.files.has(key)) {
    const f = index.files.get(key)!;
    if (!f.path.toLowerCase().includes('__macosx')) {
      if (!f.url && f.blob) {
        try { f.url = URL.createObjectURL(f.blob); } catch {}
      }
      return f;
    }
  }

  // 2. Direct lookup across common prefixes / path variations
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
    if (index.files.has(v)) {
      const f = index.files.get(v)!;
      if (!f.path.toLowerCase().includes('__macosx')) {
        if (!f.url && f.blob) {
          try { f.url = URL.createObjectURL(f.blob); } catch {}
        }
        return f;
      }
    }
  }

  // 3. Suffix match in either direction:
  // a) relKey ends with key (e.g. index has "images/packs/foo.jpg" and key is "packs/foo.jpg" or "foo.jpg")
  // b) key ends with relKey (e.g. key is "fomod/images/foo.jpg" and index has "images/foo.jpg")
  const suffixCands: VirtualFileEntry[] = [];
  const suffixSlashKey = '/' + key;
  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (
      relKey === key ||
      relKey.endsWith(key) ||
      relKey.endsWith(suffixSlashKey) ||
      key.endsWith('/' + relKey) ||
      key.endsWith(relKey)
    ) {
      suffixCands.push(entry);
    }
  }
  if (suffixCands.length > 0) {
    // Sort by shortest path length
    suffixCands.sort((a, b) => a.path.length - b.path.length);
    const chosen = suffixCands[0];
    if (!chosen.url && chosen.blob) {
      try { chosen.url = URL.createObjectURL(chosen.blob); } catch {}
    }
    return chosen;
  }

  // 4. Basename match (si le FOMOD ne spécifie que le nom de fichier final)
  const base = key.split('/').pop();
  if (base) {
    const baseSlash = '/' + base;
    const baseCands: VirtualFileEntry[] = [];
    for (const [relKey, entry] of index.files.entries()) {
      if (relKey.includes('__macosx')) continue;
      if (relKey === base || relKey.endsWith(baseSlash)) {
        baseCands.push(entry);
      }
    }
    if (baseCands.length > 0) {
      baseCands.sort((a, b) => a.path.length - b.path.length);
      const chosen = baseCands[0];
      if (!chosen.url && chosen.blob) {
        try { chosen.url = URL.createObjectURL(chosen.blob); } catch {}
      }
      return chosen;
    }
  }

  // 5. Flexible normalized match (spaces, dashes, underscores, quotes, accents)
  const sanitize = (s: string) =>
    s
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/['"`’]/g, '')
      .replace(/[-_.\s]+/g, '');

  const keyClean = sanitize(key);
  const baseClean = base ? sanitize(base) : '';

  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    const relClean = sanitize(relKey);
    const relBaseClean = sanitize(relKey.split('/').pop() || '');

    if (
      relClean === keyClean ||
      relClean.endsWith(keyClean) ||
      keyClean.endsWith(relClean) ||
      (baseClean && (relBaseClean === baseClean || relClean.endsWith(baseClean)))
    ) {
      if (!entry.url && entry.blob) {
        try { entry.url = URL.createObjectURL(entry.blob); } catch {}
      }
      return entry;
    }
  }

  // 6. Loose match en nettoyant les préfixes numérotés exotiques (ex: "00 Shared", "20 Main")
  const keyStripped = stripNumPrefix(key);
  for (const [relKey, entry] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (stripNumPrefix(relKey) === keyStripped || stripNumPrefix(relKey).endsWith('/' + keyStripped)) {
      if (!entry.url && entry.blob) {
        try { entry.url = URL.createObjectURL(entry.blob); } catch {}
      }
      return entry;
    }
  }

  return null;
}

export function findFolderInIndex(index: ArchiveIndex, src: string): string | null {
  const rawKey = norm(src);
  if (!rawKey) return null;
  const key = rawKey.toLowerCase();

  // 1. Direct exact match
  if (index.dirs.has(key)) {
    const orig = index.dirs.get(key)!;
    if (!orig.toLowerCase().includes('__macosx')) return orig;
  }

  // 2. Suffix match (ex: src="Textures/Ava body" matching "00 Shared/Textures/Ava body")
  const cands: string[] = [];
  const slashKey = '/' + key;
  for (const [relKey, orig] of index.dirs.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (relKey === key || relKey.endsWith(slashKey) || relKey.endsWith(key)) {
      cands.push(orig);
    }
  }
  if (cands.length > 0) {
    cands.sort((a, b) => a.length - b.length);
    return cands[0];
  }

  // 3. Match sans préfixes numériques exotiques (ex: "00 Shared" vs "Shared", "20 Main" vs "Main")
  const keyBn = stripNumPrefix(key);
  const prefixCands: string[] = [];
  for (const [relKey, orig] of index.dirs.entries()) {
    if (relKey.includes('__macosx')) continue;
    const strippedRel = stripNumPrefix(relKey);
    if (strippedRel === keyBn || strippedRel.endsWith('/' + keyBn)) {
      prefixCands.push(orig);
    }
  }
  if (prefixCands.length > 0) {
    prefixCands.sort((a, b) => a.length - b.length);
    return prefixCands[0];
  }

  // 4. Folder contained in files (si le dossier n'a pas été explicitement créé comme entrée séparée)
  for (const [relKey] of index.files.entries()) {
    if (relKey.includes('__macosx')) continue;
    if (relKey.startsWith(key + '/') || relKey.includes('/' + key + '/')) {
      const idx = relKey.indexOf(key);
      const sub = relKey.substring(0, idx + key.length);
      return sub;
    }
  }

  return null;
}

export function parseDependenciesNode(node: Element): FomodDependencies {
  const operator = (node.getAttribute('operator') || 'And') as 'And' | 'Or' | 'Not';
  const fileDependencies: FileDependency[] = [];
  const flagDependencies: FlagDependency[] = [];
  const nestedDependencies: FomodDependencies[] = [];

  for (let i = 0; i < node.children.length; i++) {
    const child = node.children[i];
    const tag = child.localName.toLowerCase();

    if (tag === 'filedependency') {
      const file = child.getAttribute('file') || '';
      const state = (child.getAttribute('state') || 'Active') as 'Active' | 'Inactive';
      if (file) {
        fileDependencies.push({ file: norm(file), state });
      }
    } else if (tag === 'flagdependency') {
      const flag = child.getAttribute('flag') || '';
      const value = child.getAttribute('value') || '';
      if (flag) {
        flagDependencies.push({ flag, value });
      }
    } else if (tag === 'dependencies') {
      nestedDependencies.push(parseDependenciesNode(child));
    }
  }

  return {
    operator,
    fileDependencies,
    flagDependencies,
    nestedDependencies,
  };
}

export function checkFlagValue(currVal: string | undefined, expectedVal: string): boolean {
  const c = (currVal || '').trim().toLowerCase();
  const e = (expectedVal || '').trim().toLowerCase();
  if (!c) {
    return ['inactive', 'false', '0', 'missing', 'none'].includes(e);
  }
  return c === e;
}

export function evaluateDependencies(
  deps: FomodDependencies | undefined,
  installedBasenames: Set<string>,
  activeFlags: Record<string, string>
): boolean {
  if (!deps) return true;

  const results: boolean[] = [];

  for (const fd of deps.fileDependencies) {
    const base = fd.file.replace(/\\/g, '/').split('/').pop()?.trim().toLowerCase() || fd.file.toLowerCase();
    const isInst = installedBasenames.has(base);
    const st = fd.state.toLowerCase();
    if (st === 'active') {
      results.push(isInst);
    } else if (st === 'inactive' || st === 'missing') {
      results.push(!isInst);
    } else {
      results.push(isInst);
    }
  }

  for (const flagDep of deps.flagDependencies) {
    const currVal = activeFlags[flagDep.flag];
    results.push(checkFlagValue(currVal, flagDep.value));
  }

  for (const nested of deps.nestedDependencies) {
    results.push(evaluateDependencies(nested, installedBasenames, activeFlags));
  }

  if (results.length === 0) return true;

  const op = deps.operator.toLowerCase();
  if (op === 'or') {
    return results.some(Boolean);
  } else if (op === 'not') {
    return !results.every(Boolean);
  } else {
    // Default 'and'
    return results.every(Boolean);
  }
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
  // 1. Remove XML declaration or force encoding UTF-8
  let clean = xml.replace(/<\?xml[^>]*\?>/i, '<?xml version="1.0" encoding="UTF-8"?>');
  // 2. Fix unescaped ampersands (e.g. "CBBE & Bodyslide" -> "CBBE &amp; Bodyslide")
  clean = clean.replace(/&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)/g, '&amp;');
  return clean;
}

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

  const parserError = doc.querySelector('parsererror');
  if (parserError) {
    console.warn('Erreur XML standard, tentative en mode HTML permissif...', parserError.textContent);
    try {
      doc = parser.parseFromString(cleanedXml, 'text/html');
    } catch {
      // continuer avec doc d'origine
    }
  }

  const root = doc.documentElement || doc.body;
  const moduleName =
    root.querySelector('moduleName, ModuleName')?.textContent?.trim() ||
    root.getAttribute('name') ||
    root.getAttribute('Name') ||
    'Mod Skyrim';

  const moduleHeaderImgEl = root.querySelector('headerImage, HeaderImage, moduleConfiguration > headerImage, moduleConfiguration > HeaderImage');
  const moduleHeaderImage = extractElementImage(moduleHeaderImgEl) || extractElementImage(root);

  // Read RequiredInstallFiles if present
  const requiredInstallFiles: (FomodFileItem | FomodFolderItem)[] = [];
  const reqNode = root.querySelector('requiredInstallFiles, RequiredInstallFiles');
  if (reqNode) {
    const fileNodes = reqNode.querySelectorAll('file, File');
    fileNodes.forEach(fn => {
      const src = norm(fn.getAttribute('source') || fn.getAttribute('Source'));
      const dst = norm(fn.getAttribute('destination') || fn.getAttribute('Destination'));
      const prio = parseInt(fn.getAttribute('priority') || fn.getAttribute('Priority') || '0', 10);
      if (src) requiredInstallFiles.push({ source: src, destination: dst, priority: prio });
    });
    const folderNodes = reqNode.querySelectorAll('folder, Folder');
    folderNodes.forEach(fn => {
      const src = norm(fn.getAttribute('source') || fn.getAttribute('Source'));
      const dst = norm(fn.getAttribute('destination') || fn.getAttribute('Destination'));
      const prio = parseInt(fn.getAttribute('priority') || fn.getAttribute('Priority') || '0', 10);
      if (src) requiredInstallFiles.push({ source: src, destination: dst, priority: prio });
    });
  }

  // Steps
  const stepElements: Element[] = [];
  const allSteps = doc.querySelectorAll('installStep, InstallStep');
  allSteps.forEach(s => stepElements.push(s));

  // If no installStep tags found, look for standalone groups under optionalFileGroups or moduleConfiguration
  if (stepElements.length === 0) {
    const standaloneGroups = doc.querySelectorAll('optionalFileGroups > group, optionalFileGroups > optionalFileGroup, moduleConfiguration > group');
    if (standaloneGroups.length > 0) {
      // Create a virtual step containing these groups
      const virtualStepEl = doc.createElement('installStep');
      virtualStepEl.setAttribute('name', "Options d'installation");
      const virtualGrpContainer = doc.createElement('optionalFileGroups');
      standaloneGroups.forEach(g => virtualGrpContainer.appendChild(g.cloneNode(true)));
      virtualStepEl.appendChild(virtualGrpContainer);
      stepElements.push(virtualStepEl);
    }
  }

  const rawSteps: FomodStep[] = stepElements.map((stepEl, stepIdx) => {
    const stepName =
      stepEl.getAttribute('name')?.trim() ||
      stepEl.querySelector('name')?.textContent?.trim() ||
      `Étape ${stepIdx + 1}`;

    const stepHeaderImage = extractElementImage(stepEl);

    const groupElements: Element[] = [];
    const children = stepEl.children;
    for (let c = 0; c < children.length; c++) {
      const child = children[c];
      const tag = child.localName.toLowerCase();
      if (tag === 'optionalfilegroups' || tag === 'groups') {
        for (let g = 0; g < child.children.length; g++) {
          groupElements.push(child.children[g]);
        }
      } else if (tag === 'group' || tag === 'optionalfilegroup') {
        groupElements.push(child);
      }
    }

    if (groupElements.length === 0) {
      // Search recursively
      const found = stepEl.querySelectorAll('group, optionalFileGroup');
      found.forEach(g => groupElements.push(g));
    }

    const groups: FomodGroup[] = groupElements.map((grpEl, grpIdx) => {
      const groupName =
        grpEl.getAttribute('name')?.trim() ||
        grpEl.querySelector(':scope > name')?.textContent?.trim() ||
        `Groupe ${grpIdx + 1}`;

      const grpHeaderImage = extractElementImage(grpEl);

      const rawType = (grpEl.getAttribute('type') || 'SelectExactlyOne') as GroupType;
      const type: GroupType = [
        'SelectExactlyOne',
        'SelectAtLeastOne',
        'SelectAtMostOne',
        'SelectAny',
        'SelectAll',
      ].includes(rawType)
        ? rawType
        : 'SelectExactlyOne';

      const pluginElements: Element[] = [];
      const grpChildren = grpEl.children;
      for (let p = 0; p < grpChildren.length; p++) {
        const pch = grpChildren[p];
        const ptag = pch.localName.toLowerCase();
        if (ptag === 'plugins' || ptag === 'options') {
          for (let op = 0; op < pch.children.length; op++) {
            pluginElements.push(pch.children[op]);
          }
        } else if (ptag === 'plugin' || ptag === 'option') {
          pluginElements.push(pch);
        }
      }

      if (pluginElements.length === 0) {
        const found = grpEl.querySelectorAll('plugin, option');
        found.forEach(pl => pluginElements.push(pl));
      }

      const options: FomodOption[] = pluginElements.map((plEl, plIdx) => {
        let optName =
          plEl.getAttribute('name')?.trim() ||
          plEl.querySelector(':scope > name, :scope > text')?.textContent?.trim() ||
          '';

        if (!optName) {
          const fileNode = plEl.querySelector('file, folder');
          if (fileNode) {
            const src = norm(fileNode.getAttribute('source'));
            optName = src.split('/').pop() || `Option ${plIdx + 1}`;
          } else {
            optName = `Option ${plIdx + 1}`;
          }
        }

        const desc = plEl.querySelector('description')?.textContent?.trim() || '';
        const imagePath = extractElementImage(plEl);

        const files: FomodFileItem[] = [];
        plEl.querySelectorAll(':scope > files > file, :scope file').forEach(fn => {
          const s = norm(fn.getAttribute('source'));
          const d = norm(fn.getAttribute('destination'));
          const prio = parseInt(fn.getAttribute('priority') || '0', 10);
          if (s) files.push({ source: s, destination: d, priority: prio });
        });

        const folders: FomodFolderItem[] = [];
        plEl.querySelectorAll(':scope > files > folder, :scope folder').forEach(fn => {
          const s = norm(fn.getAttribute('source'));
          const d = norm(fn.getAttribute('destination'));
          const prio = parseInt(fn.getAttribute('priority') || '0', 10);
          if (s) folders.push({ source: s, destination: d, priority: prio });
        });

        const flags: Record<string, string> = {};
        plEl.querySelectorAll('conditionFlags flag').forEach(flEl => {
          const fn = flEl.getAttribute('name');
          const fv = flEl.getAttribute('value') || 'true';
          if (fn) flags[fn] = fv;
        });

        let dependencies: FomodDependencies | undefined;
        const depEl = plEl.querySelector(
          'dependencies, visible > dependencies, typeDescriptor dependencies'
        );
        if (depEl) {
          dependencies = parseDependenciesNode(depEl);
        }

        let typeDescriptor: string | TypeDescriptor | undefined;
        const tdEl = plEl.querySelector('typeDescriptor');
        if (tdEl) {
          const dtNode = tdEl.querySelector('defaultType');
          const tNode = tdEl.querySelector(':scope > type');
          const defaultType = dtNode?.getAttribute('name') || tNode?.getAttribute('name') || 'Optional';
          const patterns: TypeDescriptorPattern[] = [];
          const patternEls = tdEl.querySelectorAll('patterns > pattern');
          patternEls.forEach(patEl => {
            const patDepEl = patEl.querySelector('dependencies');
            const patDeps = patDepEl ? parseDependenciesNode(patDepEl) : undefined;
            const patTypeEl = patEl.querySelector('type');
            const patTypeName = patTypeEl?.getAttribute('name') || 'Optional';
            patterns.push({ dependencies: patDeps, typeName: patTypeName });
          });
          typeDescriptor = { defaultType, patterns };
        }

        return {
          id: `step-${stepIdx}-grp-${grpIdx}-opt-${plIdx}`,
          name: optName,
          description: desc,
          imagePath,
          files,
          folders,
          flags,
          dependencies,
          typeDescriptor,
        };
      });

      return {
        id: `step-${stepIdx}-grp-${grpIdx}`,
        name: groupName,
        type,
        options,
        headerImage: grpHeaderImage,
        imagePath: grpHeaderImage,
      };
    });

    const fallback = `Étape ${stepIdx + 1}`;
    const derivedLabel = deriveStepLabel(stepName, groups, fallback);

    return {
      id: `step-${stepIdx}`,
      name: stepName,
      derivedLabel,
      groups,
      headerImage: stepHeaderImage,
      imagePath: stepHeaderImage,
    };
  });

  const deduplicated = dedupeSteps(rawSteps);

  if (deduplicated.length === 0) {
    // Si aucune étape n'est définie mais que le mod a été chargé, créer une étape d'accueil/confirmation
    deduplicated.push({
      id: 'step_default',
      name: 'Installation du Mod',
      derivedLabel: 'Options de base',
      groups: [
        {
          id: 'grp_default',
          name: 'Composants du mod',
          type: 'SelectExactlyOne',
          options: [
            {
              id: 'opt_default',
              name: 'Installer les fichiers par défaut',
              description: 'Ce mod est configuré pour une installation automatique sans options personnalisées supplémentaires.',
              files: requiredInstallFiles.filter(f => !f.source.endsWith('/')).map(f => f as FomodFileItem),
              folders: requiredInstallFiles.filter(f => f.source.endsWith('/')).map(f => f as FomodFolderItem),
              flags: {},
              typeDescriptor: 'Required',
            },
          ],
        },
      ],
    });
  }

  const conditionalFileInstalls: ConditionalInstallPattern[] = [];
  const condPatternEls = doc.querySelectorAll('conditionalFileInstalls > patterns > pattern, conditionalFileInstalls pattern');
  condPatternEls.forEach(patEl => {
    const depNode = patEl.querySelector('dependencies');
    const pDeps = depNode ? parseDependenciesNode(depNode) : undefined;
    const pFiles: FomodFileItem[] = [];
    const pFolders: FomodFolderItem[] = [];

    patEl.querySelectorAll('files > file, file').forEach(fn => {
      const s = norm(fn.getAttribute('source'));
      const d = norm(fn.getAttribute('destination'));
      const prio = parseInt(fn.getAttribute('priority') || '0', 10);
      if (s) pFiles.push({ source: s, destination: d, priority: prio });
    });

    patEl.querySelectorAll('files > folder, folder').forEach(fn => {
      const s = norm(fn.getAttribute('source'));
      const d = norm(fn.getAttribute('destination'));
      const prio = parseInt(fn.getAttribute('priority') || '0', 10);
      if (s) pFolders.push({ source: s, destination: d, priority: prio });
    });

    conditionalFileInstalls.push({ dependencies: pDeps, files: pFiles, folders: pFolders });
  });

  return {
    moduleName,
    moduleHeaderImage,
    steps: deduplicated,
    requiredInstallFiles,
    conditionalFileInstalls,
  };
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

export function dedupeSteps(steps: FomodStep[]): FomodStep[] {
  const seenSignatures = new Set<string>();
  const output: FomodStep[] = [];

  for (const step of steps) {
    const sig = step.groups
      .map(g =>
        g.options
          .map(
            o =>
              `${o.name}:` +
              [...o.files.map(f => f.source), ...o.folders.map(fo => fo.source)]
                .sort()
                .join(',')
          )
          .sort()
          .join('|')
      )
      .join('||');

    if (!seenSignatures.has(sig)) {
      seenSignatures.add(sig);
      output.push(step);
    }
  }

  return output;
}

export function parseInfoXml(xmlText: string): FomodMetadata {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, 'application/xml');

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
