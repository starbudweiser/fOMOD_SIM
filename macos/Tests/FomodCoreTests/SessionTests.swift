import XCTest
@testable import FomodCore

// Reproduction de « LMMC - Randomizer » : All in One / Modular + étape Modular conditionnelle
let lmmcLike = config(
    step("Résolution", group("Resolution", "SelectExactlyOne",
        plugin("16:9", files: "<folder source=\"16-9\" destination=\"\"/>") + plugin("16:10", files: "<folder source=\"16-10\" destination=\"\"/>")))
    + step("Installation", group("Installation Options", "SelectExactlyOne",
        plugin("All in One", files: "<folder source=\"wallpapers\" destination=\"wallpapers\"/>")
        + plugin("Modular", flags: "<flag name=\"modular\">On</flag>")))
    + step("Modular Selection", group("Modular Selection", "SelectAtLeastOne",
        plugin("Dragon", files: "<folder source=\"wallpapers/Dragon\" destination=\"wallpapers/Dragon\"/>")
        + plugin("Bear", files: "<folder source=\"wallpapers/Bear\" destination=\"wallpapers/Bear\"/>")),
        visible: "<dependencies operator=\"And\"><flagDependency flag=\"modular\" value=\"On\"/></dependencies>"))

func lmmcIndex() -> ArchiveIndex {
    makeIndex("16-9/meshes/logo.nif", "16-10/meshes/logo.nif", "wallpapers/Dragon/a.dds", "wallpapers/Bear/b.dds",
              "wallpapers/Wolf/c.dds", "fomod/ModuleConfig.xml")
}

func newSession(_ xml: String, _ installed: Set<String> = []) throws -> (InstallSession, [FomodStep]) {
    let c = try parseModuleConfigXML(xml)
    return (InstallSession(steps: c.steps, requiredFiles: c.requiredFiles, conditionalInstalls: c.conditionalInstalls, installedBasenames: installed), c.steps)
}

final class StepVisibilityTests: XCTestCase {
    var steps: [FomodStep] = []
    var session: InstallSession!

    override func setUpWithError() throws { (session, steps) = try newSession(lmmcLike) }

    func opt(_ stepIdx: Int, _ name: String) -> (FomodOption, FomodGroup) {
        let g = steps[stepIdx].groups[0]
        return (g.options.first { $0.name == name }!, g)
    }

    func testVisibilityParsed() {
        XCTAssertNil(steps[0].visibility)
        XCTAssertNotNil(steps[2].visibility)
    }

    func testAllInOneHidesModularStepAndInstallsEverything() {
        XCTAssertEqual(session.visibleStepIndices(), [0, 1])
        let res = session.buildStaging(lmmcIndex())
        XCTAssertTrue(res.items.map(\.destinationPath).contains("wallpapers/Wolf/c.dds"))
        XCTAssertEqual(res.missingCount, 0)
        XCTAssertFalse(session.selectedOptions().map(\.name).contains("Dragon"))
    }

    func testModularShowsStepAndInstallsOnlyChecked() {
        let (o, g) = opt(1, "Modular")
        XCTAssertTrue(session.toggle(o, group: g))
        XCTAssertEqual(session.activeFlags, ["modular": "On"])
        XCTAssertEqual(session.visibleStepIndices(), [0, 1, 2])
        let dests = Set(session.buildStaging(lmmcIndex()).items.map(\.destinationPath))
        XCTAssertFalse(dests.contains("wallpapers/Wolf/c.dds"))
        XCTAssertTrue(dests.contains("wallpapers/Dragon/a.dds"))
    }

    func testBackToAllInOneHidesStepAgain() {
        let (mod, g) = opt(1, "Modular")
        let (aio, _) = opt(1, "All in One")
        session.toggle(mod, group: g)
        session.toggle(aio, group: g)
        XCTAssertEqual(session.visibleStepIndices(), [0, 1])
        XCTAssertEqual(session.activeFlags, [:])
    }
}

final class FlagsAndConditionsTests: XCTestCase {
    func testFlagValueIsTagText() throws {
        let xml = config(
            step("Corps", group("Body", "SelectExactlyOne",
                plugin("CBBE", flags: "<flag name=\"body\">CBBE</flag>") + plugin("UNP", flags: "<flag name=\"body\">UNP</flag>")))
            + step("Textures UNP", group("T", "SelectExactlyOne", plugin("UNP tex", files: "<file source=\"unp.dds\"/>")),
                   visible: "<flagDependency flag=\"body\" value=\"UNP\"/>"))
        let (s, steps) = try newSession(xml)
        XCTAssertEqual(steps[0].groups[0].options[1].flags, ["body": "UNP"])
        XCTAssertEqual(s.visibleStepIndices(), [0])
        s.toggle(steps[0].groups[0].options[1], group: steps[0].groups[0])
        XCTAssertEqual(s.visibleStepIndices(), [0, 1])
    }

