import JSZip from 'jszip';
import { ArchiveIndex, VirtualFileEntry } from '../types/fomod';
import { norm } from './fomodParser';

// Dynamic import of libarchive.js to ensure graceful loading and SSR safety
let libarchiveModule: typeof import('libarchive.js') | null = null;
let libarchiveInitDone = false;

async function getLibArchive() {
  if (!libarchiveModule) {
    libarchiveModule = await import('libarchive.js');
  }
  if (!libarchiveInitDone) {
    libarchiveModule.Archive.init({
      workerUrl: '/libarchive.js/worker-bundle.js',
    });
    libarchiveInitDone = true;
  }
  return libarchiveModule.Archive;
}

export interface ExtractedArchiveResult {
  index: ArchiveIndex;
  moduleConfigXml: string;
  infoXml: string;
}

/**
 * Extracts a ZIP archive using JSZip (lightweight, zero WebAssembly overhead).
 */
/**
 * Detects if the archive contents are wrapped in an enclosing root folder
 * (e.g. "Mitsuriou's Follower Bodies Overhaul7z/fomod/ModuleConfig.xml")
 * and re-anchors the archive index so all paths are relative to the mod's actual root.
 */
export function reanchorIndex(
  filesMap: Map<string, VirtualFileEntry>,
  dirsMap: Map<string, string>
): { files: Map<string, VirtualFileEntry>; dirs: Map<string, string> } {
  let rootPrefix = '';

  // 1. Search for fomod/moduleconfig.xml inside a wrapper directory
  for (const [lowerPath] of filesMap.entries()) {
    const fomodIdx = lowerPath.indexOf('fomod/moduleconfig.xml');
    if (fomodIdx > 0) {
      rootPrefix = lowerPath.substring(0, fomodIdx);
      break;
    }
  }

  // 2. If not found via fomod, check if all files share a common single root folder
  if (!rootPrefix && filesMap.size > 0) {
    const firstKey = filesMap.keys().next().value;
    if (firstKey && firstKey.includes('/')) {
      const cand = firstKey.split('/')[0] + '/';
      let allShare = true;
      for (const k of filesMap.keys()) {
        if (!k.startsWith(cand)) {
          allShare = false;
          break;
        }
      }
      if (allShare) {
        rootPrefix = cand;
      }
    }
  }

  if (!rootPrefix) {
    return { files: filesMap, dirs: dirsMap };
  }

  const prefixSegments = rootPrefix.split('/').filter(Boolean).length;
  const newFiles = new Map<string, VirtualFileEntry>();
  const newDirs = new Map<string, string>();

  for (const [lowerPath, entry] of filesMap.entries()) {
    let newNormPath = entry.path;
    let newLower = lowerPath;
    if (lowerPath.startsWith(rootPrefix)) {
      newLower = lowerPath.slice(rootPrefix.length);
      const parts = entry.path.split('/');
      newNormPath = parts.slice(prefixSegments).join('/');
    }

    newFiles.set(newLower, {
      ...entry,
      path: newNormPath,
    });

    const parts = newNormPath.split('/');
    let cur = '';
    for (let i = 0; i < parts.length - 1; i++) {
      cur = cur ? `${cur}/${parts[i]}` : parts[i];
      newDirs.set(cur.toLowerCase(), cur);
    }
  }

  return { files: newFiles, dirs: newDirs };
}

