// Staging : simulation de l'installation et export (traduction de python_app/fomod/staging.py).

import Foundation

private let rxDstExt = Rx("\\.[a-zA-Z0-9_-]{2,6}$")

/// Chemin de destination normalisé pour un fichier copié via FOMOD.
/// Corrige le cas où destination="Plugin.esp" avec source="00 Core/Plugin.esp".
public func resolveFileDestination(_ rawDst: String, _ srcPath: String) -> String {
    let cleanDst = norm(rawDst).pyStrip(chars: "/")
    let fileName = srcPath.contains("/") ? srcPath.lastSlashComponent : srcPath

    if cleanDst.isEmpty { return fileName }

    let cleanLower = cleanDst.pyLower
    let nameLower = fileName.pyLower

    // 1. La destination se termine déjà par le nom du fichier
    if cleanLower == nameLower || cleanLower.hasSuffix("/" + nameLower) { return cleanDst }
    // 2. La destination se termine par une extension explicite (.esp, .dds, .nif…)
    if rxDstExt.search(cleanDst) { return cleanDst }
    // 3. Sinon c'est un répertoire cible
    return norm("\(cleanDst)/\(fileName)")
}

/// Simule la copie et l'installation de tous les fichiers FOMOD sélectionnés, y compris les requiredInstallFiles
/// et les conditionalFileInstalls.
public func buildStaging(
    selectedOptions: [FomodOption],
    requiredFiles: [FomodItem],
    archiveIndex: ArchiveIndex,
    conditionalInstalls: [ConditionalInstallPattern]? = nil,
    activeFlags: [String: String]? = nil,
    installedBasenames: Set<String>? = nil,
    forcedItems: [(item: FomodItem, optionName: String)]? = nil
) -> StagingResult {
    var log: [String] = []
    var itemsMap = OrderedDict<StagingItem>()  // destination en minuscules -> élément
    var copied = 0
    var missing = 0
    var totalSize = 0

    let cFlags = activeFlags ?? [:]
    let cBasenames = installedBasenames ?? []

    func sizeOf(_ e: VirtualFileEntry) -> Int {
        e.size != 0 ? e.size : (e.data.map { $0.isEmpty ? 1024 : $0.count } ?? 1024)
    }

    func placeFile(_ srcFile: VirtualFileEntry, _ cleanDst: String, _ optName: String, _ priority: Int, logIgnored: Bool) {
        let targetLower = cleanDst.pyLower
        let existing = itemsMap[targetLower]
        if let ex = existing, priority < ex.priority {
            if logIgnored { log.append("  [ignoré] \(srcFile.path) -> \(cleanDst) (prio \(priority) < \(ex.priority))") }
            return
        }
        let sz = sizeOf(srcFile)
        if let ex = existing {
            totalSize += sz - ex.size
        } else {
            copied += 1
            totalSize += sz
        }
        log.append("  [+ fichier] \(srcFile.path) -> \(cleanDst) (prio: \(priority))")
        itemsMap[targetLower] = StagingItem(
            sourcePath: srcFile.path, destinationPath: cleanDst, type: "file", size: sz, matchedFromOption: optName,
            data: srcFile.data, priority: priority, extractedDiskPath: srcFile.extractedDiskPath, member: srcFile.member)
    }

    func copyFolderFiles(_ dirPath: String, _ rawDst: String, _ optName: String, _ priority: Int) -> Int {
        var subCopied = 0
        var dirLower = dirPath.pyLower
        while dirLower.hasSuffix("/") { dirLower.removeLast() }
        let dirLowerSlash = dirLower.isEmpty ? "" : dirLower + "/"
        let prefixLen = dirLowerSlash.pyLen

        for (key, entry) in archiveIndex.files.items {
            if entry.isDir || isMacOSXKey(key) { continue }
            // Uniquement le contenu de CE dossier (pas d'un homonyme ailleurs dans l'archive)
            if !dirLowerSlash.isEmpty && !key.hasPrefix(dirLowerSlash) { continue }
            if dirLowerSlash.isEmpty && key.hasPrefix("fomod/") { continue }  // la racine du mod n'inclut pas l'installeur
            let relativeInside = entry.path.pySlice(prefixLen).pyLStrip("/")

            let cleanDst = norm(rawDst).pyStrip(chars: "/")
            let target: String
            if !cleanDst.isEmpty {
                target = !relativeInside.isEmpty ? norm("\(cleanDst)/\(relativeInside)") : cleanDst
            } else {
                target = !relativeInside.isEmpty ? relativeInside : entry.path.lastSlashComponent
            }

            let targetLower = target.pyLower
            let existing = itemsMap[targetLower]
            if let ex = existing, priority < ex.priority { continue }  // Priorité inférieure, ignorer

            let sz = sizeOf(entry)
            if let ex = existing {
                totalSize += sz - ex.size
            } else {
                copied += 1
                totalSize += sz
            }
            subCopied += 1
            log.append("  [+ fichier] \(entry.path) -> \(target) (prio: \(priority))")
            itemsMap[targetLower] = StagingItem(
                sourcePath: entry.path, destinationPath: target, type: "file", size: sz, matchedFromOption: optName,
                data: entry.data, priority: priority, extractedDiskPath: entry.extractedDiskPath, member: entry.member)
        }
        return subCopied
    }

    func processNode(_ tag: FomodItem.Kind, _ rawSrc: String, _ rawDst: String, _ optName: String, priority: Int = 0) {
        let src = norm(rawSrc)
        let srcFile = findFileInIndex(archiveIndex, src)
        let srcDir = findFolderInIndex(archiveIndex, src)
        let dstLabel = rawDst.isEmpty ? "." : rawDst

        if tag == .file {
            if let f = srcFile {
                placeFile(f, resolveFileDestination(rawDst, f.path), optName, priority, logIgnored: true)
            } else if let d = srcDir, !d.isEmpty {
                let n = copyFolderFiles(d, rawDst, optName, priority)
                log.append("  [+ dossier] \(d) -> \(dstLabel) (\(n) fichiers)")
            } else {
                missing += 1
                log.append("  [manquant] (fichier) \(src)")
            }
        } else {
            if let d = srcDir {
                let n = copyFolderFiles(d, rawDst, optName, priority)
                log.append("  [+ dossier] \(d) -> \(dstLabel) (\(n) fichiers)")
            } else if let f = srcFile {
                placeFile(f, resolveFileDestination(rawDst, f.path), optName, priority, logIgnored: false)
            } else {
                missing += 1
                log.append("  [manquant] (dossier) \(src)")
            }
        }
    }

    // 1. Fichiers requis
    if !requiredFiles.isEmpty {
        log.append("[Fichiers Requis (requiredInstallFiles)]")
        for req in requiredFiles { processNode(req.kind, req.source, req.destination, "Requis", priority: req.priority) }
    }

    // 2. Options sélectionnées
    for opt in selectedOptions {
        log.append("\n[\(opt.name)]")
        for f in opt.files { processNode(.file, f.source, f.destination, opt.name, priority: f.priority) }
        for fld in opt.folders { processNode(.folder, fld.source, fld.destination, opt.name, priority: fld.priority) }
    }

    // 2 bis. Fichiers installés même sans sélection (alwaysInstall / installIfUsable)
    if let forced = forcedItems, !forced.isEmpty {
        log.append("\n[Fichiers toujours installés (alwaysInstall / installIfUsable)]")
        for (item, optName) in forced { processNode(item.kind, item.source, item.destination, optName, priority: item.priority) }
    }

    // 3. Installations conditionnelles (conditionalFileInstalls)
    if let conds = conditionalInstalls, !conds.isEmpty {
        log.append("\n[Installations Conditionnelles (conditionalFileInstalls)]")
        for (idx, pat) in conds.enumerated() where evaluateDependencies(pat.dependencies, cBasenames, cFlags) {
            for f in pat.files { processNode(.file, f.source, f.destination, "Conditionnel #\(idx + 1)", priority: f.priority) }
            for fld in pat.folders { processNode(.folder, fld.source, fld.destination, "Conditionnel #\(idx + 1)", priority: fld.priority) }
        }
    }

    let sorted = itemsMap.values.enumerated().sorted { a, b in
        let ka = a.element.destinationPath.pyLower, kb = b.element.destinationPath.pyLower
        return ka == kb ? a.offset < b.offset : ka.pyLess(kb)
    }.map(\.element)

    return StagingResult(items: sorted, totalSize: totalSize, copiedCount: copied, missingCount: missing, log: log)
}

