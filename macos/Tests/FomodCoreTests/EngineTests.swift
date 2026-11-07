import XCTest
@testable import FomodCore

final class ParserTests: XCTestCase {
    func testNorm() {
        XCTAssertEqual(norm("foo\\bar\\baz"), "foo/bar/baz")
        XCTAssertEqual(norm("./meshes/actor.nif"), "meshes/actor.nif")
        XCTAssertEqual(norm("/textures/skin.dds/"), "textures/skin.dds")
    }

    func testResolveFileDestination() {
        XCTAssertEqual(resolveFileDestination("CBBE_Physics.esp", "03 Physics/CBBE_Physics.esp"), "CBBE_Physics.esp")
        XCTAssertEqual(resolveFileDestination("meshes", "01 Curvy/femalebody.nif"), "meshes/femalebody.nif")
        XCTAssertEqual(resolveFileDestination(".", "Plugin.esp"), "Plugin.esp")
    }

    func testParseInfoXML() {
        let meta = parseInfoXML(sampleCbbeInfoXML)
        XCTAssertTrue(meta.name.contains("Caliente"))
        XCTAssertEqual(meta.author, "Caliente and Ousnius")
        XCTAssertEqual(meta.version, "2.0.3")
        XCTAssertTrue(meta.description.count > 20)
    }

    func testParseModuleConfig() throws {
        let c = try parseModuleConfigXML(sampleCbbeModuleConfigXML)
        XCTAssertTrue(c.moduleName.contains("Caliente"))
        XCTAssertEqual(c.requiredFiles.count, 1)
        XCTAssertEqual(c.requiredFiles[0].source, "00 Core")
        XCTAssertEqual(c.steps.count, 5)
        XCTAssertEqual(c.conditionalInstalls.count, 0)
        let step1 = c.steps[0]
        XCTAssertTrue(step1.name.contains("Silhouette"))
        XCTAssertEqual(step1.groups.count, 1)
        let grp = step1.groups[0]
        XCTAssertEqual(grp.type, .selectExactlyOne)
        XCTAssertEqual(grp.options.count, 3)
        XCTAssertEqual(grp.options[0].name, "CBBE Curvy (Recommandé)")
        XCTAssertTrue(grp.options[0].isDefault)
    }

    func testDependenciesEvaluation() {
        let andFile = FomodDependencies(op: "And", fileDependencies: [FileDependency("SkyUI_SE.esp", "Active")])
        XCTAssertTrue(evaluateDependencies(andFile, ["skyui_se.esp"], [:]))
        XCTAssertFalse(evaluateDependencies(andFile, ["other.esp"], [:]))

        let missing = FomodDependencies(op: "And", fileDependencies: [FileDependency("Lanterns Of Skyrim II.esm", "Missing")])
        XCTAssertTrue(evaluateDependencies(missing, [], [:]))
        XCTAssertFalse(evaluateDependencies(missing, ["lanterns of skyrim ii.esm"], [:]))

        let flagActive = FomodDependencies(op: "And", flagDependencies: [FlagDependency("BodyType", "Curvy")])
        XCTAssertTrue(evaluateDependencies(flagActive, [], ["BodyType": "Curvy"]))
        XCTAssertFalse(evaluateDependencies(flagActive, [], ["BodyType": "Slim"]))

        let flagInactive = FomodDependencies(op: "And", flagDependencies: [FlagDependency("NoParallax", "inactive")])
        XCTAssertTrue(evaluateDependencies(flagInactive, [], [:]))
        XCTAssertTrue(evaluateDependencies(flagInactive, [], ["NoParallax": "inactive"]))
        XCTAssertFalse(evaluateDependencies(flagInactive, [], ["NoParallax": "active"]))
    }

    func testTypeDescriptorAndRecommendation() throws {
        let xml = """
        <config><moduleName>Patch Mod</moduleName><installSteps><installStep name="Patches"><optionalFileGroups>
        <group name="Select" type="SelectAny"><plugins><plugin name="Dumplings Patch"><typeDescriptor><dependencyType>
        <defaultType name="Optional"/><patterns><pattern><dependencies operator="And">
        <fileDependency file="DumplingsbyKadraeus.esp" state="Active"/></dependencies><type name="Recommended"/></pattern></patterns>
        </dependencyType></typeDescriptor></plugin></plugins></group></optionalFileGroups></installStep></installSteps></config>
        """
        let opt = try parseModuleConfigXML(xml).steps[0].groups[0].options[0]
        XCTAssertFalse(isOptionRecommended(opt, [], [:]))
        XCTAssertEqual(computeOptionType(opt, [], [:]), "Optional")
        XCTAssertTrue(isOptionRecommended(opt, ["dumplingsbykadraeus.esp"], [:]))
        XCTAssertEqual(computeOptionType(opt, ["dumplingsbykadraeus.esp"], [:]), "Recommended")
    }

