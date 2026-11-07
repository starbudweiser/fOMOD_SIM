import XCTest
@testable import FomodCore

final class EmbersXDTests: XCTestCase {
    func testEmbersXDInterpretationAndStaging() throws {
        let c = try parseModuleConfigXML(embersXdXML)
        XCTAssertEqual(c.moduleName, "Embers XD")
        XCTAssertEqual(c.steps.count, 5)
        XCTAssertEqual(c.conditionalInstalls.count, 5)

        let installed: Set<String> = ["gourmettables.esp", "dumplingsbykadraeus.esp", "windhelm_braziers.esp", "lanterns of skyrim ii.esm"]
        var activeFlags = ["New": "active", "EmbersXD": "active", "HD": "active", "Magick": "active", "ReducedActorFlames": "active"]
        let patchOpts = c.steps[4].groups[0].options

        XCTAssertTrue(isOptionRecommended(patchOpts[0], installed, activeFlags))   // Crispy Dumplings
        XCTAssertTrue(isOptionRecommended(patchOpts[1], installed, activeFlags))   // Gourmet
        XCTAssertFalse(isOptionRecommended(patchOpts[2], installed, activeFlags))  // Windhelm BOS (LOS2 actif)
        XCTAssertTrue(isOptionRecommended(patchOpts[3], installed, activeFlags))   // Windhelm BOS + LOS2

        let selected = [
            c.steps[0].groups[0].options[0], c.steps[1].groups[0].options[0], c.steps[2].groups[0].options[0],
            c.steps[3].groups[0].options[0], patchOpts[0], patchOpts[1], patchOpts[3],
        ]
        for o in selected { for (k, v) in o.flags { activeFlags[k] = v } }

        let entries: [(String, String)] = [
            ("plugins/esm/Embers XD.esp", "esp"), ("plugins/esm/Embers XD.esm", "esm"),
            ("plugins/magick/Embers XD - Fire Magick Add-On.esp", "magick"),
            ("patches/Reduced_Actor_Flames/Embers XD - Reduced Actor Flames.esp", "flames"),
            ("patches/Gourmet/Embers XD - Patch - Gourmet Tables.esp", "gourmet"),
            ("patches/Windhelm_Braziers_BSO-LOS2/Embers XD - Patch - Windhelm Braziers BOS - LOSII_SWAP.ini", "ini"),
            ("patches/Windhelm_Braziers_BSO-LOS2/Embers XD - Patch - Windhelm Braziers BOS.esp", "bos"),
            ("assets/core/meshes/common/mesh.nif", "mesh"),
        ]
        var files = OrderedDict<VirtualFileEntry>()
        for (p, d) in entries { files[p.lowercased()] = VirtualFileEntry(path: p, data: Data(d.utf8)) }
        var dirs = OrderedDict<String>()
        dirs["plugins/esm"] = "plugins/esm"
        dirs["patches/gourmet"] = "patches/Gourmet"
        dirs["patches/windhelm_braziers_bso-los2"] = "patches/Windhelm_Braziers_BSO-LOS2"
        dirs["assets/core/meshes/common"] = "assets/core/meshes/common"
        let index = ArchiveIndex(files: files, dirs: dirs)

        let res = buildStaging(selectedOptions: selected, requiredFiles: [], archiveIndex: index,
                               conditionalInstalls: c.conditionalInstalls, activeFlags: activeFlags, installedBasenames: installed)
        let esps = res.items.map(\.destinationPath).filter { $0.lowercased().hasSuffix(".esp") }
        XCTAssertGreaterThan(esps.count, 1)
        for n in ["Embers XD.esp", "Embers XD - Fire Magick Add-On.esp", "Embers XD - Reduced Actor Flames.esp",
                  "Embers XD - Patch - Gourmet Tables.esp", "Embers XD - Patch - Windhelm Braziers BOS.esp"] {
            XCTAssertTrue(esps.contains(n), n)
        }
    }
}
