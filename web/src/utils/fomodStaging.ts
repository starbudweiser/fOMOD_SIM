import JSZip from 'jszip';
import {
  ArchiveIndex,
  FomodOption,
  StagingItem,
  StagingResult,
  FomodFileItem,
  FomodFolderItem,
  ConditionalInstallPattern,
  VirtualFileEntry,
} from '../types/fomod';
import { findFileInIndex, findFolderInIndex, norm, evaluateDependencies, isFolderItem } from './fomodParser';

/**
 * Calcule le chemin de destination normalisé pour un fichier extrait via FOMOD.
 * Corrige spécifiquement le bug où destination="MyPlugin.esp" créait "MyPlugin.esp/MyPlugin.esp".
 */
export function resolveFileDestination(rawDst: string, srcPath: string): string {
  const cleanDst = norm(rawDst).replace(/^\/+/, '').replace(/\/+$/, '');
  const fileName = srcPath.split(/[/\\]/).pop() || 'file';

  // Si pas de destination spécifiée, le fichier va à la racine de Data
  if (!cleanDst) {
    return fileName;
  }

  const cleanDstLower = cleanDst.toLowerCase();
  const fileNameLower = fileName.toLowerCase();

  // 1. Si la destination spécifiée se termine déjà par le nom du fichier
  // Ex: destination="CBBE_RaceMenu_Morphs.esp" pour source="05 Patches/CBBE_RaceMenu_Morphs.esp"
  // Ou: destination="SKSE/Plugins/CharGen/Overlays.ini"
  if (cleanDstLower === fileNameLower || cleanDstLower.endsWith('/' + fileNameLower)) {
    return cleanDst;
  }

  // 2. Si la destination se termine par une extension de fichier explicite
  // Ex: .esp, .esm, .esl, .dds, .nif, .ini, .txt, .xml, .dll, etc.
  if (/\.[a-z0-9_-]{2,6}$/i.test(cleanDst)) {
    return cleanDst;
  }

  // 3. Sinon, destination est un répertoire cible (ex: "meshes/actors" ou "textures"),
  // on y place le fichier
  return norm(`${cleanDst}/${fileName}`);
}

/**
 * Calcule le chemin relatif de destination normalisé pour une entrée de dossier extrait via FOMOD.
 */
export function resolveFolderEntryDestination(
  rawDst: string,
  entryPath: string,
  srcDir: string
): string {
  const cleanDst = norm(rawDst).replace(/^\/+/, '').replace(/\/+$/, '');
  // On extrait le chemin relatif à l'intérieur du dossier source
  const relativeInside = norm(entryPath.slice(srcDir.length)).replace(/^\/+/, '');

  if (!cleanDst) {
    return relativeInside;
  }
  return norm(`${cleanDst}/${relativeInside}`);
}