    func testConditionalFileInstalls() throws {
        let xml = """
        <config><moduleName>Exotic Mod</moduleName><installSteps><installStep name="Step 1"><optionalFileGroups>
        <group name="Choice" type="SelectExactlyOne"><plugins><plugin name="Option A">
        <conditionFlags><flag name="StyleA">active</flag></conditionFlags>
        <files><file source="base.esp" destination="base.esp"/></files></plugin></plugins></group></optionalFileGroups></installStep></installSteps>
        <conditionalFileInstalls><patterns><pattern><dependencies operator="And"><flagDependency flag="StyleA" value="active"/></dependencies>
        <files><file source="extra_plugin.esp" destination="extra_plugin.esp" priority="5"/>
        <folder source="extra_folder" destination="" priority="2"/></files></pattern></patterns></conditionalFileInstalls></config>
        """
        let c = try parseModuleConfigXML(xml)
        XCTAssertEqual(c.conditionalInstalls.count, 1)
        XCTAssertEqual(c.conditionalInstalls[0].files.count, 1)
        XCTAssertEqual(c.conditionalInstalls[0].files[0].source, "extra_plugin.esp")

        var files = OrderedDict<VirtualFileEntry>()
        files["base.esp"] = VirtualFileEntry(path: "base.esp", data: Data("base".utf8))
        files["extra_plugin.esp"] = VirtualFileEntry(path: "extra_plugin.esp", data: Data("extra".utf8))
        files["extra_folder/mesh.nif"] = VirtualFileEntry(path: "extra_folder/mesh.nif", data: Data("nif".utf8))
        var dirs = OrderedDict<String>()
        dirs["extra_folder"] = "extra_folder"
        let index = ArchiveIndex(files: files, dirs: dirs)

        let result = buildStaging(selectedOptions: [c.steps[0].groups[0].options[0]], requiredFiles: c.requiredFiles,
                                  archiveIndex: index, conditionalInstalls: c.conditionalInstalls,
                                  activeFlags: ["StyleA": "active"], installedBasenames: [])
        let dest = result.items.map { $0.destinationPath.lowercased() }
        XCTAssertTrue(dest.contains("base.esp"))
        XCTAssertTrue(dest.contains("extra_plugin.esp"))
        XCTAssertTrue(dest.contains("mesh.nif"))
        XCTAssertEqual(result.copiedCount, 3)
    }

    func testReanchorIndex() {
        var files = OrderedDict<VirtualFileEntry>()
        files["root_wrapper/fomod/moduleconfig.xml"] = VirtualFileEntry(path: "root_wrapper/fomod/ModuleConfig.xml")
        files["root_wrapper/00 core/mesh.nif"] = VirtualFileEntry(path: "root_wrapper/00 Core/mesh.nif", size: 100)
        var dirs = OrderedDict<String>()
        dirs["root_wrapper/00 core"] = "root_wrapper/00 Core"
        let (nf, _) = reanchorIndex(files, dirs)
        XCTAssertNotNil(nf["fomod/moduleconfig.xml"])
        XCTAssertEqual(nf["00 core/mesh.nif"]?.path, "00 Core/mesh.nif")
    }

    func testStagingBuild() throws {
        let demo = getDemoMod()
        let c = try parseModuleConfigXML(demo.moduleConfigXML)
        let selected = [c.steps[0].groups[0].options[0], c.steps[1].groups[0].options[1]]
        let result = buildStaging(selectedOptions: selected, requiredFiles: c.requiredFiles, archiveIndex: demo.index,
                                  conditionalInstalls: c.conditionalInstalls)
        XCTAssertTrue(result.copiedCount > 0)
        XCTAssertEqual(result.missingCount, 0)
        let dest = result.items.map { $0.destinationPath.lowercased() }
        XCTAssertTrue(dest.contains { $0.contains("femalehead.nif") })
        XCTAssertTrue(dest.contains { $0.contains("femalebody_0.nif") })
        XCTAssertTrue(dest.contains { $0.contains("femalebody_2k.dds") })
    }

