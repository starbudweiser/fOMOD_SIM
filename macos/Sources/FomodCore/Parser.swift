// Analyse de ModuleConfig.xml et recherche de fichiers (traduction de python_app/fomod/parser.py).

import Foundation

private let rxNormDotSlash = Rx("^(\\./)+")
private let rxStripNum = Rx("^\\d+\\s*[_-]*\\s*")
private let rxHumanize = Rx("[_\\-.]+")
private let rxImageExt = Rx("\\.(jpe?g|png|bmp|webp|gif|dds|tga)$", ignoreCase: true)

/// Normalise un chemin : backslashes en slashes, supprime les './' et '/' de tête et fin.
public func norm(_ p: String?) -> String {
    guard let p = p, !p.isEmpty else { return "" }
    var s = p.replacingOccurrences(of: "\\", with: "/").pyStrip
    s = rxNormDotSlash.sub("", s)
    return trimSlashes(s)
}

private func trimSlashes(_ s: String) -> String { s.pyStrip(chars: "/") }

public func stripNumPrefix(_ name: String) -> String {
    let base = name.contains("/") ? name.lastSlashComponent : name
    return rxStripNum.sub("", base).pyLower
}

private let genericLabels: Set<String> = [
    "option", "options", "groupe", "group", "general", "misc", "various",
    "default", "step", "étape", "etape", "choose", "selection", "select",
    "unp", "cbbe", "bodytype", "type",
]

public func isGenericLabel(_ s: String) -> Bool {
    if s.isEmpty { return true }
    let t = s.pyStrip.pyLower
    if genericLabels.contains(t) { return true }
    if t.hasPrefix("step ") || t.hasPrefix("étape ") || t.hasPrefix("etape ") { return true }
    if t.pyLen <= 3 { return true }
    return false
}

public func humanizeToken(_ tok: String) -> String {
    let t = rxHumanize.sub(" ", tok).pyStrip
    return t.split(whereSeparator: { $0.unicodeScalars.allSatisfy { " \t\n\r\u{0B}\u{0C}".unicodeScalars.contains($0) } })
        .map { String($0).pyCapitalized }.joined(separator: " ")
}

private let imageAttrs = ["image", "imagepath", "imagePath", "Path", "path", "file", "File", "src", "Src", "preview", "previewImage"]
private let imageChildAttrs = ["path", "Path", "file", "File", "src", "Src", "url", "Url", "name", "Name"]
private let imageTags: Set<String> = ["image", "headerimage", "previewimage", "img", "pic"]

/// Extrait le chemin d'image depuis un élément XML ou ses descendants de manière universelle.
func extractElementImage(_ el: XNode?) -> String? {
    guard let el = el else { return nil }
    for a in imageAttrs {
        if let v = el.attr(a), !v.pyStrip.isEmpty { return norm(v) }
    }
    for ch in el.iter() where ch !== el {
        let tag = localTag(ch.tag)
        guard imageTags.contains(tag) else { continue }
        for a in imageChildAttrs {
            if let v = ch.attr(a), !v.pyStrip.isEmpty { return norm(v) }
        }
        if let t = ch.text, !t.pyStrip.isEmpty {
            let txt = t.pyStrip
            if rxImageExt.search(txt) || txt.contains("/") || txt.contains("\\") { return norm(txt) }
        }
    }
    return nil
}

func isMacOSXKey(_ k: String) -> Bool { k.contains("__macosx") }

private func byPathLength(_ list: [VirtualFileEntry]) -> [VirtualFileEntry] {
    list.enumerated().sorted { a, b in
        let la = a.element.path.pyLen, lb = b.element.path.pyLen
        return la != lb ? la < lb : a.offset < b.offset
    }.map(\.element)
}

private func removingPrefix(_ s: String, _ p: String) -> String { s.hasPrefix(p) ? String(s.dropFirst(p.count)) : s }