export function buildStaging(
  selectedOptions: FomodOption[],
  requiredFiles: (FomodFileItem | FomodFolderItem)[],
  archiveIndex: ArchiveIndex,
  stagingDirName: string = 'Staging',
  conditionalInstalls?: ConditionalInstallPattern[],
  activeFlags?: Record<string, string>,
  installedBasenames?: Set<string>,
  forcedItems?: { item: FomodFileItem | FomodFolderItem; isFolder: boolean; optionName: string }[]
): StagingResult {
  const log: string[] = [];
  const itemsMap = new Map<string, StagingItem>(); // dest lower -> item
  let copied = 0;
  let missing = 0;
  let totalSize = 0;

  /** Ajoute un fichier au staging ; une priorité inférieure ne remplace pas l'existant. */
  const stage = (entry: VirtualFileEntry, target: string, optName: string, priority: number): boolean => {
    const targetLower = target.toLowerCase();
    const existing = itemsMap.get(targetLower);
    if (existing && priority < (existing.priority || 0)) {
      log.push(`  [ignoré] ${entry.path} -> ${target} (prio ${priority} < ${existing.priority})`);
      return false;
    }
    const sz = entry.size || entry.data?.length || 1024;
    if (!existing) {
      copied++;
      totalSize += sz;
    } else {
      totalSize += sz - existing.size;
    }
    log.push(`  [+ fichier] ${entry.path} -> ${target} (prio: ${priority})`);
    itemsMap.set(targetLower, {
      sourcePath: entry.path,
      destinationPath: target,
      type: 'file',
      size: sz,
      matchedFromOption: optName,
      priority,
      blob: entry.blob,
      getBlob: entry.getBlob,
      data: entry.data,
    });
    return true;
  };

  const processNode = (
    tag: 'file' | 'folder',
    rawSrc: string,
    rawDst: string,
    optName: string,
    priority: number = 0
  ) => {
    const src = norm(rawSrc);
    const srcFile = findFileInIndex(archiveIndex, src);
    const srcDir = findFolderInIndex(archiveIndex, src);
    const cleanDst = norm(rawDst).replace(/^\/+/, '').replace(/\/+$/, '');

    // Uniquement le contenu de CE dossier (pas d'un homonyme ailleurs dans l'archive) ;
    // la racine du mod (source vide) n'inclut pas l'installeur lui-même.
    const copyFolderFiles = (dirPath: string): number => {
      let subCopied = 0;
      const dirLower = dirPath.toLowerCase().replace(/\/+$/, '');
      const prefix = dirLower ? dirLower + '/' : '';
      for (const [key, entry] of archiveIndex.files.entries()) {
        if (entry.isDir || key.includes('__macosx')) continue;
        if (prefix && !key.startsWith(prefix)) continue;
        if (!prefix && key.startsWith('fomod/')) continue;
        const relativeInside = entry.path.slice(prefix.length).replace(/^\/+/, '');
        const target = cleanDst
          ? (relativeInside ? norm(`${cleanDst}/${relativeInside}`) : cleanDst)
          : relativeInside || entry.path.split('/').pop() || 'file';
        if (stage(entry, target, optName, priority)) subCopied++;
      }
      return subCopied;
    };

    const stageFile = (entry: VirtualFileEntry) =>
      stage(entry, resolveFileDestination(rawDst, entry.path), optName, priority);

    if (tag === 'file' && srcFile) {
      stageFile(srcFile);
    } else if (srcDir !== null) {
      // <folder>, ou <file> pointant vers un dossier
      const subCopied = copyFolderFiles(srcDir);
      log.push(`  [+ dossier] ${srcDir || '.'} -> ${rawDst || '.'} (${subCopied} fichier(s))`);
    } else if (srcFile) {
      // <folder> pointant vers un fichier individuel
      stageFile(srcFile);
    } else {
      missing++;
      log.push(`  [manquant] (${tag === 'file' ? 'fichier' : 'dossier'}) ${src}`);
    }
  };

  const processItem = (item: FomodFileItem | FomodFolderItem, isFolder: boolean, optName: string) =>
    processNode(isFolder ? 'folder' : 'file', item.source, item.destination, optName, item.priority || 0);

  // 1. Fichiers requis (requiredInstallFiles)
  if (requiredFiles.length > 0) {
    log.push('[Fichiers Requis (requiredInstallFiles)]');
    for (const req of requiredFiles) processItem(req, isFolderItem(req), 'Requis');
  }

  // 2. Options sélectionnées
  for (const opt of selectedOptions) {
    log.push(`\n[${opt.name}]`);
    opt.files.forEach(f => processItem(f, false, opt.name));
    opt.folders.forEach(f => processItem(f, true, opt.name));
  }

  // 2 bis. Fichiers installés même sans sélection (alwaysInstall / installIfUsable)
  if (forcedItems && forcedItems.length > 0) {
    log.push('\n[Fichiers toujours installés (alwaysInstall / installIfUsable)]');
    for (const f of forcedItems) processItem(f.item, f.isFolder, f.optionName);
  }

  // 3. Installations conditionnelles (conditionalFileInstalls)
  if (conditionalInstalls && conditionalInstalls.length > 0) {
    const flags = activeFlags || {};
    const instFiles = installedBasenames || new Set<string>();
    log.push('\n[Installations Conditionnelles (conditionalFileInstalls)]');
    conditionalInstalls.forEach((cPat, idx) => {
      if (!evaluateDependencies(cPat.dependencies, instFiles, flags)) return;
      const name = `Conditionnel #${idx + 1}`;
      cPat.files.forEach(f => processItem(f, false, name));
      cPat.folders.forEach(f => processItem(f, true, name));
    });
  }

  const items = Array.from(itemsMap.values()).sort((a, b) =>
    a.destinationPath.toLowerCase().localeCompare(b.destinationPath.toLowerCase())
  );
  log.push(`\n--- Résumé ---\n${copied} fichier(s) copié(s), ${missing} manquant(s)`);

  return {
    items,
    log,
    totalCopied: copied,
    totalMissing: missing,
    totalSize,
    stagingDirName,
  };
}

