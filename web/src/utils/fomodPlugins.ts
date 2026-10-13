/**
 * Plugins Skyrim (.esp/.esm/.esl) : scan du dossier Data et masters des plugins fournis par le mod
 * (portage de python_app/fomod/plugins.py).
 *
 * Sert à pré-cocher les options dont les plugins sont utilisables avec le Data de l'utilisateur :
 * un patch est recommandé quand tous ses masters extérieurs au mod sont présents dans Data.
 */
import { ArchiveIndex, FomodOption, FomodStep, VirtualFileEntry } from '../types/fomod';
import { VANILLA_MASTERS, findFileInIndex, findFolderInIndex, isPluginName } from './fomodParser';

/** Fichiers qui comptent pour la détection des dépendances (badge « Auto ») */
const DATA_SCAN_EXT = /\.(esp|esm|esl|dll|bsa|ba2)$/i;
/** Dossiers de Data sans plugin : ignorés au scan (ils contiennent l'essentiel des fichiers) */
export const DATA_SCAN_SKIP_DIRS = new Set([
  'textures', 'meshes', 'sound', 'music', 'video', 'scripts', 'source', 'seq', 'strings',
  'lodsettings', 'grass', 'terrain', 'shadersfx', 'interface', 'facegen', 'dialogueviews', '__macosx',
]);

export const isDataScanFile = (name: string) => DATA_SCAN_EXT.test(name);

/** Vrai si un chemin relatif à Data traverse un dossier ignoré au scan. */
export const isInSkippedDataDir = (relPath: string) =>
  relPath.split(/[/\\]/).slice(0, -1).some(seg => DATA_SCAN_SKIP_DIRS.has(seg.toLowerCase()));

/** Noms (minuscules) des plugins, DLL et archives BSA d'un dossier Data (File System Access API). */
export async function scanDataDirHandle(handle: FileSystemDirectoryHandle): Promise<Set<string>> {
  const found = new Set<string>();
  const walk = async (dir: FileSystemDirectoryHandle) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for await (const entry of (dir as any).values()) {
      if (entry.kind === 'file') {
        if (isDataScanFile(entry.name)) found.add(entry.name.toLowerCase());
      } else if (!DATA_SCAN_SKIP_DIRS.has(entry.name.toLowerCase())) {
        await walk(entry);
      }
    }
  };
  await walk(handle);
  return found;
}

/** Masters (sous-enregistrements MAST de l'en-tête TES4) d'un plugin Skyrim, en minuscules. */
export function parsePluginMasters(data: Uint8Array): string[] {
  if (data.length < 24 || String.fromCharCode(...data.subarray(0, 4)) !== 'TES4') return [];
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const end = Math.min(24 + view.getUint32(4, true), data.length);
  const decoder = new TextDecoder('windows-1252');
  const masters: string[] = [];
  let pos = 24;
  let bigSize: number | null = null;
  while (pos + 6 <= end) {
    const sub = String.fromCharCode(...data.subarray(pos, pos + 4));
    let size = view.getUint16(pos + 4, true);
    pos += 6;
    if (bigSize !== null) {
      size = bigSize;
      bigSize = null;
    }
    if (sub === 'XXXX') {
      bigSize = view.getUint32(pos, true);
    } else if (sub === 'MAST') {
      const raw = data.subarray(pos, pos + size);
      const zero = raw.indexOf(0);
      const name = decoder.decode(zero >= 0 ? raw.subarray(0, zero) : raw).trim();
      if (name) masters.push(name.toLowerCase());
    }
    pos += size;
  }
  return masters;
}

/** Plugins que l'option installe (fichiers directs et contenu de ses dossiers). */
export function optionPluginEntries(index: ArchiveIndex, opt: FomodOption): VirtualFileEntry[] {
  const found = new Map<string, VirtualFileEntry>();
  for (const f of opt.files) {
    const e = findFileInIndex(index, f.source);
    if (e && isPluginName(e.path)) found.set(e.path.toLowerCase(), e);
  }
  for (const fo of opt.folders) {
    const d = findFolderInIndex(index, fo.source);
    if (d === null) continue;
    const prefix = d ? d.toLowerCase().replace(/\/+$/, '') + '/' : '';
    for (const [key, e] of index.files.entries()) {
      if (key.startsWith(prefix) && !key.startsWith('fomod/') && isPluginName(key)) found.set(key, e);
    }
  }
  return [...found.values()];
}

async function entryBytes(entry: VirtualFileEntry): Promise<Uint8Array | null> {
  if (entry.data) return entry.data;
  try {
    const blob = entry.blob || (entry.getBlob ? await entry.getBlob() : undefined);
    // L'en-tête suffit
    return blob ? new Uint8Array(await blob.slice(0, 1 << 20).arrayBuffer()) : null;
  } catch {
    return null;
  }
}

/**
 * Renseigne `requiredMasters` de chaque option : masters de ses plugins, hors jeu de base et hors
 * plugins fournis par le mod lui-même.
 */
export async function annotateOptionMasters(index: ArchiveIndex, steps: FomodStep[]): Promise<void> {
  const provided = new Set([...index.files.keys()].filter(isPluginName).map(k => k.split('/').pop() || k));
  const cache = new Map<string, string[]>();
  for (const step of steps) {
    for (const grp of step.groups) {
      for (const opt of grp.options) {
        const masters = new Set<string>();
        for (const e of optionPluginEntries(index, opt)) {
          const key = e.path.toLowerCase();
          if (!cache.has(key)) {
            const data = await entryBytes(e);
            cache.set(key, data ? parsePluginMasters(data) : []);
          }
          cache.get(key)!.forEach(m => masters.add(m));
        }
        opt.requiredMasters = [...masters].filter(m => !VANILLA_MASTERS.has(m) && !provided.has(m));
      }
    }
  }
}