/// Recherche de fichier robuste et insensible à la casse avec variations de préfixes FOMOD.
public func findFileInIndex(_ index: ArchiveIndex, _ src: String) -> VirtualFileEntry? {
    let rawKey = norm(src)
    if rawKey.isEmpty { return nil }
    let key = rawKey.pyLower

    // 1. Correspondance directe exacte
    if let f = index.files[key], !f.path.pyLower.contains("__macosx") { return f }

    // 2. Variations fréquentes de préfixes (fomod/, images/, fomod/images/)
    let variations = [
        key,
        removingPrefix(key, "fomod/"),
        removingPrefix(key, "images/"),
        key.hasPrefix("fomod/images/") ? "images/" + removingPrefix(key, "fomod/images/") : key,
        "fomod/\(key)",
        "images/\(key)",
        "fomod/images/\(key)",
    ]
    for v in variations {
        if let f = index.files[v], !f.path.pyLower.contains("__macosx") { return f }
    }

    // 3. Correspondance par suffixe, sur des segments entiers
    var suffixCands: [VirtualFileEntry] = []
    let suffixSlashKey = "/" + key
    for (relKey, entry) in index.files.items {
        if isMacOSXKey(relKey) { continue }
        if relKey.hasSuffix(suffixSlashKey) || key.hasSuffix("/" + relKey) { suffixCands.append(entry) }
    }
    if !suffixCands.isEmpty { return byPathLength(suffixCands)[0] }

    // 4. Correspondance par nom de fichier final (basename)
    let base = key.lastSlashComponent
    if !base.isEmpty, let cands = index.basenameMap[base], !cands.isEmpty { return cands[0] }

    // 5. Correspondance souple en ignorant les préfixes numériques
    let keyStripped = stripNumPrefix(key)
    for (relKey, entry) in index.files.items {
        if isMacOSXKey(relKey) { continue }
        let relStripped = stripNumPrefix(relKey)
        if relStripped == keyStripped || relStripped.hasSuffix("/" + keyStripped) { return entry }
    }
    return nil
}

let imageExts = [".png", ".jpg", ".jpeg", ".bmp", ".dds", ".tga", ".webp", ".gif"]

/// Comme findFileInIndex, mais tolère une extension d'image différente de celle déclarée.
public func findImageInIndex(_ index: ArchiveIndex, _ src: String) -> VirtualFileEntry? {
    let entry = findFileInIndex(index, src)
    if entry != nil || src.isEmpty { return entry }
    let key = norm(src).pyLower
    let stem = key.lastSlashComponent.contains(".") ? key.pyRPartition(".").0 : key
    for ext in imageExts {
        if let alt = findFileInIndex(index, stem + ext) { return alt }
    }
    return nil
}

/// Retrouve un dossier de l'archive (casse d'origine). Une source vide désigne la racine du mod.
public func findFolderInIndex(_ index: ArchiveIndex, _ src: String) -> String? {
    let rawKey = norm(src)
    if rawKey.isEmpty { return "" }
    let key = rawKey.pyLower

    // 1. Correspondance exacte
    if let d = index.dirs[key], !key.contains("__macosx") { return d }

    // 2. Dossier implicite (archives sans entrées de dossier)
    let prefix = key + "/"
    for (relKey, entry) in index.files.items where relKey.hasPrefix(prefix) && !isMacOSXKey(relKey) {
        return entry.path.pySlice(0, rawKey.pyLen)
    }

    // 3. Correspondance par suffixe sur des segments entiers
    let slashKey = "/" + key
    var cands: [String] = []
    for (relKey, orig) in index.dirs.items {
        if isMacOSXKey(relKey) { continue }
        if relKey.hasSuffix(slashKey) || key.hasSuffix("/" + relKey) { cands.append(orig) }
    }
    if !cands.isEmpty { return stableSortedByLen(cands)[0] }

    // 4. Correspondance sans préfixes numériques (« 01 Textures » ↔ « Textures »)
    let keyBn = stripNumPrefix(key)
    var prefixCands: [String] = []
    for (relKey, orig) in index.dirs.items {
        if isMacOSXKey(relKey) { continue }
        let sameParent = relKey.pyRPartition("/").0 == key.pyRPartition("/").0
        if sameParent && stripNumPrefix(relKey) == keyBn { prefixCands.append(orig) }
    }
    if !prefixCands.isEmpty { return stableSortedByLen(prefixCands)[0] }
    return nil
}

