import XCTest
@testable import FomodCore

/// Archive virtuelle à partir de chemins (fichiers de 10 octets, dossiers déduits).
func makeIndex(_ paths: String...) -> ArchiveIndex {
    var files = OrderedDict<VirtualFileEntry>()
    var dirs = OrderedDict<String>()
    for p in paths {
        files[p.lowercased()] = VirtualFileEntry(path: p, size: 10)
        addParentDirs(of: p, to: &dirs)
    }
    return ArchiveIndex(files: files, dirs: dirs)
}

func plugin(_ name: String, files: String = "", flags: String = "", typeName: String = "Optional", extra: String = "") -> String {
    let flagXML = flags.isEmpty ? "" : "<conditionFlags>\(flags)</conditionFlags>"
    let filesXML = files.isEmpty ? "" : "<files>\(files)</files>"
    return "<plugin name=\"\(name)\"><description>\(name)</description>\(filesXML)\(flagXML)"
        + "<typeDescriptor><type name=\"\(typeName)\"/></typeDescriptor>\(extra)</plugin>"
}

func config(_ stepsXML: String, stepsOrder: String = "Explicit", extra: String = "") -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-16\"?>"
        + "<config xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
        + "xsi:noNamespaceSchemaLocation=\"http://qconsulting.ca/fo3/ModConfig5.0.xsd\">"
        + "<moduleName>Test</moduleName>\(extra)<installSteps order=\"\(stepsOrder)\">\(stepsXML)</installSteps></config>"
}

func step(_ name: String, _ groupsXML: String, visible: String = "") -> String {
    let vis = visible.isEmpty ? "" : "<visible>\(visible)</visible>"
    return "<installStep name=\"\(name)\">\(vis)<optionalFileGroups order=\"Explicit\">\(groupsXML)</optionalFileGroups></installStep>"
}

func group(_ name: String, _ gtype: String, _ pluginsXML: String, order: String = "Explicit") -> String {
    "<group name=\"\(name)\" type=\"\(gtype)\"><plugins order=\"\(order)\">\(pluginsXML)</plugins></group>"
}

/// Dossier d'essai jetable (dans le dossier temporaire du système).
func makeTempDir() -> String {
    let p = NSTemporaryDirectory() + "fomodsim_test_" + UUID().uuidString
    try! FileManager.default.createDirectory(atPath: p, withIntermediateDirectories: true)
    return p
}

func write(_ root: String, _ rel: String, _ text: String) {
    let full = root + "/" + rel
    try! FileManager.default.createDirectory(atPath: (full as NSString).deletingLastPathComponent, withIntermediateDirectories: true)
    try! text.write(toFile: full, atomically: false, encoding: .utf8)
}

/// Crée une archive avec bsdtar (`format` : zip, 7zip) à partir d'un dossier.
func makeArchive(from dir: String, to archive: String, format: String) {
    let r = runTool("/usr/bin/bsdtar", ["--format", format, "--no-mac-metadata", "-cf", archive, "-C", dir, "."])
    precondition(r.status == 0, "bsdtar a échoué")
}