    func testVisibleWithOrAndFileDependency() throws {
        let xml = config(
            step("A", group("G", "SelectAny", plugin("x", files: "<file source=\"x.esp\"/>")))
            + step("Patch USSEP", group("P", "SelectAny", plugin("p", files: "<file source=\"p.esp\"/>")),
                   visible: "<dependencies operator=\"Or\"><fileDependency file=\"Unofficial Skyrim Special Edition Patch.esp\" state=\"Active\"/>"
                   + "<flagDependency flag=\"force\" value=\"yes\"/></dependencies>"))
        XCTAssertEqual(try newSession(xml).0.visibleStepIndices(), [0])
        let withUssep = try newSession(xml, ["unofficial skyrim special edition patch.esp"]).0
        XCTAssertEqual(withUssep.visibleStepIndices(), [0, 1])
    }

    func testGameVersionDependencyAssumedTrue() throws {
        let xml = config(step("A", group("G", "SelectAny", plugin("x")),
                              visible: "<dependencies operator=\"And\"><gameDependency version=\"1.5.97\"/></dependencies>"))
        XCTAssertEqual(try newSession(xml).0.visibleStepIndices(), [0])
    }

    func testConditionalInstallsUseFlags() throws {
        let xml = config(step("Body", group("B", "SelectExactlyOne",
            plugin("CBBE", flags: "<flag name=\"b\">cbbe</flag>") + plugin("3BA", flags: "<flag name=\"b\">3ba</flag>"))))
            .replacingOccurrences(of: "</installSteps>", with:
                "</installSteps><conditionalFileInstalls><patterns><pattern><dependencies><flagDependency flag=\"b\" value=\"3ba\"/>"
                + "</dependencies><files><folder source=\"3ba\" destination=\"\"/></files></pattern></patterns></conditionalFileInstalls>")
        let (s, steps) = try newSession(xml)
        let idx = makeIndex("3ba/meshes/body.nif")
        XCTAssertEqual(s.buildStaging(idx).copiedCount, 0)
        s.toggle(steps[0].groups[0].options[1], group: steps[0].groups[0])
        XCTAssertEqual(s.buildStaging(idx).items.map(\.destinationPath), ["meshes/body.nif"])
    }
}

final class GroupRulesTests: XCTestCase {
    func session(_ gtype: String, _ plugins: String) throws -> (FomodGroup, InstallSession) {
        let (s, steps) = try newSession(config(step("S", group("G", gtype, plugins))))
        return (steps[0].groups[0], s)
    }

    func testExactlyOneSelectsFirstAndCannotBeEmptied() throws {
        let (g, s) = try session("SelectExactlyOne", plugin("a") + plugin("b"))
        XCTAssertEqual(s.selected, [g.options[0].id])
        XCTAssertFalse(s.toggle(g.options[0], group: g))
        XCTAssertEqual(s.selected, [g.options[0].id])
    }

    func testExactlyOnePrefersRecommended() throws {
        let (g, s) = try session("SelectExactlyOne", plugin("a") + plugin("b", typeName: "Recommended"))
        XCTAssertEqual(s.selected, [g.options[1].id])
    }

    func testAtMostOneCanBeEmptied() throws {
        let (g, s) = try session("SelectAtMostOne", plugin("a") + plugin("b"))
        XCTAssertEqual(s.selected, [])
        s.toggle(g.options[0], group: g)
        s.toggle(g.options[0], group: g)
        XCTAssertEqual(s.selected, [])
    }

    func testAtLeastOneKeepsOne() throws {
        let (g, s) = try session("SelectAtLeastOne", plugin("a") + plugin("b"))
        XCTAssertEqual(s.selected, [g.options[0].id])
        XCTAssertFalse(s.toggle(g.options[0], group: g))
        s.toggle(g.options[1], group: g)
        XCTAssertTrue(s.toggle(g.options[0], group: g))
        XCTAssertEqual(s.selected, [g.options[1].id])
    }

    func testSelectAllIsLocked() throws {
        let (g, s) = try session("SelectAll", plugin("a") + plugin("b"))
        XCTAssertEqual(s.selected, Set(g.options.map(\.id)))
        XCTAssertFalse(s.toggle(g.options[0], group: g))
    }

    func testRequiredAndNotUsable() throws {
        let (g, s) = try session("SelectAny", plugin("req", typeName: "Required") + plugin("no", typeName: "NotUsable"))
        XCTAssertEqual(s.selected, [g.options[0].id])
        XCTAssertFalse(s.toggle(g.options[0], group: g))
        XCTAssertFalse(s.toggle(g.options[1], group: g))
    }