func stableSortedByLen(_ list: [String]) -> [String] {
    list.enumerated().sorted { a, b in
        let la = a.element.pyLen, lb = b.element.pyLen
        return la != lb ? la < lb : a.offset < b.offset
    }.map(\.element)
}

// MARK: - XML

func localTag(_ tag: String) -> String {
    (tag.range(of: "}") != nil ? String(tag[tag.range(of: "}")!.upperBound...]) : tag).pyLower
}

/// Lit un attribut sans tenir compte de la casse de son nom.
func attr(_ el: XNode, _ names: String..., default def: String? = nil) -> String? {
    var lowered: [String: String] = [:]
    for (k, v) in el.attrib { lowered[k.pyLower] = v }
    for n in names {
        if let v = lowered[n.pyLower] { return v }
    }
    return def
}

private func children(_ el: XNode, _ names: String...) -> [XNode] {
    let wanted = Set(names.map { $0.pyLower })
    return el.children.filter { wanted.contains(localTag($0.tag)) }
}

private func child(_ el: XNode, _ names: String...) -> XNode? {
    let wanted = Set(names.map { $0.pyLower })
    return el.children.first { wanted.contains(localTag($0.tag)) }
}

/// Analyse récursive d'un bloc de dépendances (<dependencies>, <visible>, <moduleDependencies>…).
func parseDependenciesNode(_ node: XNode) -> FomodDependencies {
    var op = attr(node, "operator", default: "And") ?? "And"
    if op.isEmpty { op = "And" }
    var fileDeps: [FileDependency] = []
    var flagDeps: [FlagDependency] = []
    var nested: [FomodDependencies] = []
    var assumed = 0

    for ch in node.children {
        let tag = localTag(ch.tag)
        if tag == "filedependency" {
            let f = attr(ch, "file", default: "") ?? ""
            var st = attr(ch, "state", default: "Active") ?? "Active"
            if st.isEmpty { st = "Active" }
            if !f.isEmpty { fileDeps.append(FileDependency(f, st)) }
        } else if tag == "flagdependency" {
            let fl = attr(ch, "flag", default: "") ?? ""
            let val = attr(ch, "value", default: "") ?? ""
            if !fl.isEmpty { flagDeps.append(FlagDependency(fl, val)) }
        } else if tag == "dependencies" {
            nested.append(parseDependenciesNode(ch))
        } else if tag.hasSuffix("dependency") {
            // gameDependency, fommDependency, foseDependency… : non simulables, supposées satisfaites
            assumed += 1
        }
    }
    return FomodDependencies(op: op, fileDependencies: fileDeps, flagDependencies: flagDeps, nestedDependencies: nested, assumedTrue: assumed)
}

/// <visible> ou <pattern> peuvent contenir les conditions directement ou via un <dependencies>.
func parseConditionContainer(_ node: XNode?) -> FomodDependencies? {
    guard let node = node else { return nil }
    if localTag(node.tag) == "dependencies" { return parseDependenciesNode(node) }
    let inner = children(node, "dependencies")
    let hasDirect = node.children.contains { localTag($0.tag).hasSuffix("dependency") }
    if inner.count == 1 && !hasDirect { return parseDependenciesNode(inner[0]) }
    return parseDependenciesNode(node)
}

