import XCTest
@testable import FomodCore

// Export du staging : les fichiers non chargés à l'indexation (textures, meshes) sont lus dans l'archive à l'export,
// jamais écrits vides (bug du Lore Main Menu Compendium, 13/10/2026).
let exportConfig = """
<?xml version="1.0" encoding="UTF-8"?>
<config><moduleName>Test</moduleName><installSteps order="Explicit">
<installStep name="Wallpapers"><optionalFileGroups order="Explicit">
<group name="Choix" type="SelectAny"><plugins order="Explicit">
<plugin name="Tous"><description>x</description>
<files><folder source="wallpapers" destination="mainmenuwallpapers"/></files>
<typeDescriptor><type name="Recommended"/></typeDescriptor></plugin>
</plugins></group></optionalFileGroups></installStep></installSteps></config>
"""

// Plusieurs fichiers de même nom dans des dossiers différents, comme MainMenu.dds dans LMMC
let textures: [(String, String)] = ["Alduin", "Dragon War", "Bear Attack (2)"].map {
    ("wallpapers/\($0)/data/textures/loremainmenu/MainMenu.dds", String(repeating: "DDS \($0) ", count: 500))
}

final class StagingExportTests: XCTestCase {
    var tmp = ""
    var index: ArchiveIndex!
    var result: StagingResult!

    override func setUpWithError() throws {
        tmp = makeTempDir()
        let src = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: src) }
        write(src, "fomod/ModuleConfig.xml", exportConfig)
        for (p, d) in textures { write(src, p, d) }
        let archive = tmp + "/mod.zip"
        makeArchive(from: src, to: archive, format: "zip")
        let r = try extractArchive(archive)
        index = r.index
        let c = try parseModuleConfigXML(r.moduleConfigXML)
        result = InstallSession(steps: c.steps, requiredFiles: c.requiredFiles, conditionalInstalls: c.conditionalInstalls).buildStaging(index)
    }

    override func tearDown() { try? FileManager.default.removeItem(atPath: tmp) }

    func testTexturesAreDeferred() {
        XCTAssertEqual(result.items.count, 3)
        XCTAssertTrue(result.items.allSatisfy { $0.data == nil && $0.member != nil })
    }

    func testDirectoryExportHasContent() throws {
        let out = tmp + "/staging"
        XCTAssertEqual(exportStagingToDirectory(result, targetDir: out, archiveIndex: index), [])
        for (p, d) in textures {
            let dest = out + "/" + p.replacingOccurrences(of: "wallpapers/", with: "mainmenuwallpapers/")
            XCTAssertEqual(try String(contentsOfFile: dest, encoding: .utf8), d)
        }
    }

    func testZipExportHasContent() throws {
        let z = tmp + "/out.zip"
        XCTAssertEqual(exportStagingToZip(result, zipPath: z, archiveIndex: index), [])
        let names = Set((listArchive(z) ?? []).filter { !$0.isDir }.map(\.member))
        XCTAssertEqual(names, Set(textures.map { $0.0.replacingOccurrences(of: "wallpapers/", with: "mainmenuwallpapers/") }))
        let back = readArchiveMembers(z, members: Array(names))
        for (p, d) in textures {
            XCTAssertEqual(back[p.replacingOccurrences(of: "wallpapers/", with: "mainmenuwallpapers/")], Data(d.utf8))
        }
    }

    func testUnreadableContentIsReportedNotWrittenEmpty() {
        let out = tmp + "/staging"
        let failures = exportStagingToDirectory(result, targetDir: out, archiveIndex: nil)  // pas d'accès à l'archive
        XCTAssertEqual(failures.count, textures.count)
        for item in result.items {
            XCTAssertFalse(FileManager.default.fileExists(atPath: out + "/" + item.destinationPath))
        }
    }
}

final class StagingFolderNameTests: XCTestCase {
    func testNexusArchiveSuffixRemovedUppercase() {
        XCTAssertEqual(stagingFolderName("/m/5 Main Menu Compendium - Randomizer (16-10)-150450-2-0-1747924526.zip", modName: "LMMC"),
                       "5 MAIN MENU COMPENDIUM - RANDOMIZER (16-10)")
        XCTAssertEqual(stagingFolderName("/m/SLF Hair - Lite 1K-36510-2-0.7z"), "SLF HAIR - LITE 1K")
    }

    func testRecentNexusAndCollectionFormats() {
        let cases = [
            "LMMC - Randomizer (16-9_10) (2K) 150450 2.1.1 2026-09-15T13-16Z izkcFpI8F.7z": "LMMC - RANDOMIZER (16-9_10) (2K)",
            "Accuracy - MCM menu 187578 MCM-01 2026-08-07T23-03Z CmfxYjTwZ.zip": "ACCURACY - MCM MENU",
            "DynDOLOD 3.00 68518 Alpha-208 2026-07-24T09-23Z OyYrPubRn (1).7z": "DYNDOLOD 3.00",
            "Easy_Console_Commands_1.0.25_Ks18n0cJO.zip": "EASY CONSOLE COMMANDS",
            "Lute-3391-.zip": "LUTE",
            "Lock.Picking.Redone.7z": "LOCK.PICKING.REDONE",
        ]
        for (archive, expected) in cases { XCTAssertEqual(stagingFolderName("/m/" + archive), expected, archive) }
    }

    func testVariantsOfSameModGetDistinctFolders() {
        let a = stagingFolderName("/m/LMMC - Randomizer (16-9)-150450-2-0-1.zip", modName: "Lore-Friendly Main Menu Compendium")
        let b = stagingFolderName("/m/LMMC - Randomizer (21-9)-150450-2-0-1.zip", modName: "Lore-Friendly Main Menu Compendium")
        XCTAssertNotEqual(a, b)
    }

    func testFallbackAndForbiddenCharacters() {
        XCTAssertEqual(stagingFolderName(nil, modName: "Nom: du/mod"), "NOM- DU-MOD")
        XCTAssertEqual(stagingFolderName(nil, modName: ""), "MOD FOMOD")
    }
}