export async function extractZipArchive(
  file: File,
  onProgress?: (msg: string) => void
): Promise<ExtractedArchiveResult> {
  onProgress?.(`Lecture de l'archive ${file.name}...`);
  const zip = await JSZip.loadAsync(file);
  const filesMap = new Map<string, VirtualFileEntry>();
  const dirsMap = new Map<string, string>();

  let moduleConfigXml = '';
  let infoXml = '';

  const entries = Object.keys(zip.files);
  onProgress?.(`Indexation de ${entries.length} éléments...`);

  for (const rawPath of entries) {
    const zipEntry = zip.files[rawPath];
    if (rawPath.includes('__MACOSX/') || rawPath.endsWith('/.DS_Store') || rawPath === '.DS_Store') {
      continue;
    }

    const normalized = norm(rawPath);
    const lower = normalized.toLowerCase();

    if (zipEntry.dir) {
      dirsMap.set(lower, normalized);
    } else {
      const basename = lower.split('/').pop() || '';
      const ext = lower.split('.').pop() || '';
      const isImg = ['png', 'jpg', 'jpeg', 'bmp', 'webp', 'svg'].includes(ext);
      const isXml = basename === 'moduleconfig.xml' || basename === 'info.xml';

      let blob: Blob | undefined;
      let url: string | undefined;

      // Optimisation majeure : On n'extrait en mémoire que le XML et les images d'aperçu.
      // Tous les autres fichiers lourds (meshes, textures .dds) sont référencés de façon paresseuse.
      if (isXml || isImg) {
        blob = await zipEntry.async('blob');
        if (isImg) {
          url = URL.createObjectURL(blob);
        }
        if (basename === 'moduleconfig.xml') {
          moduleConfigXml = await blob.text();
        } else if (basename === 'info.xml') {
          infoXml = await blob.text();
        }
      }

      const approxSize = (zipEntry as any)._data?.uncompressedSize || blob?.size || 1024;

      filesMap.set(lower, {
        path: normalized,
        isDir: false,
        size: approxSize,
        blob,
        url,
        getBlob: () => zipEntry.async('blob'),
      });

      const parts = normalized.split('/');
      let cur = '';
      for (let i = 0; i < parts.length - 1; i++) {
        cur = cur ? `${cur}/${parts[i]}` : parts[i];
        dirsMap.set(cur.toLowerCase(), cur);
      }
    }
  }

  // Si moduleConfigXml n'a pas été capturé par basename exact, recherche souple
  if (!moduleConfigXml) {
    for (const [k, entry] of filesMap.entries()) {
      if (k.endsWith('moduleconfig.xml')) {
        const rawBlob = entry.blob || (entry.getBlob ? await entry.getBlob() : undefined);
        if (rawBlob) {
          moduleConfigXml = await rawBlob.text();
          break;
        }
      }
    }
  }

  const reanchored = reanchorIndex(filesMap, dirsMap);

  return {
    index: reanchored,
    moduleConfigXml,
    infoXml,
  };
}

/**
 * Extracts RAR, 7Z, TAR, or other complex archives using libarchive.js (WebAssembly libarchive).
 */