// MARK: - Nom du dossier de staging

// Noms d'archives Nexus (téléchargement manuel, Vortex, collections), suffixes à retirer :
private let rxNexusNew = Rx("\\s+\\d{2,7}\\s+\\S+\\s+\\d{4}-\\d{2}-\\d{2}T\\d{2}-\\d{2}Z(?:\\s+[0-9A-Za-z_-]+)?$")
private let rxNexusOld = Rx("-\\d{3,7}(?:-[0-9A-Za-z.]+){1,6}$")
private let rxNexusUnderscore = Rx("(?:_[0-9][0-9.]*)*_[0-9A-Za-z]{9}$")
private let rxNexusTruncated = Rx("-\\d{3,7}-$")
private let rxDuplicateMark = Rx("\\s*\\(\\d{1,2}\\)$")
private let rxForbidden = Rx("[/\\\\:*?\"<>|\\x00-\\x1f]+")
private let rxSpaces = Rx("\\s{2,}")
let archiveExts = [".tar.gz", ".tar.bz2", ".zip", ".7z", ".rar", ".tar", ".tgz", ".gz", ".bz2"]

/// Nom lisible d'une archive de mod (sans extension) : retire l'identifiant, la version, l'horodatage et le code
/// ajoutés par Nexus, ainsi que la marque de copie « (1) ».
public func cleanArchiveName(_ base: String) -> String {
    for candidate in [base, rxDuplicateMark.sub("", base)] {
        if rxNexusNew.search(candidate) { return rxNexusNew.sub("", candidate) }
        if rxNexusOld.search(candidate) { return rxNexusOld.sub("", candidate) }
        if !candidate.contains(" ") && candidate.contains("_") && rxNexusUnderscore.search(candidate) {
            let stripped = rxNexusUnderscore.sub("", candidate)
            if !stripped.isEmpty { return stripped.replacingOccurrences(of: "_", with: " ") }
        }
        if rxNexusTruncated.search(candidate) { return rxNexusTruncated.sub("", candidate) }
    }
    return base
}

