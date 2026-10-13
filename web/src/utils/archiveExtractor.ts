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

const FOMOD_CONFIG_SUFFIX = 'fomod/moduleconfig.xml';

/**
 * Returns ModuleConfig.xml and info.xml from the index, preferring the ones stored
 * in a "fomod/" folder, then the shallowest in the tree.
 */
export async function selectFomodXml(
  filesMap: Map<string, VirtualFileEntry>
): Promise<{ moduleConfigXml: string; infoXml: string }> {
  const pick = async (basename: string): Promise<string> => {
    const rank = (k: string) => {
      const parts = k.split('/');
      return [parts[parts.length - 2] === 'fomod' ? 0 : 1, parts.length] as const;
    };
    const matches = [...filesMap.keys()]
      .filter((k) => k.split('/').pop() === basename)
      .sort((a, b) => {
        const [ra, rb] = [rank(a), rank(b)];
        return ra[0] - rb[0] || ra[1] - rb[1] || a.localeCompare(b);
      });
    for (const k of matches) {
      const entry = filesMap.get(k)!;
      try {
        const blob = entry.blob || (entry.getBlob ? await entry.getBlob() : undefined);
        if (blob) return await blob.text();
      } catch (err) {
        console.warn(`Lecture impossible de ${k}`, err);
      }
    }
    return '';
  };
  return { moduleConfigXml: await pick('moduleconfig.xml'), infoXml: await pick('info.xml') };
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

  // 1. Search for a fomod/ folder holding ModuleConfig.xml, shallowest first
  //    (whole segment only: "my-fomod/" is not a fomod folder)
  const candidates = [...filesMap.keys()].filter(
    (k) => k === FOMOD_CONFIG_SUFFIX || k.endsWith(`/${FOMOD_CONFIG_SUFFIX}`)
  );
  if (candidates.length > 0) {
    const best = candidates.reduce((a, b) => (b.split('/').length < a.split('/').length ? b : a));
    rootPrefix = best.slice(0, -FOMOD_CONFIG_SUFFIX.length);
    if (!rootPrefix) {
      return { files: filesMap, dirs: dirsMap };
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


  const reanchored = reanchorIndex(filesMap, dirsMap);
  const { moduleConfigXml, infoXml } = await selectFomodXml(reanchored.files);

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


  const reanchored = reanchorIndex(filesMap, dirsMap);
  const { moduleConfigXml, infoXml } = await selectFomodXml(reanchored.files);

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
