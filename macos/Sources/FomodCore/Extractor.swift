// Indexation des archives et dossiers de mods (traduction de python_app/fomod/extractor.py).
//
// Le Python lisait ZIP et TAR par ses modules, le 7Z par py7zr et le RAR par les outils en ligne de commande ; ici
// bsdtar fait tout. Même résultat : mêmes entrées (chemins, casse, tailles), mêmes octets pour les fichiers lus d'office.

import Foundation

public let lightImageExtensions = [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"]
public let fomodConfigSuffix = "fomod/moduleconfig.xml"
/// Au-delà, un fichier « essentiel » n'est pas chargé en mémoire : il est lu à la demande (export, aperçu).
let maxPreloadBytes = 128 * 1024 * 1024

public struct ExtractError: Error, CustomStringConvertible, LocalizedError {
    public let message: String
    public var description: String { message }
    public var errorDescription: String? { message }
}

public struct ExtractedArchive {
    public var index: ArchiveIndex
    public var moduleConfigXML: String
    public var infoXML: String
}

func readEntryBytes(_ entry: VirtualFileEntry) -> Data? {
    if let d = entry.data, !d.isEmpty { return d }
    if let p = entry.extractedDiskPath, FileManager.default.fileExists(atPath: p) { return FileManager.default.contents(atPath: p) }
    return nil
}

/// (ModuleConfig.xml, info.xml) de l'index, en privilégiant ceux rangés dans un dossier « fomod/ », puis le moins profond.
func selectFomodXML(_ files: OrderedDict<VirtualFileEntry>) -> (String, String) {
    func pick(_ basename: String) -> String {
        var matches = files.keys.filter { $0.lastSlashComponent == basename }
        func sortKey(_ k: String) -> (Int, Int, String) {
            let parts = k.pySplit("/")
            let parent = parts.count >= 2 ? parts[parts.count - 2] : nil
            return (parent == "fomod" ? 0 : 1, k.filter { $0 == "/" }.count, k)
        }
        matches = matches.enumerated().sorted { a, b in
            let ka = sortKey(a.element), kb = sortKey(b.element)
            if ka.0 != kb.0 { return ka.0 < kb.0 }
            if ka.1 != kb.1 { return ka.1 < kb.1 }
            return ka.2 == kb.2 ? a.offset < b.offset : ka.2.pyLess(kb.2)
        }.map(\.element)
        for k in matches {
            if let data = readEntryBytes(files[k]!), !data.isEmpty { return decodeXMLText(data) }
        }
        return ""
    }
    return (pick("moduleconfig.xml"), pick("info.xml"))
}

/// Détecte si l'archive ou le dossier est encapsulé dans un dossier racine parent
/// (ex : NomDuMod_v1.0/fomod/ModuleConfig.xml) et réaligne tous les chemins à la racine du FOMOD.
public func reanchorIndex(_ files: OrderedDict<VirtualFileEntry>, _ dirs: OrderedDict<String>) -> (OrderedDict<VirtualFileEntry>, OrderedDict<String>) {
    var rootPrefix = ""

    // 1. Dossier fomod/ contenant ModuleConfig.xml, le moins profond d'abord (segment entier)
    let candidates = files.keys.filter { $0 == fomodConfigSuffix || $0.hasSuffix("/" + fomodConfigSuffix) }
    if !candidates.isEmpty {
        var best = candidates[0]
        var bestDepth = best.filter { $0 == "/" }.count
        for c in candidates.dropFirst() {
            let d = c.filter { $0 == "/" }.count
            if d < bestDepth { best = c; bestDepth = d }
        }
        rootPrefix = String(best.unicodeScalars.dropLast(fomodConfigSuffix.unicodeScalars.count))
        if rootPrefix.isEmpty { return (files, dirs) }
    }

    // 2. Sinon, tous les fichiers partagent un préfixe commun unique
    if rootPrefix.isEmpty, let firstKey = files.keys.first {
        if firstKey.contains("/") {
            let cand = firstKey.pySplit("/")[0] + "/"
            if files.keys.allSatisfy({ $0.hasPrefix(cand) }) { rootPrefix = cand }
        }
    }
    if rootPrefix.isEmpty { return (files, dirs) }

    let prefixSegments = rootPrefix.pySplit("/").filter { !$0.isEmpty }.count
    var newFiles = OrderedDict<VirtualFileEntry>()
    var newDirs = OrderedDict<String>()
    for (lowerPath, entry) in files.items {
        var newNormPath = entry.path
        var newLower = lowerPath
        if lowerPath.hasPrefix(rootPrefix) {
            newLower = lowerPath.pySlice(rootPrefix.pyLen)
            newNormPath = Array(entry.path.pySplit("/").dropFirst(prefixSegments)).joined(separator: "/")
        }
        newFiles[newLower] = VirtualFileEntry(path: newNormPath, isDir: entry.isDir, size: entry.size, data: entry.data,
                                              extractedDiskPath: entry.extractedDiskPath, member: entry.member)
        addParentDirs(of: newNormPath, to: &newDirs)
    }
    return (newFiles, newDirs)
}

/// Ajoute à `dirs` les dossiers parents d'un chemin (clé en minuscules -> casse d'origine).
func addParentDirs(of path: String, to dirs: inout OrderedDict<String>) {
    let parts = path.pySplit("/")
    var cur = ""
    for i in 0..<max(parts.count - 1, 0) {
        cur = cur.isEmpty ? parts[i] : "\(cur)/\(parts[i])"
        dirs[cur.pyLower] = cur
    }
}

/// Fichiers décompressés en mémoire à l'indexation (XML FOMOD, images légères, plugins, INI, textes).
public func isEssentialFile(_ pathLower: String) -> Bool {
    let bn = pathLower.lastSlashComponent
    if bn == "moduleconfig.xml" || bn == "info.xml" { return true }
    if pathLower.contains("fomod/") { return true }
    if bn.hasAnySuffix(lightImageExtensions) { return true }
    if bn.hasAnySuffix([".esp", ".esm", ".esl", ".ini", ".txt"]) { return true }
    return false
}

private func decodeUTF16(_ data: Data, bigEndian: Bool?) -> String? {
    var bytes = [UInt8](data)
    var be = bigEndian ?? false
    if bigEndian == nil {  // « utf-16 » : BOM, sinon petit-boutiste
        if bytes.count >= 2, bytes[0] == 0xFF, bytes[1] == 0xFE { bytes.removeFirst(2) }
        else if bytes.count >= 2, bytes[0] == 0xFE, bytes[1] == 0xFF { bytes.removeFirst(2); be = true }
    }
    if bytes.count % 2 != 0 { return nil }
    var units: [UInt16] = []
    units.reserveCapacity(bytes.count / 2)
    var i = 0
    while i < bytes.count {
        units.append(be ? UInt16(bytes[i]) << 8 | UInt16(bytes[i + 1]) : UInt16(bytes[i + 1]) << 8 | UInt16(bytes[i]))
        i += 2
    }
    // Strict : un substitut isolé est une erreur, comme en Python
    var out = String.UnicodeScalarView()
    var k = 0
    while k < units.count {
        let u = units[k]
        if u >= 0xD800 && u < 0xDC00 {
            guard k + 1 < units.count, units[k + 1] >= 0xDC00, units[k + 1] < 0xE000 else { return nil }
            let v = 0x10000 + ((UInt32(u) - 0xD800) << 10) + (UInt32(units[k + 1]) - 0xDC00)
            guard let sc = Unicode.Scalar(v) else { return nil }
            out.append(sc)
            k += 2
        } else if u >= 0xDC00 && u < 0xE000 {
            return nil
        } else {
            out.append(Unicode.Scalar(UInt32(u))!)
            k += 1
        }
    }
    return String(out)
}

/// Décode du texte XML en gérant UTF-8 avec/sans BOM, UTF-16 et Latin-1.
public func decodeXMLText(_ data: Data) -> String {
    if data.isEmpty { return "" }
    enum Enc { case utf8sig, utf8, utf16, utf16le, utf16be, latin1 }
    var encodings: [Enc] = [.utf8sig, .utf8, .utf16, .latin1]
    let b = [UInt8](data.prefix(4))
    if data.count >= 2, (b[0] == 0xFF && b[1] == 0xFE) || (b[0] == 0xFE && b[1] == 0xFF) {
        encodings.insert(.utf16, at: 0)
    } else if data.count > 3, b[1] == 0, b[3] == 0 {
        encodings.insert(.utf16le, at: 0)
    } else if data.count > 3, b[0] == 0, b[2] == 0 {
        encodings.insert(.utf16be, at: 0)
    }
    for enc in encodings {
        switch enc {
        case .utf8sig, .utf8:
            if var s = String(data: data, encoding: .utf8) {
                if enc == .utf8sig, s.unicodeScalars.first == "\u{FEFF}" { s = String(s.unicodeScalars.dropFirst()) }
                return s
            }
        case .utf16: if let s = decodeUTF16(data, bigEndian: nil) { return s }
        case .utf16le: if let s = decodeUTF16(data, bigEndian: false) { return s }
        case .utf16be: if let s = decodeUTF16(data, bigEndian: true) { return s }
        case .latin1:
            var v = String.UnicodeScalarView()
            for byte in data { v.append(Unicode.Scalar(byte)) }
            return String(v)
        }
    }
    return ""
}

// MARK: - Dossier

public func extractDirectory(_ folderPath: String, progress: ((String) -> Void)? = nil) -> ExtractedArchive {
    progress?("Indexation du dossier \(pyName(folderPath))...")
    var files = OrderedDict<VirtualFileEntry>()
    var dirs = OrderedDict<String>()
    var total = 0

    let root = pyPath(folderPath)
    walkTree(root) { current, rel, _, names in
        for f in names {
            let relPath = norm((rel + [f]).joined(separator: "/"))
            let fullPath = current + "/" + f
            if relPath.pyLower.contains("__macosx") || relPath.hasSuffix(".DS_Store") { continue }
            let lower = relPath.pyLower
            var sz = 0
            var data: Data?
            do {
                let attrs = try FileManager.default.attributesOfItem(atPath: fullPath)
                sz = (attrs[.size] as? NSNumber)?.intValue ?? 0
                if isEssentialFile(lower) {
                    guard let d = FileManager.default.contents(atPath: fullPath) else { continue }
                    data = d
                }
            } catch { continue }
            files[lower] = VirtualFileEntry(path: relPath, isDir: false, size: sz, data: data, extractedDiskPath: fullPath)
            addParentDirs(of: relPath, to: &dirs)
            total += 1
            if total % 50 == 0 { progress?("Indexation : \(total) fichiers analysés...") }
        }
        return true
    }
    let (nf, nd) = reanchorIndex(files, dirs)
    let (cfg, info) = selectFomodXML(nf)
    return ExtractedArchive(index: ArchiveIndex(files: nf, dirs: nd, archivePath: folderPath), moduleConfigXML: cfg, infoXML: info)
}

// MARK: - Archives (bsdtar)

private enum Flavor { case zip, tar, sevenZ, rar }

/// Indexe une archive d'après la liste de bsdtar, puis lit d'office les fichiers essentiels (une seule passe).
private func extractListed(_ archivePath: String, flavor: Flavor, progress: ((String) -> Void)?) throws -> ExtractedArchive {
    guard let listed = listArchive(archivePath) else {
        throw ExtractError(message: "Archive illisible : \(pyName(archivePath))")
    }
    var files = OrderedDict<VirtualFileEntry>()
    var dirs = OrderedDict<String>()
    var toLoad: [String] = []  // clés minuscules des fichiers à lire d'office

    for (idx, item) in listed.enumerated() {
        let raw = item.member
        if flavor == .tar {
            if item.isSymlink { continue }
            if raw.contains("__MACOSX") || raw.hasSuffix(".DS_Store") { continue }
        } else {
            if raw.contains("__MACOSX") || raw.hasSuffix(".DS_Store") { continue }
        }
        let normalized = norm(raw.precomposedStringWithCanonicalMapping)
        let lower = normalized.pyLower

        if item.isDir {
            if flavor != .rar { dirs[lower] = normalized }  // le RAR n'a que les dossiers de ses fichiers
            continue
        }
        if flavor == .rar && (lower.contains("__macosx")) { continue }
        files[lower] = VirtualFileEntry(path: normalized, isDir: false, size: item.size, data: nil, member: raw)
        addParentDirs(of: normalized, to: &dirs)
        if isEssentialFile(lower) && item.size <= maxPreloadBytes { toLoad.append(lower) }
        if idx % 50 == 0 { progress?("Indexation : \(idx)/\(listed.count) éléments...") }
    }

    if !toLoad.isEmpty {
        progress?("Chargement des configurations FOMOD et aperçus...")
        let members = toLoad.compactMap { files[$0]?.member }
        let got = readArchiveMembers(archivePath, members: members)
        for k in toLoad {
            if let e = files[k], let m = e.member, let d = got[m] { e.data = d }
        }
    }

    let (nf, nd) = reanchorIndex(files, dirs)
    let (cfg, info) = selectFomodXML(nf)
    return ExtractedArchive(index: ArchiveIndex(files: nf, dirs: nd, archivePath: archivePath), moduleConfigXML: cfg, infoXML: info)
}

public func extractZip(_ archivePath: String, progress: ((String) -> Void)? = nil) throws -> ExtractedArchive {
    progress?("Ouverture de l'archive ZIP \(pyName(archivePath))...")
    return try extractListed(archivePath, flavor: .zip, progress: progress)
}

public func extractTar(_ archivePath: String, progress: ((String) -> Void)? = nil) throws -> ExtractedArchive {
    progress?("Ouverture de l'archive TAR \(pyName(archivePath))...")
    return try extractListed(archivePath, flavor: .tar, progress: progress)
}

public func extract7z(_ archivePath: String, progress: ((String) -> Void)? = nil) throws -> ExtractedArchive {
    progress?("Analyse de l'archive 7Z \(pyName(archivePath))...")
    do {
        return try extractListed(archivePath, flavor: .sevenZ, progress: progress)
    } catch {
        throw ExtractError(message: "Impossible d'ouvrir l'archive 7Z '\(pyName(archivePath))'. Erreur : \(error)")
    }
}

public func extractRar(_ archivePath: String, progress: ((String) -> Void)? = nil) throws -> ExtractedArchive {
    progress?("Analyse de l'archive RAR \(pyName(archivePath))...")
    do {
        return try extractListed(archivePath, flavor: .rar, progress: progress)
    } catch {
        throw ExtractError(message: "Impossible d'ouvrir l'archive RAR '\(pyName(archivePath))'.\n"
            + "Convertissez l'archive au format .ZIP standard si le problème persiste.")
    }
}

/// Détecteur universel pour dossier, ZIP, 7Z, RAR, TAR, etc.
public func extractArchive(_ fileOrDirPath: String, progress: ((String) -> Void)? = nil) throws -> ExtractedArchive {
    if !FileManager.default.fileExists(atPath: fileOrDirPath) {
        throw ExtractError(message: "Chemin introuvable : \(fileOrDirPath)")
    }
    if isDir(fileOrDirPath) { return extractDirectory(fileOrDirPath, progress: progress) }
    let ext = pySplitExt(pyName(fileOrDirPath)).ext.pyLower
    switch ext {
    case ".zip": return try extractZip(fileOrDirPath, progress: progress)
    case ".tar", ".gz", ".bz2", ".tgz": return try extractTar(fileOrDirPath, progress: progress)
    case ".7z": return try extract7z(fileOrDirPath, progress: progress)
    case ".rar": return try extractRar(fileOrDirPath, progress: progress)
    default:
        // Tenter zip en premier (bsdtar reconnaît le format lui-même)
        if let r = try? extractZip(fileOrDirPath, progress: progress) { return r }
        if let r = try? extract7z(fileOrDirPath, progress: progress) { return r }
        return try extractTar(fileOrDirPath, progress: progress)
    }
}

/// Lit à la demande le contenu de fichiers non chargés à l'indexation (textures d'aperçu…), en une passe par archive.
/// Renvoie {chemin normalisé en minuscules: octets}.
public func readEntriesBytes(_ index: ArchiveIndex, _ entries: [VirtualFileEntry]) -> [String: Data] {
    var out: [String: Data] = [:]
    var pending: [VirtualFileEntry] = []
    for e in entries {
        if let d = readEntryBytes(e) { out[e.path.pyLower] = d } else if e.member != nil { pending.append(e) }
    }
    guard !pending.isEmpty, let path = index.archivePath, !isDir(path) else { return out }
    let got = readArchiveMembers(path, members: pending.compactMap(\.member))
    for e in pending {
        if let m = e.member, let d = got[m] { out[e.path.pyLower] = d }
    }
    return out
}

/// Extrait sur disque, en flux et en une passe, les membres d'archive demandés. Renvoie {membre: chemin extrait}.
public func extractMembersToDir(_ index: ArchiveIndex, members: [String], outDir: String, progress: ((String) -> Void)? = nil) -> [String: String] {
    var out: [String: String] = [:]
    let uniq = Array(OrderedDict<Bool>.from(members.filter { !$0.isEmpty }).keys)
    guard !uniq.isEmpty, let path = index.archivePath, !isDir(path) else { return out }
    try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)
    progress?("Décompression de \(uniq.count) fichiers depuis l'archive...")
    bsdtarExtract(path, members: uniq, to: outDir)
    for m in uniq {
        let d = confinedDest(outDir, m)
        if isFile(d) { out[m] = d }
    }
    return out
}