private let flagFalse: Set<String> = ["", "inactive", "false", "missing", "0", "off", "none", "no", "disabled"]
private let flagTrue: Set<String> = ["active", "true", "1", "on", "yes", "enabled"]

/// Évalue la concordance d'un flag FOMOD (comparaison exacte d'abord, puis équivalences usuelles On/True/Active…).
public func checkFlagValue(_ currVal: String?, _ expectedVal: String) -> Bool {
    let curr = (currVal ?? "").pyStrip
    let exp = expectedVal.pyStrip
    if curr == exp { return true }
    let cl = curr.pyLower, el = exp.pyLower
    if cl == el { return true }
    if flagFalse.contains(el) { return flagFalse.contains(cl) }
    if flagTrue.contains(el) { return flagTrue.contains(cl) }
    return false
}

/// Évalue récursivement si les dépendances FOMOD sont satisfaites.
public func evaluateDependencies(_ deps: FomodDependencies?, _ installedBasenames: Set<String>, _ activeFlags: [String: String]) -> Bool {
    guard let deps = deps else { return true }
    var results: [Bool] = Array(repeating: true, count: deps.assumedTrue)

    for fd in deps.fileDependencies {
        let base = fd.file.replacingOccurrences(of: "\\", with: "/").pyStrip.lastSlashComponent.pyLower
        let present = installedBasenames.contains(base)
        let st = (fd.state.isEmpty ? "Active" : fd.state).pyStrip.pyLower
        if ["active", "present", "installed", "true"].contains(st) {
            results.append(present)
        } else if ["missing", "absent", "false"].contains(st) {
            results.append(!present)
        } else if st == "inactive" {
            results.append(false)
        } else {
            results.append(present)
        }
    }
    for fd in deps.flagDependencies { results.append(checkFlagValue(activeFlags[fd.flag], fd.value)) }
    for n in deps.nestedDependencies { results.append(evaluateDependencies(n, installedBasenames, activeFlags)) }

    if results.isEmpty { return true }
    let op = (deps.op.isEmpty ? "And" : deps.op).pyStrip.pyLower
    if op == "or" { return results.contains(true) }
    if op == "not" { return !results.contains(true) }
    return !results.contains(false)
}

/// Type effectif d'une option ('Recommended', 'Optional', 'Required', 'NotUsable', 'CouldBeUsable').
public func computeOptionType(_ opt: FomodOption, _ installedBasenames: Set<String>, _ activeFlags: [String: String]) -> String {
    if let td = opt.typeDescriptor {
        for pat in td.patterns where evaluateDependencies(pat.dependencies, installedBasenames, activeFlags) {
            return pat.typeName
        }
        return td.defaultType
    }
    if let deps = opt.dependencies {
        return evaluateDependencies(deps, installedBasenames, activeFlags) ? "Recommended" : "Optional"
    }
    return opt.isDefault ? "Recommended" : "Optional"
}

public let pluginExts = [".esp", ".esm", ".esl"]
/// Masters du jeu de base, toujours présents
public let vanillaMasters: Set<String> = ["skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm", "dragonborn.esm"]
private let rxNonAlnum = Rx("[^a-z0-9]")

private func hasFileDep(_ deps: FomodDependencies?) -> Bool {
    guard let d = deps else { return false }
    return !d.fileDependencies.isEmpty || d.nestedDependencies.contains { hasFileDep($0) }
}

/// Heuristique de secours : un fichier ou dossier « patch » de l'option porte le nom d'un plugin présent dans Data.
func patchNameHint(_ opt: FomodOption, _ installedBasenames: Set<String>) -> Bool {
    var names = (opt.files + opt.folders).map { rxNonAlnum.sub("", norm($0.source).lastSlashComponent.pyLower) }
    names = names.filter { $0.contains("patch") }
    if names.isEmpty { return false }
    for inst in installedBasenames {
        if !inst.hasAnySuffix(pluginExts) || vanillaMasters.contains(inst) { continue }
        let stem = rxNonAlnum.sub("", inst.contains(".") ? inst.pyRPartition(".").0 : inst)
        if stem.pyLen >= 4 && names.contains(where: { $0.contains(stem) }) { return true }
    }
    return false
}

