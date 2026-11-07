import XCTest
@testable import FomodCore

final class LaunchArgumentTests: XCTestCase {
    // Équivalent de tests/test_main_cli.py : un chemin passé au lancement ouvre le mod, les options macOS sont ignorées
    func testPathIsFirstNonOption() {
        XCTAssertEqual(launchArgumentPath(["-psn_0_12345", "-AppleLanguages", "(en)", "/tmp/mod.zip"]), "/tmp/mod.zip")
        XCTAssertNil(launchArgumentPath(["-AppleLanguages", "(fr)"]))
        XCTAssertNil(launchArgumentPath([]))
    }
}

final class ConfinementTests: XCTestCase {
    func testExtractionPathStaysInsideOutputFolder() {
        XCTAssertEqual(confinedDest("/out", "../../etc/passwd"), "/out/etc/passwd")
        XCTAssertEqual(confinedDest("/out", "/abs/olute.txt"), "/out/abs/olute.txt")
        XCTAssertEqual(confinedDest("/out", "a/./b/../c.txt"), "/out/a/b/c.txt")
    }

    func testStagingExportNeverWritesOutsideTarget() throws {
        let tmp = makeTempDir()
        defer { try? FileManager.default.removeItem(atPath: tmp) }
        let item = StagingItem(sourcePath: "x.txt", destinationPath: "../../escape.txt", type: "file", size: 3, matchedFromOption: "t", data: Data("abc".utf8))
        let res = StagingResult(items: [item], totalSize: 3, copiedCount: 1, missingCount: 0, log: [])
        exportStagingToDirectory(res, targetDir: tmp + "/staging")
        XCTAssertFalse(FileManager.default.fileExists(atPath: tmp + "/escape.txt"))
        XCTAssertTrue(FileManager.default.fileExists(atPath: tmp + "/staging/escape.txt"))
    }
}

final class SettingsTests: XCTestCase {
    func testLanguageSettingRoundTripInIsolatedSuite() {
        let suite = "test.fomodsim.\(UUID().uuidString)"
        let s = AppSettings(suite: suite)
        XCTAssertEqual(s.string("language", "auto"), "auto")
        s.set("language", "it")
        XCTAssertEqual(AppSettings(suite: suite).string("language"), "it")
        UserDefaults().removePersistentDomain(forName: suite)
    }
}