    func testDependencyTypePattern() throws {
        let td = "<typeDescriptor><dependencyType><defaultType name=\"Optional\"/><patterns><pattern>"
            + "<dependencies operator=\"And\"><fileDependency file=\"SkyUI_SE.esp\" state=\"Active\"/></dependencies>"
            + "<type name=\"Recommended\"/></pattern></patterns></dependencyType></typeDescriptor>"
        let xml = config(step("S", group("G", "SelectAny", "<plugin name=\"skyui patch\"><description/>" + td + "</plugin>")))
        XCTAssertEqual(try newSession(xml).0.selected, [])
        XCTAssertEqual(try newSession(xml, ["skyui_se.esp"]).0.selected.count, 1)
    }
}

final class OrderAndFilesTests: XCTestCase {
    func testOrderAttributes() throws {
        let xml = config(
            step("Zeta", group("G", "SelectAny", plugin("b") + plugin("a"), order: "Ascending"))
            + step("Alpha", group("G", "SelectAny", plugin("c"))), stepsOrder: "Ascending")
        let steps = try parseModuleConfigXML(xml).steps
        XCTAssertEqual(steps.map(\.name), ["Alpha", "Zeta"])
        XCTAssertEqual(steps[1].groups[0].options.map(\.name), ["a", "b"])
    }

    func testExplicitOrderKept() throws {
        let xml = config(step("Z", group("G", "SelectAny", "")) + step("A", group("G", "SelectAny", "")))
        XCTAssertEqual(try parseModuleConfigXML(xml).steps.map(\.name), ["Z", "A"])
    }

    func testMissingDestinationDefaultsToSource() throws {
        let xml = config(step("S", group("G", "SelectAll", plugin("a", files: "<file source=\"Docs\\readme.txt\"/><folder source=\"meshes\"/>"))))
        let opt = try parseModuleConfigXML(xml).steps[0].groups[0].options[0]
        XCTAssertEqual(opt.files[0].destination, "Docs/readme.txt")
        XCTAssertEqual(opt.folders[0].destination, "meshes")
    }

    func testAlwaysInstallAndInstallIfUsable() throws {
        let xml = config(step("S", group("G", "SelectAny",
            plugin("doc", files: "<file source=\"always.txt\" alwaysInstall=\"true\"/>")
            + plugin("usable", files: "<file source=\"usable.txt\" installIfUsable=\"true\"/>")
            + plugin("blocked", files: "<file source=\"blocked.txt\" installIfUsable=\"true\"/>", typeName: "NotUsable"))))
        let (s, _) = try newSession(xml)
        XCTAssertEqual(s.selected, [])
        let dests = Set(s.buildStaging(makeIndex("always.txt", "usable.txt", "blocked.txt")).items.map(\.destinationPath))
        XCTAssertEqual(dests, ["always.txt", "usable.txt"])
    }

    func testFolderDoesNotGrabHomonyms() throws {
        let xml = config(step("S", group("G", "SelectAll", plugin("core", files: "<folder source=\"00 Core/textures\" destination=\"textures\"/>"))))
        let (s, _) = try newSession(xml)
        let idx = makeIndex("00 Core/textures/a.dds", "01 Option/textures/b.dds")
        XCTAssertEqual(Set(s.buildStaging(idx).items.map(\.destinationPath)), ["textures/a.dds"])
    }

    func testEmptyFolderSourceIsModRoot() throws {
        let xml = config(step("S", group("G", "SelectAll", plugin("all", files: "<folder source=\"\" destination=\"\"/>"))))
        let (s, _) = try newSession(xml)
        let idx = makeIndex("plugin.esp", "meshes/a.nif", "fomod/ModuleConfig.xml")
        XCTAssertEqual(Set(s.buildStaging(idx).items.map(\.destinationPath)), ["plugin.esp", "meshes/a.nif"])
    }
}

final class LookupAndEncodingTests: XCTestCase {
    func testLookupRespectsSegmentBoundaries() {
        let idx = makeIndex("mymod.esp", "Data/mod.esp")
        XCTAssertEqual(findFileInIndex(idx, "mod.esp")?.path, "Data/mod.esp")
        XCTAssertNil(findFolderInIndex(makeIndex("xtextures/a.dds"), "textures"))
    }

    func testImageExtensionFallback() {
        let idx = makeIndex("Images/shot 1.jpg")
        XCTAssertEqual(findImageInIndex(idx, "Images\\shot 1.png")?.path, "Images/shot 1.jpg")
    }

    func testUTF16WithoutBOMAndBareAmpersand() throws {
        let xml = config(step("Tops & Bottoms", group("G", "SelectAny", plugin("a"))))
        let utf16 = Data(xml.utf16.flatMap { [UInt8($0 & 0xFF), UInt8($0 >> 8)] })        // sans BOM
        let withBOM = Data([0xFF, 0xFE]) + utf16
        for raw in [utf16, withBOM] {
            let steps = try parseModuleConfigXML(decodeXMLText(raw)).steps
            XCTAssertEqual(steps[0].name, "Tops & Bottoms")
        }
    }
}
