// Sortie JSON complète d'une analyse fOMODSIM, pour la comparer à celle de la version Python (parity_py.py).
// Usage : fomod-parity <archive|dossier|--demo> [--seed N] [--scenarios K] [--export DIR]
// L'archive, le dossier Data et le dossier d'export sont les seuls chemins touchés : l'archive en lecture seule.

import CryptoKit
import Foundation
import FomodCore

struct Rng {
    var s: UInt64
    init(_ seed: UInt64) { s = seed }
    mutating func next() -> UInt64 {
        s = s &+ 0x9E3779B97F4A7C15
        var z = s
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
    mutating func below(_ n: Int) -> Int { Int(next() % UInt64(n)) }
}

func fnv(_ s: String) -> UInt64 {
    var h: UInt64 = 0xcbf29ce484222325
    for b in s.utf8 { h = (h ^ UInt64(b)) &* 0x100000001b3 }
    return h
}

func sha(_ d: Data?) -> Any {
    guard let d = d else { return NSNull() }
    return SHA256.hash(data: d).map { String(format: "%02x", $0) }.joined()
}

func depsJSON(_ d: FomodDependencies?) -> Any {
    guard let d = d else { return NSNull() }
    return ["op": d.op, "files": d.fileDependencies.map { [$0.file, $0.state] }, "flags": d.flagDependencies.map { [$0.flag, $0.value] },
            "nested": d.nestedDependencies.map { depsJSON($0) }, "assumed": d.assumedTrue] as [String: Any]
}

func itemJSON(_ i: FomodItem) -> [Any] {
    [i.kind == .file ? "file" : "folder", i.source, i.destination, i.priority, i.alwaysInstall, i.installIfUsable]
}

func tdJSON(_ t: TypeDescriptor?) -> Any {
    guard let t = t else { return NSNull() }
    return ["default": t.defaultType, "patterns": t.patterns.map { ["deps": depsJSON($0.dependencies), "type": $0.typeName] as [String: Any] }] as [String: Any]
}

func treeJSON(_ steps: [FomodStep]) -> [Any] {
    steps.map { s in
        ["id": s.id, "name": s.name, "vis": depsJSON(s.visibility), "groups": s.groups.map { g in
            ["id": g.id, "name": g.name, "type": g.type.rawValue, "options": g.options.map { o in
                ["id": o.id, "name": o.name, "desc": o.description, "image": o.imagePath as Any? ?? NSNull(),
                 "files": o.files.map(itemJSON), "folders": o.folders.map(itemJSON), "flags": o.flags, "deps": depsJSON(o.dependencies),
                 "td": tdJSON(o.typeDescriptor), "default": o.isDefault, "masters": o.requiredMasters.sorted { $0.pyLess($1) }] as [String: Any]
            }] as [String: Any]
        }] as [String: Any]
    }
}

func stagingJSON(_ r: StagingResult) -> Any {
    ["items": r.items.map { [$0.destinationPath, $0.sourcePath, $0.size, $0.priority, $0.matchedFromOption, sha($0.data)] as [Any] },
     "total": r.totalSize, "copied": r.copiedCount, "missing": r.missingCount, "log": r.log] as [String: Any]
}

func fileDeps(_ steps: [FomodStep], _ cond: [ConditionalInstallPattern]) -> [String] {
    var out = Set<String>()
    func walk(_ d: FomodDependencies?) {
        guard let d = d else { return }
        for f in d.fileDependencies { out.insert(f.file.replacingOccurrences(of: "\\", with: "/").pyStrip.lastSlashComponent.pyLower) }
        for n in d.nestedDependencies { walk(n) }
    }
    for s in steps {
        walk(s.visibility)
        for g in s.groups { for o in g.options {
            walk(o.dependencies)
            if let td = o.typeDescriptor { for p in td.patterns { walk(p.dependencies) } }
        } }
    }
    for c in cond { walk(c.dependencies) }
    return out.sorted { $0.pyLess($1) }
}

func sortedPy(_ a: [String]) -> [String] { a.sorted { $0.pyLess($1) } }

struct Scenario { var json: [String: Any]; var session: InstallSession; var result: StagingResult }

func scenario(_ name: String, _ steps: [FomodStep], _ req: [FomodItem], _ cond: [ConditionalInstallPattern], _ index: ArchiveIndex,
              _ installed: [String], rng: Rng? = nil, clicks: Int = 0) -> Scenario {
    let s = InstallSession(steps: steps, requiredFiles: req, conditionalInstalls: cond, installedBasenames: Set(installed))
    if var rng = rng {
        for _ in 0..<clicks {
            let vis = s.visibleStepIndices()
            if vis.isEmpty { break }
            let st = steps[vis[rng.below(vis.count)]]
            if st.groups.isEmpty { continue }
            let g = st.groups[rng.below(st.groups.count)]
            if g.options.isEmpty { continue }
            s.toggle(g.options[rng.below(g.options.count)], group: g)
        }
    }
    let res = s.buildStaging(index)
    var prev: [Any] = []
    for i in s.visibleStepIndices() {
        for g in steps[i].groups { for o in g.options {
            let (a, b) = pickPreviewEntries(index, o, group: g)
            prev.append([o.id, a?.path as Any? ?? NSNull(), b?.path as Any? ?? NSNull()] as [Any])
        } }
    }
    var types: [Any] = []
    for st in steps { for g in st.groups { for o in g.options { types.append([o.id, s.optionType(o), s.isLocked(o, group: g)] as [Any]) } } }
    let j: [String: Any] = ["name": name, "installed": sortedPy(installed), "selected": sortedPy(Array(s.selected)), "visible": s.visibleStepIndices(),
                            "flags": s.activeFlags, "types": types, "previews": prev, "staging": stagingJSON(res)]
    return Scenario(json: j, session: s, result: res)
}

func emit(_ obj: [String: Any]) {
    let d = try! JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])
    FileHandle.standardOutput.write(d)
    FileHandle.standardOutput.write(Data("\n".utf8))
}

