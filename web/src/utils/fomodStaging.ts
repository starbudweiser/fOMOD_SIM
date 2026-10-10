import JSZip from 'jszip';
import {
  ArchiveIndex,
  FomodOption,
  StagingItem,
  StagingResult,
  FomodFileItem,
  FomodFolderItem,
  ConditionalInstallPattern,
} from '../types/fomod';
import { findFileInIndex, findFolderInIndex, norm, evaluateDependencies } from './fomodParser';

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
  installedBasenames?: Set<string>
): StagingResult {
  const log: string[] = [];
  const itemsMap = new Map<string, StagingItem>(); // dest lower -> item
  let copied = 0;
  let missing = 0;
  let totalSize = 0;

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

    const copyFolderFiles = (dirPath: string) => {
      let subCopied = 0;
      const dirLower = dirPath.toLowerCase().replace(/\/+$/, '');
      const dirLowerSlash = dirLower + '/';

      for (const [key, entry] of archiveIndex.files.entries()) {
        if (entry.isDir || key.includes('__macosx')) continue;

        // Vérifier si le fichier se trouve dans ce dossier ou sous-dossier
        let matched = false;
        let relativeInside = '';

        if (key.startsWith(dirLowerSlash)) {
          matched = true;
          relativeInside = entry.path.slice(dirPath.length).replace(/^\/+/, '');
        } else if (key.includes('/' + dirLowerSlash)) {
          const idx = key.indexOf('/' + dirLowerSlash);
          matched = true;
          const matchedPrefixLen = idx + 1 + dirPath.length;
          relativeInside = entry.path.slice(matchedPrefixLen).replace(/^\/+/, '');
        }

        if (matched) {
          const cleanDst = norm(rawDst).replace(/^\/+/, '').replace(/\/+$/, '');
          const target = cleanDst
            ? (relativeInside ? norm(`${cleanDst}/${relativeInside}`) : cleanDst)
            : relativeInside || entry.path.split('/').pop() || 'file';

          const targetLower = target.toLowerCase();
          const existing = itemsMap.get(targetLower);
          if (!existing || priority >= (existing.priority || 0)) {
            const sz = entry.size || 1024;
            if (!existing) {
              totalSize += sz;
              copied++;
            }
            log.push(`  [+ fichier] ${entry.path} -> ${target} (priorité ${priority})`);
            itemsMap.set(targetLower, {
              sourcePath: entry.path,
              destinationPath: target,
              type: 'file',
              size: sz,
              matchedFromOption: optName,
              priority,
              blob: entry.blob,
            });
            subCopied++;
          }
        }
      }
      return subCopied;
    };

    if (tag === 'file') {
      if (srcFile) {
        const cleanDst = resolveFileDestination(rawDst, srcFile.path);
        const cleanDstLower = cleanDst.toLowerCase();
        const existing = itemsMap.get(cleanDstLower);
        if (!existing || priority >= (existing.priority || 0)) {
          const sz = srcFile.size || 1024;
          if (!existing) {
            totalSize += sz;
            copied++;
          }
          log.push(`  [+ fichier] ${srcFile.path} -> ${cleanDst} (priorité ${priority})`);
          itemsMap.set(cleanDstLower, {
            sourcePath: srcFile.path,
            destinationPath: cleanDst,
            type: 'file',
            size: sz,
            matchedFromOption: optName,
            priority,
            blob: srcFile.blob,
          });
        }
      } else if (srcDir) {
        // Cas d'arborescence : balise <file> mais pointant vers un dossier
        const subCopied = copyFolderFiles(srcDir);
        log.push(`  [+ dossier] ${srcDir} -> ${rawDst || '.'} (${subCopied} fichier(s))`);
      } else {
        missing++;
        log.push(`  [manquant] (fichier) ${src}`);
      }
    } else {
      // tag === 'folder'
      if (srcDir) {
        const subCopied = copyFolderFiles(srcDir);
        log.push(`  [+ dossier] ${srcDir} -> ${rawDst || '.'} (${subCopied} fichier(s))`);
      } else if (srcFile) {
        // Balise <folder> mais pointant vers un fichier individuel
        const cleanDst = resolveFileDestination(rawDst, srcFile.path);
        const cleanDstLower = cleanDst.toLowerCase();
        const existing = itemsMap.get(cleanDstLower);
        if (!existing || priority >= (existing.priority || 0)) {
          const sz = srcFile.size || 1024;
          if (!existing) {
            totalSize += sz;
            copied++;
          }
          log.push(`  [+ fichier] ${srcFile.path} -> ${cleanDst} (priorité ${priority})`);
          itemsMap.set(cleanDstLower, {
            sourcePath: srcFile.path,
            destinationPath: cleanDst,
            type: 'file',
            size: sz,
            matchedFromOption: optName,
            priority,
            blob: srcFile.blob,
          });
        }
      } else {
        missing++;
        log.push(`  [manquant] (dossier) ${src}`);
      }
    }
  };

  // Traiter les fichiers requis (requiredInstallFiles)
  if (requiredFiles.length > 0) {
    log.push('\n[Fichiers Requis (requiredInstallFiles)]');
    for (const req of requiredFiles) {
      processNode('source' in req ? 'file' : 'folder', req.source, req.destination, 'Requis', req.priority || 0);
    }
  }

  // Traiter toutes les options sélectionnées
  for (const opt of selectedOptions) {
    log.push(`\n[${opt.name}]`);
    for (const file of opt.files) {
      processNode('file', file.source, file.destination, opt.name, file.priority || 0);
    }
    for (const folder of opt.folders) {
      processNode('folder', folder.source, folder.destination, opt.name, folder.priority || 0);
    }
  }

  // Installations conditionnelles globales (conditionalFileInstalls)
  if (conditionalInstalls && conditionalInstalls.length > 0) {
    const flags = activeFlags || {};
    const instFiles = installedBasenames || new Set<string>();
    log.push('\n[Installations Conditionnelles (conditionalFileInstalls)]');
    for (const cPat of conditionalInstalls) {
      if (evaluateDependencies(cPat.dependencies, instFiles, flags)) {
        for (const file of cPat.files) {
          processNode('file', file.source, file.destination, 'Conditionnel', file.priority || 0);
        }
        for (const folder of cPat.folders) {
          processNode('folder', folder.source, folder.destination, 'Conditionnel', folder.priority || 0);
        }
      }
    }
  }

  const items = Array.from(itemsMap.values());
  const summaryLine = `\n--- Résumé ---\n${copied} fichier(s) copié(s), ${missing} manquant(s)`;
  log.push(summaryLine);

  return {
    items,
    log,
    totalCopied: copied,
    totalMissing: missing,
    totalSize,
    stagingDirName,
  };
}