/// nil si l'option n'a pas de master extérieur au mod (ou Data non défini) ; sinon vrai si tous ses masters sont présents.
func mastersSatisfied(_ opt: FomodOption, _ installedBasenames: Set<String>) -> Bool? {
    if installedBasenames.isEmpty || opt.requiredMasters.isEmpty { return nil }
    return opt.requiredMasters.isSubset(of: installedBasenames)
}

/// Vrai si l'option est justifiée par le contenu du dossier Data (badge « Auto »).
public func optionMatchesInstalled(_ opt: FomodOption, _ installedBasenames: Set<String>, _ activeFlags: [String: String]) -> Bool {
    if installedBasenames.isEmpty { return false }
    if let td = opt.typeDescriptor {
        for pat in td.patterns where evaluateDependencies(pat.dependencies, installedBasenames, activeFlags) {
            if ["recommended", "required", "highlight"].contains(pat.typeName.pyLower) && hasFileDep(pat.dependencies) { return true }
            break  // seul le premier motif satisfait détermine le type
        }
    }
    if hasFileDep(opt.dependencies) && evaluateDependencies(opt.dependencies, installedBasenames, activeFlags) { return true }
    if let ok = mastersSatisfied(opt, installedBasenames) { return ok }
    return patchNameHint(opt, installedBasenames)
}

/// Détermine si une option ou patch doit être auto-cochée.
public func isOptionRecommended(_ opt: FomodOption, _ installedBasenames: Set<String>, _ activeFlags: [String: String]) -> Bool {
    let eff = computeOptionType(opt, installedBasenames, activeFlags).pyLower
    if ["recommended", "required", "highlight"].contains(eff) { return true }
    if eff == "notusable" { return false }
    if hasFileDep(opt.dependencies) { return evaluateDependencies(opt.dependencies, installedBasenames, activeFlags) }
    if let ok = mastersSatisfied(opt, installedBasenames) { return ok }
    if !installedBasenames.isEmpty && patchNameHint(opt, installedBasenames) { return true }
    return false
}

private let rxXmlDecl = Rx("^\\s*<\\?xml[^>]*\\?>", ignoreCase: true)
private let rxControl = Rx("[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f]")
private let rxBareAmp = Rx("&(?!(?:[a-zA-Z]+|#\\d+|#x[0-9a-fA-F]+);)")

/// Parse un XML FOMOD tolérant : BOM, déclaration d'encodage déjà décodée, caractères de contrôle parasites ;
/// les espaces de noms sont retirés des balises par l'analyseur.
func loadXMLRoot(_ xmlText: String) throws -> XNode {
    var cleaned = xmlText.pyLStrip("\u{FEFF}").replacingOccurrences(of: "\u{0}", with: "")
    cleaned = rxXmlDecl.sub("", cleaned, count: 1).pyStrip
    cleaned = rxControl.sub("", cleaned)
    cleaned = rxBareAmp.sub("&amp;", cleaned)
    return try parseXMLTree(cleaned)
}

/// Applique l'attribut order (Explicit | Ascending | Descending) du conteneur.
private func ordered(_ elements: [XNode], _ container: XNode?) -> [XNode] {
    let order = container.map { (attr($0, "order", default: "") ?? "").pyStrip.pyLower } ?? ""
    func nameKey(_ e: XNode) -> String { (attr(e, "name", default: "") ?? "").pyLower }
    if order == "ascending" {
        return elements.enumerated().sorted { a, b in
            let ka = nameKey(a.element), kb = nameKey(b.element)
            return ka == kb ? a.offset < b.offset : ka.pyLess(kb)
        }.map(\.element)
    }
    if order == "descending" {
        // sorted(..., reverse=True) de Python garde l'ordre d'origine des éléments égaux
        return elements.enumerated().sorted { a, b in
            let ka = nameKey(a.element), kb = nameKey(b.element)
            return ka == kb ? a.offset < b.offset : kb.pyLess(ka)
        }.map(\.element)
    }
    return elements
}

