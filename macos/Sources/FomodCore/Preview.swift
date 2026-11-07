// Choix de l'image d'aperçu d'une option FOMOD (traduction de python_app/fomod/preview.py).
//
// Ordre de préférence :
// 1. l'image déclarée par l'option, si elle lui est propre (pas la même image pour tout le groupe) ;
// 2. sinon, une image tirée des fichiers que l'option installe (capture fournie, puis texture principale) ;
// 3. sinon, l'image déclarée partagée (bannière générique du FOMOD).

import Foundation

public let pictureExts = [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"]
public let textureExts = [".dds", ".tga"]
// Cartes techniques d'une texture (normales, spéculaire, masques…) : pas représentatives
private let rxTechnicalMap = Rx("_(n|msn|s|m|g|p|em|sk|b|bl|rmaos|e|h|mask|spec|norm|normal)\\.(dds|tga)$", ignoreCase: true)
private let rxPreviewHint = Rx("(preview|screenshot|screen|apercu|thumb|sample|cover)", ignoreCase: true)

/// Vrai si plusieurs options du groupe déclarent la même image (bannière générique).
public func declaredImageIsShared(_ group: FomodGroup?, _ opt: FomodOption) -> Bool {
    guard let group = group, let ip = opt.imagePath, !ip.isEmpty else { return false }
    let key = norm(ip).pyLower
    return group.options.filter { o in
        if let p = o.imagePath, !p.isEmpty { return norm(p).pyLower == key }
        return false
    }.count > 1
}

/// Images contenues dans les fichiers et dossiers que l'option installe, de la plus parlante à la moins.
public func optionContentImages(_ index: ArchiveIndex, _ opt: FomodOption) -> [VirtualFileEntry] {
    let exts = pictureExts + textureExts
    var found = OrderedDict<VirtualFileEntry>()
    for f in opt.files {
        if let e = findFileInIndex(index, f.source), e.path.pyLower.hasAnySuffix(exts) { found[e.path.pyLower] = e }
    }
    for fo in opt.folders {
        guard let d = findFolderInIndex(index, fo.source) else { continue }
        var dl = d.pyLower
        while dl.hasSuffix("/") { dl.removeLast() }
        let prefix = d.isEmpty ? "" : dl + "/"
        for (key, e) in index.files.items where key.hasPrefix(prefix) && !key.hasPrefix("fomod/") && key.hasAnySuffix(exts) {
            found[key] = e
        }
    }

    func rank(_ e: VirtualFileEntry) -> [Int] {
        let name = e.path.pyLower
        return [rxPreviewHint.search(name) ? 0 : 1, name.hasAnySuffix(textureExts) ? 1 : 0, rxTechnicalMap.search(name) ? 1 : 0, -e.size]
    }
    return found.values.enumerated().sorted { a, b in
        let ra = rank(a.element), rb = rank(b.element)
        return ra == rb ? a.offset < b.offset : ra.lexicographicallyPrecedes(rb)
    }.map(\.element)
}

/// (image à afficher, image de repli). L'image de repli est la bannière partagée éventuelle.
public func pickPreviewEntries(_ index: ArchiveIndex?, _ opt: FomodOption, group: FomodGroup? = nil)
    -> (VirtualFileEntry?, VirtualFileEntry?) {
    guard let index = index else { return (nil, nil) }
    var declared: VirtualFileEntry?
    if let ip = opt.imagePath, !ip.isEmpty { declared = findImageInIndex(index, ip) }
    if let d = declared, !declaredImageIsShared(group, opt) { return (d, nil) }
    let content = optionContentImages(index, opt)
    if let first = content.first { return (first, declared) }
    return (declared, nil)
}