export async function exportStagingAsZip(stagingResult: StagingResult): Promise<Blob> {
  const zip = new JSZip();

  // Ajouter install_log.txt
  zip.file('install_log.txt', stagingResult.log.join('\n'));

  // Ajouter tous les fichiers avec arborescence exacte
  for (const item of stagingResult.items) {
    if (item.blob) {
      zip.file(item.destinationPath, item.blob);
    } else {
      // Contenu de démonstration si le fichier est issu d'un mod virtuel/simulé
      const dummyContent = `// Fichier généré par Simulateur FOMOD : ${item.destinationPath}\n// Source: ${item.sourcePath}\n// Option: ${item.matchedFromOption}\n`;
      zip.file(item.destinationPath, dummyContent);
    }
  }

  return await zip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
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
): Promise<{ success: boolean; writtenCount: number; destinationFolderName: string }> {
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
  for (const item of stagingResult.items) {
    const parts = item.destinationPath.split(/[/\\]/);
    const fileName = parts.pop() || 'file';
    const relDir = parts.join('/');

    const dirHandle = await getTargetDirHandle(relDir);
    const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
    const writable = await fileHandle.createWritable();

    if (item.blob) {
      await writable.write(item.blob);
    } else {
      await writable.write(
        `// Staged from FOMOD: ${item.sourcePath}\n// Option: ${item.matchedFromOption}\n`
      );
    }
    await writable.close();
    count++;
  }

  return {
    success: true,
    writtenCount: count,
    destinationFolderName: targetDirectoryHandle.name,
  };
}