export async function extractUniversalArchive(
  file: File,
  onProgress?: (msg: string) => void
): Promise<ExtractedArchiveResult> {
  onProgress?.(`Initialisation du moteur de décompression pour ${file.name}...`);
  const Archive = await getLibArchive();

  onProgress?.(`Ouverture de l'archive ${file.name}...`);
  let archive: any;
  try {
    archive = await Archive.open(file);
  } catch (openErr: any) {
    throw new Error(
      `Impossible d'ouvrir l'archive ${file.name}. Le format ou la compression peut être trop récent (ex: RAR5 récent). Convertissez l'archive en format standard .ZIP ou décompressez-la dans un dossier : ${openErr.message || openErr}`
    );
  }

  const filesMap = new Map<string, VirtualFileEntry>();
  const dirsMap = new Map<string, string>();
  let moduleConfigXml = '';
  let infoXml = '';

  let processedCount = 0;

  const isFileLike = (v: any): boolean => {
    if (!v) return false;
    if (typeof File !== 'undefined' && v instanceof File) return true;
    if (typeof Blob !== 'undefined' && v instanceof Blob) return true;
    return (
      typeof v === 'object' &&
      typeof v.name === 'string' &&
      typeof v.size === 'number' &&
      typeof v.slice === 'function'
    );
  };

  const processFile = async (rawPath: string, fileObj: File | Blob) => {
    if (rawPath.includes('__MACOSX/') || rawPath.endsWith('/.DS_Store') || rawPath === '.DS_Store') {
      return;
    }

    const normalized = norm(rawPath);
    const lower = normalized.toLowerCase();
    const blob: Blob = fileObj;

    let url: string | undefined;
    const ext = lower.split('.').pop() || '';
    if (['png', 'jpg', 'jpeg', 'bmp', 'webp', 'svg'].includes(ext)) {
      url = URL.createObjectURL(blob);
    }

    filesMap.set(lower, {
      path: normalized,
      isDir: false,
      size: blob.size,
      blob,
      url,
    });

    const basename = lower.split('/').pop() || '';
    if (basename === 'moduleconfig.xml' && !moduleConfigXml) {
      try {
        moduleConfigXml = await blob.text();
      } catch (tErr) {
        console.warn('Erreur lecture texte moduleconfig.xml', tErr);
      }
    } else if (basename === 'info.xml' && !infoXml) {
      try {
        infoXml = await blob.text();
      } catch (tErr) {
        console.warn('Erreur lecture texte info.xml', tErr);
      }
    }

    const parts = normalized.split('/');
    let cur = '';
    for (let i = 0; i < parts.length - 1; i++) {
      cur = cur ? `${cur}/${parts[i]}` : parts[i];
      dirsMap.set(cur.toLowerCase(), cur);
    }
  };

  onProgress?.('Extraction et analyse des fichiers de l’archive...');

  // Traiter via extractFiles
  try {
    const extractedTree = await archive.extractFiles(async (entry: { file: File; path: string }) => {
      processedCount++;
      if (processedCount % 15 === 0) {
        onProgress?.(`Extraction en cours : ${processedCount} fichiers traités...`);
      }
      if (entry && entry.file) {
        const rawPath = entry.path ? `${entry.path}/${entry.file.name}` : entry.file.name;
        await processFile(rawPath, entry.file);
      }
    });

    // Parcourir l'arbre extrait
    if (extractedTree && typeof extractedTree === 'object') {
      const traverse = async (node: any, currentPath: string) => {
        if (!node || typeof node !== 'object') return;
        for (const key of Object.keys(node)) {
          const val = node[key];
          const nextPath = currentPath ? `${currentPath}/${key}` : key;
          if (isFileLike(val)) {
            await processFile(nextPath, val);
          } else if (val && typeof val === 'object') {
            await traverse(val, nextPath);
          }
        }
      };
      await traverse(extractedTree, '');
    }
  } catch (extractErr: any) {
    console.error('Erreur extractFiles libarchive:', extractErr);
    throw new Error(
      `Échec lors de l'extraction de l'archive (${extractErr.message || extractErr}). Si le fichier est très volumineux ou compressé en RAR5 récent, convertissez-le en .ZIP ou déposez le dossier décompressé.`
    );
  }

  // Recherche de secours si moduleConfigXml n'a pas été extrait
  if (!moduleConfigXml) {
    for (const [lowerPath, entry] of filesMap.entries()) {
      if (lowerPath.endsWith('moduleconfig.xml') && entry.blob) {
        moduleConfigXml = await entry.blob.text();
        break;
      }
    }
  }

  const reanchored = reanchorIndex(filesMap, dirsMap);

  return {
    index: reanchored,
    moduleConfigXml,
    infoXml,
  };
}

/**
 * Universal archive dispatcher for .zip, .rar, .7z, .tar, .gz, etc.
 */
export async function extractAnyArchive(
  file: File,
  onProgress?: (msg: string) => void
): Promise<ExtractedArchiveResult> {
  const name = file.name.toLowerCase();

  // For ZIP files, JSZip is faster and zero-overhead
  if (name.endsWith('.zip')) {
    try {
      return await extractZipArchive(file, onProgress);
    } catch (zipErr) {
      console.warn('JSZip a échoué sur ce ZIP, basculement vers libarchive WASM :', zipErr);
      return await extractUniversalArchive(file, onProgress);
    }
  }

  // For .rar, .7z, .tar, .bz2, .gz etc.
  return await extractUniversalArchive(file, onProgress);
}
