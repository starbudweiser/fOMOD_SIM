// Plugins Skyrim (.esp/.esm/.esl) : scan du dossier Data et masters des plugins fournis par le mod
// (traduction de python_app/fomod/plugins.py).

import Foundation

/// Fichiers qui comptent pour la détection des dépendances (badge « Auto »)
public let dataScanExts = pluginExts + [".dll", ".bsa", ".ba2"]
/// Dossiers de Data sans plugin : ignorés au scan
public let dataScanSkipDirs: Set<String> = [
    "textures", "meshes", "sound", "music", "video", "scripts", "source", "seq", "strings",
    "lodsettings", "grass", "terrain", "shadersfx", "interface", "facegen", "dialogueviews",
]

/// Noms (minuscules) des plugins, DLL et archives BSA présents dans un dossier Data (lecture seule).
public func scanDataDir(_ folder: String) -> Set<String> {
    var found = Set<String>()
    walkTree(folder) { _, _, dirs, files in
        dirs = dirs.filter { !dataScanSkipDirs.contains($0.pyLower) }
        for f in files {
            let lower = f.pyLower
            if lower.hasAnySuffix(dataScanExts) { found.insert(lower) }
        }
        return true
    }
    return found
}

private func le32(_ d: [UInt8], _ p: Int) -> Int { Int(d[p]) | Int(d[p + 1]) << 8 | Int(d[p + 2]) << 16 | Int(d[p + 3]) << 24 }
private func le16(_ d: [UInt8], _ p: Int) -> Int { Int(d[p]) | Int(d[p + 1]) << 8 }

/// Décodage cp1252 (octets 0x80-0x9F en caractères Windows ; les cinq octets non définis restent tels quels comme Python « replace »).
func decodeCP1252(_ bytes: ArraySlice<UInt8>) -> String {
    let table: [UInt32] = [0x20AC, 0xFFFD, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0xFFFD, 0x017D, 0xFFFD,
                           0xFFFD, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0xFFFD, 0x017E, 0x0178]
    var s = String.UnicodeScalarView()
    for b in bytes {
        if b >= 0x80 && b < 0xA0 { s.append(Unicode.Scalar(table[Int(b) - 0x80]) ?? "\u{FFFD}") } else { s.append(Unicode.Scalar(b)) }
    }
    return String(s)
}

/// Masters (sous-enregistrements MAST de l'en-tête TES4) d'un plugin Skyrim, en minuscules.
public func parsePluginMasters(_ data: Data) -> [String] {
    let d = [UInt8](data)
    if d.count < 24 || Array(d[0..<4]) != Array("TES4".utf8) { return [] }
    let size = le32(d, 4)
    var pos = 24
    let end = min(24 + size, d.count)
    var masters: [String] = []
    var bigSize: Int?
    while pos + 6 <= end {
        let sub = Array(d[pos..<pos + 4])
        var subSize = le16(d, pos + 4)
        pos += 6
        if let b = bigSize { subSize = b; bigSize = nil }
        if sub == Array("XXXX".utf8) {
            guard pos + 4 <= d.count else { break }  // struct.unpack_from lèverait une erreur
            bigSize = le32(d, pos)
        } else if sub == Array("MAST".utf8) {
            let chunk = d[min(pos, d.count)..<min(pos + subSize, d.count)]
            let name = chunk.prefix { $0 != 0 }
            let n = decodeCP1252(name).pyStrip
            if !n.isEmpty { masters.append(n.pyLower) }
        }
        pos += subSize
    }
    return masters
}

public func entryBytes(_ entry: VirtualFileEntry) -> Data? {
    if let d = entry.data, !d.isEmpty { return d }
    if let p = entry.extractedDiskPath, isFile(p) {
        guard let fh = FileHandle(forReadingAtPath: p) else { return nil }
        defer { try? fh.close() }
        return fh.readData(ofLength: 1 << 20)  // l'en-tête suffit
    }
    return nil
}

/// Plugins que l'option installe (fichiers directs et contenu de ses dossiers).
func optionPluginEntries(_ index: ArchiveIndex, _ opt: FomodOption) -> [VirtualFileEntry] {
    var found = OrderedDict<VirtualFileEntry>()
    for f in opt.files {
        if let e = findFileInIndex(index, f.source), e.path.pyLower.hasAnySuffix(pluginExts) { found[e.path.pyLower] = e }
    }
    for fo in opt.folders {
        guard let d = findFolderInIndex(index, fo.source) else { continue }
        var dl = d.pyLower
        while dl.hasSuffix("/") { dl.removeLast() }
        let prefix = d.isEmpty ? "" : dl + "/"
        for (key, e) in index.files.items where key.hasPrefix(prefix) && !key.hasPrefix("fomod/") && key.hasAnySuffix(pluginExts) {
            found[key] = e
        }
    }
    return found.values
}

/// Renseigne `requiredMasters` de chaque option : masters de ses plugins, hors jeu de base et hors plugins du mod.
public func annotateOptionMasters(_ index: ArchiveIndex, _ steps: [FomodStep], readBytes: (VirtualFileEntry) -> Data? = entryBytes) {
    var provided = Set<String>()
    for k in index.keys where k.hasAnySuffix(pluginExts) { provided.insert(k.lastSlashComponent) }
    var cache: [String: [String]] = [:]
    for step in steps {
        for grp in step.groups {
            for opt in grp.options {
                var masters = Set<String>()
                for e in optionPluginEntries(index, opt) {
                    let key = e.path.pyLower
                    if cache[key] == nil {
                        if let data = readBytes(e), !data.isEmpty { cache[key] = parsePluginMasters(data) } else { cache[key] = [] }
                    }
                    masters.formUnion(cache[key]!)
                }
                opt.requiredMasters = masters.filter { !vanillaMasters.contains($0) && !provided.contains($0) }
            }
        }
    }
}

private extension ArchiveIndex {
    var keys: [String] { files.keys }
}