private func truthy(_ v: String?) -> Bool { ["true", "1", "yes"].contains((v ?? "").pyStrip.pyLower) }

/// Lit les <file>/<folder> d'un conteneur <files> ou <requiredInstallFiles>.
func parseFileList(_ container: XNode?) -> [FomodItem] {
    var items: [FomodItem] = []
    guard let container = container else { return items }
    for el in container.iter() {
        let tag = localTag(el.tag)
        guard tag == "file" || tag == "folder" else { continue }
        guard let rawSrc = attr(el, "source") else { continue }
        let src = norm(rawSrc)
        let rawDst = attr(el, "destination")
        let dst = rawDst == nil ? src : norm(rawDst)
        let prio = pyInt((attr(el, "priority", default: "0") ?? "0").pyStrip) ?? 0
        let item = FomodItem(kind: tag == "file" ? .file : .folder, source: src, destination: dst, priority: prio,
                             alwaysInstall: truthy(attr(el, "alwaysInstall")), installIfUsable: truthy(attr(el, "installIfUsable")))
        if tag == "file" {
            if !src.isEmpty { items.append(item) }
        } else {
            items.append(item)  // Un dossier source vide désigne la racine du mod
        }
    }
    return items
}

/// `int(s)` de Python pour une chaîne déjà nettoyée : signe optionnel, chiffres, tirets bas entre chiffres.
func pyInt(_ s: String) -> Int? {
    if s.isEmpty { return nil }
    var t = Substring(s)
    var neg = false
    if t.first == "+" || t.first == "-" { neg = t.first == "-"; t = t.dropFirst() }
    if t.isEmpty || t.first == "_" || t.last == "_" || t.contains("__") { return nil }
    let digits = t.replacingOccurrences(of: "_", with: "")
    guard !digits.isEmpty, digits.unicodeScalars.allSatisfy({ $0.properties.numericType == .decimal }) else { return nil }
    var n = 0
    for u in digits.unicodeScalars {
        guard let d = u.properties.numericValue else { return nil }
        let (m, o1) = n.multipliedReportingOverflow(by: 10)
        let (a, o2) = m.addingReportingOverflow(Int(d))
        if o1 || o2 { return nil }
        n = a
    }
    return neg ? -n : n
}

private func parseTypeDescriptor(_ plEl: XNode) -> TypeDescriptor? {
    guard let tdEl = child(plEl, "typeDescriptor") else { return nil }
    if let dtEl = child(tdEl, "dependencyType") {
        let defEl = child(dtEl, "defaultType")
        var defName = defEl.flatMap { attr($0, "name", default: "Optional") } ?? "Optional"
        if defName.isEmpty { defName = "Optional" }
        var patterns: [TypeDescriptorPattern] = []
        if let pats = child(dtEl, "patterns") {
            for patEl in children(pats, "pattern") {
                let deps = parseConditionContainer(child(patEl, "dependencies")) ?? FomodDependencies()
                let tEl = child(patEl, "type")
                var tName = tEl.flatMap { attr($0, "name", default: "Optional") } ?? "Optional"
                if tName.isEmpty { tName = "Optional" }
                patterns.append(TypeDescriptorPattern(dependencies: deps, typeName: tName))
            }
        }
        return TypeDescriptor(defaultType: defName, patterns: patterns)
    }
    if let tEl = child(tdEl, "type") {
        var n = attr(tEl, "name", default: "Optional") ?? "Optional"
        if n.isEmpty { n = "Optional" }
        return TypeDescriptor(defaultType: n, patterns: [])
    }
    return nil
}