/// Nom du dossier de staging d'un mod : nom de l'archive (ou du dossier) nettoyé des ajouts de Nexus, sinon nom du mod,
/// en majuscules.
public func stagingFolderName(_ sourcePath: String?, modName: String = "") -> String {
    var name = ""
    if let sp = sourcePath, !sp.isEmpty {
        var base = pyName(sp)
        if isDir(sp) {
            name = base
        } else {
            for ext in archiveExts where base.pyLower.hasSuffix(ext) {
                base = String(base.unicodeScalars.dropLast(ext.unicodeScalars.count))
                break
            }
            let cleaned = cleanArchiveName(base)
            name = cleaned.isEmpty ? base : cleaned
        }
    }
    let chosen = !name.isEmpty ? name : (!modName.isEmpty ? modName : "Mod FOMOD")
    var n = rxForbidden.sub("-", chosen)
    n = rxSpaces.sub(" ", n).pyStrip(chars: " .-_")
    return (n.isEmpty ? "Mod FOMOD" : n).uppercased()
}

// MARK: - Export

private func confinedPath(_ root: String, _ relative: String) -> String {
    // Chemin de sortie confiné au dossier cible (pas de « .. » ni de chemin absolu venant d'un FOMOD)
    let parts = relative.pySplit("/").filter { !["", ".", ".."].contains($0) }
    return parts.isEmpty ? root : pyJoin(root, parts.joined(separator: "/"))
}

private func fileSize(_ path: String) -> Int? {
    (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? NSNumber)?.intValue
}