    func testExportToZip() throws {
        let demo = getDemoMod()
        let c = try parseModuleConfigXML(demo.moduleConfigXML)
        let result = buildStaging(selectedOptions: [c.steps[0].groups[0].options[0]], requiredFiles: c.requiredFiles,
                                  archiveIndex: demo.index, conditionalInstalls: c.conditionalInstalls)
        let tmp = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: tmp) }
        let zip = tmp + "/out.zip"
        exportStagingToZip(result, zipPath: zip)
        XCTAssertTrue(FileManager.default.fileExists(atPath: zip))
        let names = (listArchive(zip) ?? []).map(\.member)
        XCTAssertFalse(names.isEmpty)
        XCTAssertTrue(names.contains { $0.contains("femalehead.nif") })
    }
}

final class LocationTests: XCTestCase {
    let strayConfig = "<config><installSteps/></config>"

    func makeTree(_ root: String) {
        write(root, "Mon Mod v1.0/fomod/ModuleConfig.xml", sampleCbbeModuleConfigXML)
        write(root, "Mon Mod v1.0/Fomod/info.xml", sampleCbbeInfoXML)
        // Leurres hors du dossier fomod/ : ne doivent pas être choisis
        write(root, "Mon Mod v1.0/Docs/ModuleConfig.xml", strayConfig)
        write(root, "Mon Mod v1.0/SKSE/Plugins/info.xml", "<plugin/>")
        write(root, "Mon Mod v1.0/00 Core/mod.esp", "esp")
    }

    func assertFound(_ r: ExtractedArchive, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(r.moduleConfigXML.contains("CBBE"), file: file, line: line)
        XCTAssertEqual(r.moduleConfigXML, sampleCbbeModuleConfigXML, file: file, line: line)
        XCTAssertEqual(r.infoXML, sampleCbbeInfoXML, file: file, line: line)
        XCTAssertNotNil(r.index.files["00 core/mod.esp"], file: file, line: line)
    }

    func testNestedFomodIn7z() throws {
        let src = makeTempDir(), out = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: src); try? FileManager.default.removeItem(atPath: out) }
        makeTree(src)
        let archive = out + "/mod.7z"
        makeArchive(from: src, to: archive, format: "7zip")
        assertFound(try extractArchive(archive))
    }

    func testNestedFomodInZip() throws {
        let src = makeTempDir(), out = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: src); try? FileManager.default.removeItem(atPath: out) }
        makeTree(src)
        let archive = out + "/mod.zip"
        makeArchive(from: src, to: archive, format: "zip")
        assertFound(try extractArchive(archive))
    }

    func testNestedFomodInFolder() throws {
        let src = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: src) }
        makeTree(src)
        assertFound(try extractArchive(src))
    }

    func testReanchorIgnoresFolderEndingWithFomod() {
        var files = OrderedDict<VirtualFileEntry>()
        files["mon-fomod/moduleconfig.xml"] = VirtualFileEntry(path: "mon-fomod/ModuleConfig.xml")
        files["mon-fomod/mod.esp"] = VirtualFileEntry(path: "mon-fomod/mod.esp")
        files["autre/readme.txt"] = VirtualFileEntry(path: "autre/readme.txt")
        let (nf, _) = reanchorIndex(files, OrderedDict())
        XCTAssertEqual(Set(nf.keys), Set(files.keys))
    }

    func testArchiveNamesWithGlobCharacters() throws {
        // Les noms contenant * ? [ ne doivent pas être pris pour des motifs par bsdtar
        let src = makeTempDir(), out = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: src); try? FileManager.default.removeItem(atPath: out) }
        write(src, "fomod/ModuleConfig.xml", sampleCbbeModuleConfigXML)
        write(src, "notes/b[1].txt", "AAA")
        write(src, "notes/b1.txt", "BBB")
        write(src, "notes/c*.txt", "CCC")
        let archive = out + "/glob.zip"
        makeArchive(from: src, to: archive, format: "zip")
        let r = try extractArchive(archive)
        XCTAssertEqual(r.index.files["notes/b[1].txt"]?.data, Data("AAA".utf8))
        XCTAssertEqual(r.index.files["notes/b1.txt"]?.data, Data("BBB".utf8))
        XCTAssertEqual(r.index.files["notes/c*.txt"]?.data, Data("CCC".utf8))
    }
}