/**
 * Contenu d'un fichier du staging : chargé en mémoire, sinon lu dans l'archive. Un fichier d'un
 * mod de démonstration (virtuel, sans contenu ni archive) reçoit un texte explicatif.
 * null : contenu illisible — le fichier n'est pas écrit plutôt que d'être écrit vide.
 */
async function itemContent(item: StagingItem): Promise<Blob | string | null> {
  if (item.blob) return item.blob;
  if (item.data) return new Blob([item.data as BlobPart]);
  if (item.getBlob) {
    try {
      const blob = await item.getBlob();
      return blob.size > 0 || item.size === 0 ? blob : null;
    } catch {
      return null;
    }
  }
  return `// Fichier de démonstration généré par fOMODSIM : ${item.destinationPath}\n// Source : ${item.sourcePath}\n// Option : ${item.matchedFromOption}\n`;
}

export async function exportStagingAsZip(
  stagingResult: StagingResult
): Promise<{ blob: Blob; failures: string[] }> {
  const zip = new JSZip();
  const failures: string[] = [];

  // Ajouter install_log.txt
  zip.file('install_log.txt', stagingResult.log.join('\n'));

  // Ajouter tous les fichiers avec arborescence exacte
  for (const item of stagingResult.items) {
    const content = await itemContent(item);
    if (content === null) failures.push(item.destinationPath);
    else zip.file(item.destinationPath, content);
  }

  const blob = await zip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
  return { blob, failures };
}

/**
 * Écrit directement l'arborescence des fichiers du Staging sur le disque dur local
 * via la File System Access API (navigateurs modernes sur Desktop).
 * Les fichiers sont copiés DIRECTEMENT dans le dossier sélectionné par l'utilisateur,
 * sans créer de sous-dossier "Staging" superflu.
 */
export async function writeStagingToLocalDirectoryHandle(
  targetDirectoryHandle: FileSystemDirectoryHandle,
  stagingResult: StagingResult
): Promise<{ success: boolean; writtenCount: number; destinationFolderName: string; failures: string[] }> {
  const getTargetDirHandle = async (relPath: string): Promise<FileSystemDirectoryHandle> => {
    const parts = relPath.split(/[/\\]/).filter(Boolean);
    let current = targetDirectoryHandle;
    for (const part of parts) {
      current = await current.getDirectoryHandle(part, { create: true });
    }
    return current;
  };

  // 1. Écrire install_log.txt directement à la racine du dossier choisi
  const logFileHandle = await targetDirectoryHandle.getFileHandle('install_log.txt', { create: true });
  const logWritable = await logFileHandle.createWritable();
  await logWritable.write(stagingResult.log.join('\n'));
  await logWritable.close();

  // 2. Écrire chaque fichier directement dans l'arborescence du dossier choisi
  let count = 0;
  const failures: string[] = [];
  for (const item of stagingResult.items) {
    const content = await itemContent(item);
    if (content === null) {
      failures.push(item.destinationPath);
      continue;
    }
    const parts = item.destinationPath.split(/[/\\]/);
    const fileName = parts.pop() || 'file';
    const dirHandle = await getTargetDirHandle(parts.join('/'));
    const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(content);
    await writable.close();
    count++;
  }

  return {
    success: failures.length === 0,
    writtenCount: count,
    destinationFolderName: targetDirectoryHandle.name,
    failures,
  };
}

/** Texte d'alerte listant les fichiers que l'export n'a pas pu écrire. */
export function formatExportFailures(failures: string[], title: string, message: string): string {
  const shown = failures.slice(0, 15).join('\n');
  const more = failures.length > 15 ? `\n… (+${failures.length - 15})` : '';
  return `${title.replace('{count}', String(failures.length))}\n\n${message}\n\n${shown}${more}`;
}