private func elementText(_ el: XNode?) -> String { el.map { ($0.text ?? "").pyStrip } ?? "" }

public struct ModuleConfig {
    public var moduleName: String
    public var steps: [FomodStep]
    public var requiredFiles: [FomodItem]
    public var conditionalInstalls: [ConditionalInstallPattern]
}

public struct FomodParseError: Error, CustomStringConvertible {
    public let message: String
    public var description: String { message }
}

/// Analyse ModuleConfig.xml (schéma ModConfig 5.0 et variantes rencontrées dans les mods réels).
public func parseModuleConfigXML(_ xmlText: String) throws -> ModuleConfig {
    if xmlText.pyStrip.isEmpty {
        return ModuleConfig(moduleName: "Mod sans configuration FOMOD", steps: [], requiredFiles: [], conditionalInstalls: [])
    }
    let root: XNode
    do { root = try loadXMLRoot(xmlText) } catch {
        throw FomodParseError(message: "Erreur de syntaxe XML : \(error)")
    }

    var moduleName = elementText(child(root, "moduleName"))
    if moduleName.isEmpty {
        for ch in root.iter() where localTag(ch.tag) == "modulename" && !elementText(ch).isEmpty {
            moduleName = elementText(ch)
            break
        }
    }
    if moduleName.isEmpty {
        moduleName = attr(root, "name", default: "Mod Skyrim") ?? "Mod Skyrim"
        if moduleName.isEmpty { moduleName = "Mod Skyrim" }
    }

    var requiredFiles: [FomodItem] = []
    for reqNode in root.iter() where localTag(reqNode.tag) == "requiredinstallfiles" {
        requiredFiles.append(contentsOf: parseFileList(reqNode))
    }

    let stepElements: [XNode]
    if let sc = child(root, "installSteps") {
        stepElements = ordered(children(sc, "installStep"), sc)
    } else {
        stepElements = root.iter().filter { ["installstep", "step"].contains(localTag($0.tag)) }
    }

    var steps: [FomodStep] = []
    for (stepIdx, stepEl) in stepElements.enumerated() {
        var stepName = (attr(stepEl, "name", default: "") ?? "").pyStrip
        if stepName.isEmpty { stepName = elementText(child(stepEl, "name")) }
        if stepName.isEmpty { stepName = "Étape \(stepIdx + 1)" }

        let visibility = parseConditionContainer(child(stepEl, "visible"))

        let groupElements: [XNode]
        if let gc = child(stepEl, "optionalFileGroups") {
            groupElements = ordered(children(gc, "group"), gc)
        } else {
            groupElements = stepEl.iter().filter { ["group", "optionalfilegroup"].contains(localTag($0.tag)) }
        }

        var groups: [FomodGroup] = []
        for (grpIdx, grpEl) in groupElements.enumerated() {
            var groupName = (attr(grpEl, "name", default: "") ?? "").pyStrip
            if groupName.isEmpty { groupName = elementText(child(grpEl, "name")) }
            if groupName.isEmpty { groupName = "Groupe \(grpIdx + 1)" }

            var rawType = attr(grpEl, "type", default: "SelectAny") ?? "SelectAny"
            if rawType.isEmpty { rawType = "SelectAny" }
            rawType = rawType.pyStrip
            let grpType = GroupType.allCases.first { $0.rawValue.pyLower == rawType.pyLower } ?? .selectAny

            let pluginElements: [XNode]
            if let pc = child(grpEl, "plugins") {
                pluginElements = ordered(children(pc, "plugin"), pc)
            } else {
                pluginElements = grpEl.iter().filter { ["plugin", "option"].contains(localTag($0.tag)) }
            }

            var options: [FomodOption] = []
            for (plIdx, plEl) in pluginElements.enumerated() {
                var optName = (attr(plEl, "name", default: "") ?? "").pyStrip
                if optName.isEmpty { optName = elementText(child(plEl, "name", "text")) }

                let desc = elementText(child(plEl, "description"))
                var imagePath = extractElementImage(child(plEl, "image"))
                if imagePath == nil || imagePath!.isEmpty { imagePath = extractElementImage(plEl) }
                if imagePath != nil && imagePath!.isEmpty { imagePath = nil }

                let items = parseFileList(child(plEl, "files"))
                let files = items.filter { $0.kind == .file }
                let folders = items.filter { $0.kind == .folder }

                if optName.isEmpty {
                    if let first = files.first ?? folders.first {
                        optName = first.source.lastSlashComponent
                    } else {
                        optName = "Option \(plIdx + 1)"
                    }
                }

                var flags: [String: String] = [:]
                if let cf = child(plEl, "conditionFlags") {
                    for flEl in children(cf, "flag") {
                        guard let fname = attr(flEl, "name"), !fname.isEmpty else { continue }
                        if let t = flEl.text {
                            flags[fname] = t.pyStrip
                        } else {
                            let v = attr(flEl, "value", default: "") ?? ""
                            flags[fname] = v
                        }
                    }
                }

                let typeDesc = parseTypeDescriptor(plEl)
                let deps = parseConditionContainer(child(plEl, "dependencies"))
                let tdDefault = typeDesc.map { $0.defaultType.pyLower } ?? ""
                let isDef = tdDefault == "recommended" || tdDefault == "required"

                options.append(FomodOption(
                    id: "step_\(stepIdx)_grp_\(grpIdx)_opt_\(plIdx)", name: optName, description: desc, imagePath: imagePath,
                    files: files, folders: folders, flags: flags, dependencies: deps, typeDescriptor: typeDesc, isDefault: isDef))
            }
            groups.append(FomodGroup(id: "step_\(stepIdx)_grp_\(grpIdx)", name: groupName, type: grpType, options: options))
        }
        steps.append(FomodStep(id: "step_\(stepIdx)", name: stepName, groups: groups, visibility: visibility))
    }

    var conditional: [ConditionalInstallPattern] = []
    for cNode in root.iter() where localTag(cNode.tag) == "conditionalfileinstalls" {
        guard let pats = child(cNode, "patterns") else { continue }
        for patEl in children(pats, "pattern") {
            let patDeps = parseConditionContainer(child(patEl, "dependencies")) ?? FomodDependencies()
            let items = parseFileList(child(patEl, "files"))
            conditional.append(ConditionalInstallPattern(
                dependencies: patDeps, files: items.filter { $0.kind == .file }, folders: items.filter { $0.kind == .folder }))
        }
    }
    return ModuleConfig(moduleName: moduleName, steps: steps, requiredFiles: requiredFiles, conditionalInstalls: conditional)
}

/// Analyse info.xml pour extraire les métadonnées (nom, auteur, version, description, website).
public func parseInfoXML(_ xmlText: String) -> FomodMetadata {
    do {
        let root = try loadXMLRoot(xmlText)
        func getText(_ tags: [String]) -> String {
            for tag in tags {
                for el in root.iter() where el.tag.pyLower == tag.pyLower {
                    if let t = el.text, !t.isEmpty { return t.pyStrip }
                }
            }
            return ""
        }
        func or(_ a: String, _ b: String) -> String { a.isEmpty ? b : a }
        return FomodMetadata(
            name: or(getText(["Name", "ModName", "Title"]), "Mod Skyrim"),
            author: or(getText(["Author", "Authors"]), "Inconnu"),
            version: or(getText(["Version"]), "1.0.0"),
            website: or(getText(["Website", "URL", "Homepage", "Link"]), ""),
            description: or(getText(["Description", "Summary", "Details"]), "(Aucune description disponible)"))
    } catch {
        return FomodMetadata(name: "Mod Skyrim", author: "Inconnu", version: "1.0.0", website: "", description: "(Impossible de lire info.xml)")
    }
}
