/**
 * Choix de l'image d'aperçu d'une option FOMOD (portage de python_app/fomod/preview.py).
 *
 * Ordre de préférence :
 * 1. l'image déclarée par l'option, si elle lui est propre (pas la même image pour tout le groupe) ;
 * 2. sinon, une image tirée des fichiers que l'option installe (capture fournie en priorité) ;
 * 3. sinon, l'image déclarée partagée (bannière générique du FOMOD).
 *
 * Le navigateur ne lit pas les textures .dds / .tga : seules les images classiques sont retenues.
 */
import { ArchiveIndex, FomodGroup, FomodOption, VirtualFileEntry } from '../types/fomod';
import { findFileInIndex, findFolderInIndex, findImageInIndex, norm } from './fomodParser';

const PICTURE_EXT = /\.(png|jpe?g|bmp|webp|gif|svg)$/i;
const PREVIEW_HINT = /(preview|screenshot|screen|apercu|thumb|sample|cover)/i;

/** Vrai si plusieurs options du groupe déclarent la même image (bannière générique). */
export function declaredImageIsShared(group: FomodGroup | null | undefined, opt: FomodOption): boolean {
  if (!group || !opt.imagePath) return false;
  const key = norm(opt.imagePath).toLowerCase();
  return group.options.filter(o => o.imagePath && norm(o.imagePath).toLowerCase() === key).length > 1;
}

/** Images contenues dans les fichiers et dossiers que l'option installe, de la plus parlante à la moins. */
export function optionContentImages(index: ArchiveIndex, opt: FomodOption): VirtualFileEntry[] {
  const found = new Map<string, VirtualFileEntry>();
  for (const f of opt.files) {
    const e = findFileInIndex(index, f.source);
    if (e && PICTURE_EXT.test(e.path)) found.set(e.path.toLowerCase(), e);
  }
  for (const fo of opt.folders) {
    const d = findFolderInIndex(index, fo.source);
    if (d === null) continue;
    const prefix = d ? d.toLowerCase().replace(/\/+$/, '') + '/' : '';
    for (const [key, e] of index.files.entries()) {
      if (key.startsWith(prefix) && !key.startsWith('fomod/') && PICTURE_EXT.test(key)) found.set(key, e);
    }
  }
  const rank = (e: VirtualFileEntry): [number, number] => [PREVIEW_HINT.test(e.path) ? 0 : 1, -(e.size || 0)];
  return [...found.values()].sort((a, b) => {
    const [ra, rb] = [rank(a), rank(b)];
    return ra[0] - rb[0] || ra[1] - rb[1];
  });
}

/** Image à afficher pour l'option, ou null (l'appelant affiche alors un visuel généré). */
export function pickPreviewEntry(
  index: ArchiveIndex | null,
  opt: FomodOption,
  group?: FomodGroup | null
): VirtualFileEntry | null {
  if (!index) return null;
  const declared = opt.imagePath ? findImageInIndex(index, opt.imagePath) : null;
  const declaredUsable = declared && declared.url ? declared : null;
  if (declaredUsable && !declaredImageIsShared(group, opt)) return declaredUsable;
  const content = optionContentImages(index, opt).filter(e => e.url);
  return content[0] || declaredUsable;
}
