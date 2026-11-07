// Petites fonctions de chemins qui se comportent comme pathlib / os.path de la version Python.

import Darwin
import Foundation

/// Chemin normalisé comme `pathlib.Path(...)` : barres doubles et « . » retirés, pas de barre finale, « . » si vide.
public func pyPath(_ s: String) -> String {
    if s.isEmpty { return "." }
    let absolute = s.hasPrefix("/")
    let parts = s.split(separator: "/", omittingEmptySubsequences: true).filter { $0 != "." }
    let joined = parts.joined(separator: "/")
    if absolute { return "/" + joined }
    return joined.isEmpty ? "." : joined
}

/// `Path(a) / b` : b absolu l'emporte ; « . » ne s'ajoute pas.
public func pyJoin(_ a: String, _ b: String) -> String {
    if b.hasPrefix("/") { return pyPath(b) }
    let base = pyPath(a)
    let rest = pyPath(b)
    if rest == "." { return base }
    if base == "." { return rest }
    return base == "/" ? "/" + rest : base + "/" + rest
}

public func pyName(_ path: String) -> String {
    let p = pyPath(path)
    return p == "/" || p == "." ? "" : (p.split(separator: "/").last.map(String.init) ?? "")
}

public func pyParent(_ path: String) -> String {
    let p = pyPath(path)
    guard let idx = p.lastIndex(of: "/") else { return "." }
    if idx == p.startIndex { return "/" }
    return String(p[..<idx])
}

/// `os.path.splitext` : (racine, extension) ; les points de tête du nom ne comptent pas.
public func pySplitExt(_ name: String) -> (root: String, ext: String) {
    let scalars = Array(name.unicodeScalars)
    guard let dot = scalars.lastIndex(of: ".") else { return (name, "") }
    var i = 0
    while i < dot {
        if scalars[i] != "." {
            var rootView = String.UnicodeScalarView()
            rootView.append(contentsOf: scalars[..<dot])
            var extView = String.UnicodeScalarView()
            extView.append(contentsOf: scalars[dot...])
            return (String(rootView), String(extView))
        }
        i += 1
    }
    return (name, "")
}

/// `Path.stem`
public func pyStem(_ path: String) -> String {
    let name = pyName(path)
    if name.hasSuffix("."), name.count > 1 { return name }  // « a. » : pas de suffixe
    let (root, ext) = pySplitExt(name)
    return ext.isEmpty ? name : root
}

public func isDir(_ path: String) -> Bool {
    var st = stat()
    return stat(path, &st) == 0 && (st.st_mode & S_IFMT) == S_IFDIR
}

public func isFile(_ path: String) -> Bool {
    var st = stat()
    return stat(path, &st) == 0 && (st.st_mode & S_IFMT) == S_IFREG
}

/// `os.path.realpath` : résout les liens ; la fin qui n'existe pas est gardée telle quelle.
public func realPath(_ path: String) -> String {
    var p = pyPath(path)
    if !p.hasPrefix("/") { p = pyJoin(FileManager.default.currentDirectoryPath, p) }
    var tail: [String] = []
    var cur = p
    while true {
        if let r = realpath(cur, nil) {
            let base = String(cString: r)
            free(r)
            return tail.isEmpty ? base : pyJoin(base, tail.reversed().joined(separator: "/"))
        }
        if cur == "/" || cur.isEmpty { return p }
        tail.append(pyName(cur))
        cur = pyParent(cur)
    }
}

/// Erreur « [Errno 2] No such file or directory: 'chemin' » comme les exceptions OSError de Python.
public struct PyOSError: Error, CustomStringConvertible, LocalizedError {
    public let code: Int32
    public let path: String?
    public init(_ code: Int32, _ path: String? = nil) { self.code = code; self.path = path }
    public var description: String {
        let msg = String(cString: strerror(code))
        return "[Errno \(code)] \(msg)" + (path.map { ": '\($0)'" } ?? "")
    }
    public var errorDescription: String? { description }
}

public struct DirEntry {
    public let name: String
    /// `os.DirEntry.is_dir()` : suit les liens
    public let isDir: Bool
    public let isSymlink: Bool
}

/// `os.scandir` : entrées d'un dossier (sans « . » ni « .. »), nil si illisible.
public func scanDir(_ path: String) -> [DirEntry]? {
    guard let dir = opendir(path) else { return nil }
    defer { closedir(dir) }
    var out: [DirEntry] = []
    while let ent = readdir(dir) {
        let name = withUnsafePointer(to: &ent.pointee.d_name) {
            $0.withMemoryRebound(to: CChar.self, capacity: Int(ent.pointee.d_namlen) + 1) { String(cString: $0) }
        }
        if name == "." || name == ".." { continue }
        let type = Int32(ent.pointee.d_type)
        var dirFlag = type == Int32(DT_DIR)
        let link = type == Int32(DT_LNK)
        if link || type == Int32(DT_UNKNOWN) {
            dirFlag = isDir(path + "/" + name)
        }
        out.append(DirEntry(name: name, isDir: dirFlag, isSymlink: link))
    }
    return out
}

/// `os.walk(top)` descendant, sans suivre les liens vers des dossiers. `visit(dossier, rel, &sous-dossiers, fichiers)` peut
/// retirer des sous-dossiers de la liste (ils ne sont alors pas parcourus) ; renvoyer faux arrête tout le parcours (le
/// résultat est alors faux). `rel` : chemin du dossier visité depuis `top` (composants).
@discardableResult
public func walkTree(_ top: String, _ visit: (_ root: String, _ rel: [String], _ dirs: inout [String], _ files: [String]) -> Bool) -> Bool {
    func go(_ root: String, _ rel: [String]) -> Bool {
        guard let entries = scanDir(root) else { return true }
        var dirs: [String] = [], files: [String] = []
        var links = Set<String>()
        for e in entries {
            if e.isDir { dirs.append(e.name); if e.isSymlink { links.insert(e.name) } } else { files.append(e.name) }
        }
        if !visit(root, rel, &dirs, files) { return false }
        for d in dirs where !links.contains(d) {
            if !go(root + "/" + d, rel + [d]) { return false }
        }
        return true
    }
    guard isDir(top) else { return true }
    return go(pyPath(top), [])
}

/// `Path.home()` : la variable HOME d'abord (les essais la remplacent), sinon le dossier de l'utilisateur.
public func homeDir() -> String {
    if let h = ProcessInfo.processInfo.environment["HOME"], !h.isEmpty { return h }
    return NSHomeDirectory()
}