// Noms d'archives Nexus (téléchargement manuel, Vortex, collections), suffixes à retirer
// (portage de staging.clean_archive_name) :
/** récent : « <nom> <id> <version> 2026-09-15T13-16Z <code> » */
const NEXUS_NEW = /\s+\d{2,7}\s+\S+\s+\d{4}-\d{2}-\d{2}T\d{2}-\d{2}Z(?:\s+[0-9A-Za-z_-]+)?$/;
/** ancien : « <nom>-<id>-<version…>[-<horodatage>] » */
const NEXUS_OLD = /-\d{3,7}(?:-[0-9A-Za-z.]+){1,6}$/;
/** collections : « <nom_avec_tirets_bas>_<version>_<code de 9 caractères> » */
const NEXUS_UNDERSCORE = /(?:_[0-9][0-9.]*)*_[0-9A-Za-z]{9}$/;
/** tronqué : « <nom>-<id>- » */
const NEXUS_TRUNCATED = /-\d{3,7}-$/;
/** copie du navigateur : « … (1) » */
const DUPLICATE_MARK = /\s*\(\d{1,2}\)$/;
const ARCHIVE_EXTS = ['.tar.gz', '.tar.bz2', '.zip', '.7z', '.rar', '.tar', '.tgz', '.gz', '.bz2'];

/**
 * Nom lisible d'une archive de mod (sans extension) : retire l'identifiant, la version,
 * l'horodatage et le code ajoutés par Nexus, ainsi que la marque de copie « (1) ».
 */
export function cleanArchiveName(base: string): string {
  for (const candidate of [base, base.replace(DUPLICATE_MARK, '')]) {
    if (NEXUS_NEW.test(candidate)) return candidate.replace(NEXUS_NEW, '');
    if (NEXUS_OLD.test(candidate)) return candidate.replace(NEXUS_OLD, '');
    if (!candidate.includes(' ') && candidate.includes('_') && NEXUS_UNDERSCORE.test(candidate)) {
      const stripped = candidate.replace(NEXUS_UNDERSCORE, '');
      if (stripped) return stripped.replace(/_/g, ' ');
    }
    if (NEXUS_TRUNCATED.test(candidate)) return candidate.replace(NEXUS_TRUNCATED, '');
  }
  return base;
}

/**
 * Nom du dossier de staging d'un mod (portage de staging.staging_folder_name) : nom de l'archive
 * (ou du dossier) nettoyé des ajouts de Nexus, sinon nom du mod, en majuscules. Deux variantes
 * d'un même mod (16-9 / 16-10…) ont souvent le même nom de mod, mais des archives distinctes.
 */
export function stagingFolderName(sourceName: string | null, modName = '', isArchive = true): string {
  let name = '';
  if (sourceName) {
    let base = sourceName.split(/[/\\]/).filter(Boolean).pop() || '';
    if (isArchive) {
      const ext = ARCHIVE_EXTS.find(e => base.toLowerCase().endsWith(e));
      if (ext) base = base.slice(0, -ext.length);
      name = cleanArchiveName(base) || base;
    } else {
      name = base;
    }
  }
  // eslint-disable-next-line no-control-regex
  name = (name || modName || 'Mod FOMOD').replace(/[/\\:*?"<>|\x00-\x1f]+/g, '-');
  name = name.replace(/\s{2,}/g, ' ').replace(/^[ .\-_]+|[ .\-_]+$/g, '');
  return (name || 'Mod FOMOD').toUpperCase();
}

/**
 * Sous-dossier du mod dans le dossier de staging. S'il existe déjà avec du contenu, il est vidé
 * après confirmation (sinon des fichiers d'options décochées depuis resteraient). null : annulé.
 */
export async function prepareModDirectory(
  root: FileSystemDirectoryHandle,
  name: string,
  confirmReplace: () => boolean
): Promise<FileSystemDirectoryHandle | null> {
  let existing: FileSystemDirectoryHandle | null = null;
  try {
    existing = await root.getDirectoryHandle(name);
  } catch {
    existing = null;
  }
  if (existing) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const it = (existing as any).values() as AsyncIterableIterator<unknown>;
    const hasContent = !(await it.next()).done;
    if (hasContent) {
      if (!confirmReplace()) return null;
      await root.removeEntry(name, { recursive: true });
    }
  }
  return root.getDirectoryHandle(name, { create: true });
}