func main() {
    let a = Array(CommandLine.arguments.dropFirst())
    guard let target = a.first else { print("usage: fomod-parity <archive|--demo> [--seed N] [--scenarios K] [--export DIR]"); exit(2) }
    func opt(_ n: String) -> String? { a.firstIndex(of: n).flatMap { $0 + 1 < a.count ? a[$0 + 1] : nil } }
    let seed = Int(opt("--seed") ?? "1") ?? 1
    let k = Int(opt("--scenarios") ?? "3") ?? 3
    let exportDir = opt("--export")

    var out: [String: Any] = ["error": NSNull()]
    let extracted: ExtractedArchive
    let key: String
    do {
        if target == "--demo" { extracted = getDemoMod(); key = "demo" } else { extracted = try extractArchive(target); key = pyName(target) }
    } catch {
        out["error"] = "extract"
        emit(out); return
    }
    let index = extracted.index
    let cfg = extracted.moduleConfigXML, info = extracted.infoXML
    out["cfg_sha"] = sha(Data(cfg.utf8)); out["info_sha"] = sha(Data(info.utf8))
    out["folder_name"] = stagingFolderName(target == "--demo" ? nil : target, modName: "")
    if info.isEmpty { out["meta"] = NSNull() } else {
        let m = parseInfoXML(info)
        out["meta"] = [m.name, m.author, m.version, m.website, m.description]
    }
    var files: [[Any]] = index.files.items.map { [$0.key, $0.value.path, $0.value.size, sha($0.value.data)] }
    files.sort { ($0[0] as! String).pyLess($1[0] as! String) }
    var dirs: [[Any]] = index.dirs.items.map { [$0.key, $0.value] }
    dirs.sort { ($0[0] as! String).pyLess($1[0] as! String) }
    out["index"] = ["files": files, "dirs": dirs] as [String: Any]
    if cfg.isEmpty { out["error"] = "no-config"; emit(out); return }
    let conf: ModuleConfig
    do { conf = try parseModuleConfigXML(cfg) } catch { out["error"] = "parse"; emit(out); return }
    let (steps, req, cond) = (conf.steps, conf.requiredFiles, conf.conditionalInstalls)
    annotateOptionMasters(index, steps)
    out["module_name"] = conf.moduleName
    out["tree"] = treeJSON(steps)
    out["required"] = req.map(itemJSON)
    out["conditional"] = cond.map { ["deps": depsJSON($0.dependencies), "files": $0.files.map(itemJSON), "folders": $0.folders.map(itemJSON)] as [String: Any] }

    let deps = fileDeps(steps, cond)
    let van = ["skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm", "dragonborn.esm"]
    func half(_ l: [String]) -> [String] { l.enumerated().filter { $0.offset % 2 == 0 }.map(\.element) }
    var scen: [Scenario] = []
    scen.append(scenario("default", steps, req, cond, index, []))
    scen.append(scenario("data_all", steps, req, cond, index, sortedPy(Array(Set(deps).union(van)))))
    scen.append(scenario("data_half", steps, req, cond, index, sortedPy(Array(Set(half(deps)).union(van)))))
    for j in 0..<k {
        let rng = Rng(fnv(key) ^ UInt64(seed * 1000003 + j))
        let inst = j % 2 == 0 ? [] : sortedPy(Array(Set(half(deps)).union(van)))
        scen.append(scenario("random\(j)", steps, req, cond, index, inst, rng: rng, clicks: 12))
    }
    var exp: Any = NSNull()
    if let dir = exportDir {
        let fails = exportStagingToDirectory(scen[1].result, targetDir: dir, archiveIndex: index)
        var list: [[Any]] = []
        let fm = FileManager.default
        if let en = fm.enumerator(atPath: dir) {
            for case let rel as String in en {
                var isD: ObjCBool = false
                if fm.fileExists(atPath: dir + "/" + rel, isDirectory: &isD), !isD.boolValue {
                    list.append([rel, sha(fm.contents(atPath: dir + "/" + rel))])
                }
            }
        }
        list.sort { ($0[0] as! String).pyLess($1[0] as! String) }
        exp = ["failures": sortedPy(fails), "files": list] as [String: Any]
    }
    out["scenarios"] = scen.map(\.json)
    out["export"] = exp
    emit(out)
}

main()
