import XCTest
@testable import FomodCore

/// En-tête TES4 minimal : HEDR puis un MAST + DATA par master.
func makePlugin(_ masters: String...) -> Data {
    func u16(_ v: Int) -> [UInt8] { [UInt8(v & 0xFF), UInt8((v >> 8) & 0xFF)] }
    func u32(_ v: Int) -> [UInt8] { [UInt8(v & 0xFF), UInt8((v >> 8) & 0xFF), UInt8((v >> 16) & 0xFF), UInt8((v >> 24) & 0xFF)] }
    var subs: [UInt8] = Array("HEDR".utf8) + u16(12) + [UInt8](repeating: 0, count: 12)
    for m in masters {
        let name = Array(m.utf8) + [0]
        subs += Array("MAST".utf8) + u16(name.count) + name + Array("DATA".utf8) + u16(8) + [UInt8](repeating: 0, count: 8)
    }
    return Data(Array("TES4".utf8) + u32(subs.count) + [UInt8](repeating: 0, count: 16) + subs)
}

func indexWith(_ plugins: [(String, Data)]) -> ArchiveIndex {
    var files = OrderedDict<VirtualFileEntry>()
    var dirs = OrderedDict<String>()
    for (path, data) in plugins {
        files[path.lowercased()] = VirtualFileEntry(path: path, size: data.count, data: data)
        addParentDirs(of: path, to: &dirs)
    }
    return ArchiveIndex(files: files, dirs: dirs)
}

final class PluginMastersTests: XCTestCase {
    func testParseMasters() {
        XCTAssertEqual(parsePluginMasters(makePlugin("Skyrim.esm", "SkyUI_SE.esp")), ["skyrim.esm", "skyui_se.esp"])
    }

    func testNotAPlugin() {
        XCTAssertEqual(parsePluginMasters(Data([0x50, 0x4B, 3, 4] + [UInt8](repeating: 0, count: 40))), [])
    }
}

// Mod avec un plugin principal et deux patchs en choix unique : USSEP ou non, plus un patch SkyUI
let patchMod = config(
    step("Version", group("Version", "SelectExactlyOne",
        plugin("Standard", files: "<file source=\"Standard/Mod.esp\"/>", typeName: "Recommended")
        + plugin("USSEP", files: "<file source=\"USSEP/Mod.esp\"/>")))
    + step("Patchs", group("Patchs", "SelectAny", plugin("SkyUI", files: "<file source=\"Patches/Mod - UI.esp\"/>"))))

final class PatchPreselectionTests: XCTestCase {
    var steps: [FomodStep] = []
    var standard: FomodOption!, ussep: FomodOption!, ui: FomodOption!

    override func setUpWithError() throws {
        steps = try parseModuleConfigXML(patchMod).steps
        let index = indexWith([
            ("Standard/Mod.esp", makePlugin("Skyrim.esm")),
            ("USSEP/Mod.esp", makePlugin("Skyrim.esm", "Unofficial Skyrim Special Edition Patch.esp")),
            ("Patches/Mod - UI.esp", makePlugin("Skyrim.esm", "Mod.esp", "SkyUI_SE.esp")),
        ])
        annotateOptionMasters(index, steps)
        standard = steps[0].groups[0].options[0]
        ussep = steps[0].groups[0].options[1]
        ui = steps[1].groups[0].options[0]
    }

    func session(_ installed: Set<String> = []) -> InstallSession { InstallSession(steps: steps, installedBasenames: installed) }

    func testMastersExcludeVanillaAndModPlugins() {
        XCTAssertEqual(standard.requiredMasters, [])
        XCTAssertEqual(ussep.requiredMasters, ["unofficial skyrim special edition patch.esp"])
        XCTAssertEqual(ui.requiredMasters, ["skyui_se.esp"])
    }

    func testWithoutDataAuthorDefaults() { XCTAssertEqual(session().selected, [standard.id]) }

    func testDetectedMastersWin() {
        let s = session(["skyrim.esm", "unofficial skyrim special edition patch.esp", "skyui_se.esp"])
        XCTAssertEqual(s.selected, [ussep.id, ui.id])
    }

    func testMissingMasterNotChecked() {
        let s = session(["skyrim.esm", "unofficial skyrim special edition patch.esp"])
        XCTAssertFalse(s.selected.contains(ui.id))
    }
}

final class DataScanTests: XCTestCase {
    func testScanKeepsPluginsAndSkipsAssetFolders() {
        let d = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: d) }
        for rel in ["Skyrim.esm", "SKSE/Plugins/po3.dll", "Mod.bsa", "readme.txt", "textures/fake.esp", "Meshes/x.nif"] { write(d, rel, "") }
        XCTAssertEqual(scanDataDir(d), ["skyrim.esm", "po3.dll", "mod.bsa"])
    }
}