/// Écrit physiquement les fichiers du staging dans `targetDir`. Le contenu vient, dans l'ordre : des octets chargés à
/// l'indexation, du fichier sur disque (dossier de mod), sinon de l'archive, lue en une passe et en flux.
/// Renvoie la liste des destinations dont le contenu n'a pas pu être obtenu : ces fichiers ne sont pas créés.
@discardableResult
public func exportStagingToDirectory(
    _ staging: StagingResult, targetDir: String, archiveIndex: ArchiveIndex? = nil, progress: ((String) -> Void)? = nil
) -> [String] {
    let fm = FileManager.default
    try? fm.createDirectory(atPath: targetDir, withIntermediateDirectories: true)
    var failures: [String] = []
    var pending = OrderedDict<[StagingItem]>()

    func destOf(_ item: StagingItem) -> String { confinedPath(targetDir, item.destinationPath) }
    func prepare(_ item: StagingItem) -> String {
        let dest = destOf(item)
        try? fm.createDirectory(atPath: pyParent(dest), withIntermediateDirectories: true)
        return dest
    }
    func write(_ data: Data, to dest: String) -> Bool {
        (try? data.write(to: URL(fileURLWithPath: dest))) != nil
    }
    func copy(_ src: String, to dest: String) -> Bool {
        try? fm.removeItem(atPath: dest)
        return (try? fm.copyItem(atPath: src, toPath: dest)) != nil
    }

    for item in staging.items {
        if let d = item.data, !d.isEmpty {
            _ = write(d, to: prepare(item))
        } else if let p = item.extractedDiskPath, isFile(p) {
            _ = copy(p, to: prepare(item))
        } else if let m = item.member, archiveIndex != nil {
            var l = pending[m] ?? []
            l.append(item)
            pending[m] = l
        } else if item.size == 0 {
            _ = write(Data(), to: prepare(item))  // fichier réellement vide dans le mod
        } else {
            failures.append(item.destinationPath)
        }
    }

    if !pending.isEmpty, let index = archiveIndex {
        let tmp = pyJoin(targetDir, ".fomodsim_extract_" + UUID().uuidString.prefix(8))
        try? fm.createDirectory(atPath: tmp, withIntermediateDirectories: true)
        defer { try? fm.removeItem(atPath: tmp) }
        let extracted = extractMembersToDir(index, members: pending.keys, outDir: tmp, progress: progress)
        for (member, items) in pending.items {
            let src = extracted[member]
            for item in items {
                if let s = src, isFile(s) {
                    _ = copy(s, to: prepare(item))
                } else {
                    failures.append(item.destinationPath)
                }
            }
        }
    }

    // Contrôle : aucun fichier vide là où la source ne l'est pas
    for item in staging.items {
        let dest = destOf(item)
        if failures.contains(item.destinationPath) { continue }
        if !isFile(dest) || (item.size > 0 && fileSize(dest) == 0) { failures.append(item.destinationPath) }
    }
    return failures
}

/// Génère une archive .ZIP du staging prête à être installée. Renvoie les fichiers sans contenu.
@discardableResult
public func exportStagingToZip(
    _ staging: StagingResult, zipPath: String, archiveIndex: ArchiveIndex? = nil, progress: ((String) -> Void)? = nil
) -> [String] {
    let fm = FileManager.default
    let tmp = NSTemporaryDirectory() + ".fomodsim_zip_" + UUID().uuidString.prefix(8)
    try? fm.createDirectory(atPath: tmp, withIntermediateDirectories: true)
    defer { try? fm.removeItem(atPath: tmp) }
    let failures = exportStagingToDirectory(staging, targetDir: tmp, archiveIndex: archiveIndex, progress: progress)
    let names = staging.items.map(\.destinationPath).filter { isFile(confinedPath(tmp, $0)) }
    let list = tmp + "/.names.txt"
    try? names.joined(separator: "\n").write(toFile: list, atomically: false, encoding: .utf8)
    try? fm.removeItem(atPath: zipPath)
    _ = runTool("/usr/bin/bsdtar", ["--format", "zip", "--no-mac-metadata", "-cf", zipPath, "-C", tmp, "-T", list])
    return failures
}
