// Lecture des archives (ZIP, 7Z, RAR, TAR) par /usr/bin/bsdtar, l'outil libarchive fourni avec macOS : aucune dépendance
// à embarquer. Liste des entrées (chemins, tailles) et extraction de membres choisis, en une passe.

import Foundation

public let bsdtarPath = "/usr/bin/bsdtar"

/// Lance un outil et renvoie son code de sortie et sa sortie standard (erreurs jetées).
@discardableResult
public func runTool(_ exe: String, _ args: [String]) -> (status: Int32, out: Data) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: exe)
    p.arguments = args
    var env = ProcessInfo.processInfo.environment
    env["LC_ALL"] = "en_US.UTF-8"  // noms d'entrées en UTF-8, pas en octets échappés
    p.environment = env
    let out = Pipe()
    p.standardOutput = out
    p.standardError = FileHandle.nullDevice
    p.standardInput = FileHandle.nullDevice
    do { try p.run() } catch { return (-1, Data()) }
    let data = out.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return (p.terminationStatus, data)
}

public struct ArchiveListEntry {
    /// Nom tel que bsdtar l'affiche (c'est aussi celui qu'il faut lui redonner pour extraire)
    public var member: String
    public var size: Int
    public var isDir: Bool
    public var isSymlink: Bool
}

private let rxListLine = Rx("^(.)\\S*\\s+\\d+\\s+\\S+\\s+\\S+\\s+(\\d+)\\s+[A-Za-z]{3}\\s+\\d{1,2}\\s+(?:\\d{4}|\\d{1,2}:\\d{2}) ")

/// Options de lecture : les noms de ZIP sans indicateur UTF-8 se lisent en CP437, comme le fait zipfile en Python.
func readOptions(for path: String) -> [String] {
    path.pyLower.hasSuffix(".zip") ? ["--options", "hdrcharset=CP437"] : []
}

/// Liste d'une archive (`bsdtar -tvf`). Nil si l'outil échoue.
public func listArchive(_ path: String) -> [ArchiveListEntry]? {
    let r = runTool(bsdtarPath, readOptions(for: path) + ["-tvf", path])
    if r.status != 0 && r.out.isEmpty { return nil }
    let text = String(decoding: r.out, as: UTF8.self)
    var entries: [ArchiveListEntry] = []
    for line in text.split(separator: "\n", omittingEmptySubsequences: true) {
        let l = String(line)
        guard let m = rxListLine.re.firstMatch(in: l, range: NSRange(l.startIndex..., in: l)),
              let tr = Range(m.range(at: 1), in: l), let sr = Range(m.range(at: 2), in: l) else { continue }
        let type = l[tr]
        var name = String(l[Range(m.range, in: l)!.upperBound...])
        let isLink = type == "l"
        if isLink, let r = name.range(of: " -> ") { name = String(name[..<r.lowerBound]) }
        entries.append(ArchiveListEntry(member: name, size: Int(l[sr]) ?? 0, isDir: type == "d" || name.hasSuffix("/"), isSymlink: isLink))
    }
    if r.status != 0 && entries.isEmpty { return nil }
    return entries
}

/// Protège un nom contre les caractères génériques de bsdtar (`*`, `?`, `[`, `\`).
func escapePattern(_ name: String) -> String {
    var out = ""
    for ch in name {
        if "\\*?[".contains(ch) { out.append("\\") }
        out.append(ch)
    }
    return out
}

/// Chemin de sortie confiné au dossier d'extraction (pas de « .. » ni de chemin absolu venant de l'archive).
public func confinedDest(_ outDir: String, _ member: String) -> String {
    let safe = norm(member).pyLStrip("/")
    let parts = safe.pySplit("/").filter { !["", ".", ".."].contains($0) }
    return parts.isEmpty ? outDir : pyJoin(outDir, parts.joined(separator: "/"))
}

/// Extrait des membres précis dans `outDir`, en une passe. Un nom absent du résultat n'a pas pu être lu.
func bsdtarExtract(_ archive: String, members: [String], to outDir: String) {
    guard !members.isEmpty else { return }
    try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)
    let listFile = NSTemporaryDirectory() + "fomodsim_members_\(UUID().uuidString).txt"
    let content = members.map(escapePattern).joined(separator: "\n")
    guard (try? content.write(toFile: listFile, atomically: false, encoding: .utf8)) != nil else { return }
    defer { try? FileManager.default.removeItem(atPath: listFile) }
    runTool(bsdtarPath, readOptions(for: archive) + ["-xf", archive, "-C", outDir, "-T", listFile])
}

/// Lit le contenu d'un fichier extrait ; rend lisible un fichier dont l'archive avait des droits nuls.
func readExtracted(_ path: String) -> Data? {
    if let d = FileManager.default.contents(atPath: path) { return d }
    chmod(path, 0o600)
    return FileManager.default.contents(atPath: path)
}

/// Extrait `members` dans un dossier temporaire jetable et renvoie {membre: octets}.
public func readArchiveMembers(_ archive: String, members: [String]) -> [String: Data] {
    let uniq = Array(OrderedDict<Bool>.from(members).keys)
    guard !uniq.isEmpty else { return [:] }
    let tmp = NSTemporaryDirectory() + "fomodsim_read_\(UUID().uuidString)"
    defer { try? FileManager.default.removeItem(atPath: tmp) }
    bsdtarExtract(archive, members: uniq, to: tmp)
    var out: [String: Data] = [:]
    for m in uniq {
        let dest = confinedDest(tmp, m)
        if isFile(dest), let d = readExtracted(dest) { out[m] = d }
    }
    return out
}

extension OrderedDict where Value == Bool {
    /// `dict.fromkeys(items)` : doublons retirés, ordre conservé.
    static func from(_ items: [String]) -> OrderedDict<Bool> {
        var d = OrderedDict<Bool>()
        for i in items where d[i] == nil { d[i] = true }
        return d
    }
}
