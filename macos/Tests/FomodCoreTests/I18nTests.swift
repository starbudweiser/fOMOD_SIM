import XCTest
@testable import FomodCore

final class I18nTests: XCTestCase {
    func testSameKeysInAllLanguages() {
        // Chaque texte français a ses trois traductions, non vides
        for (fr, tr) in translations {
            XCTAssertEqual(tr.count, 3, fr)
            for t in tr { XCTAssertFalse(t.isEmpty, fr) }
        }
        for (id, fr) in textIds { XCTAssertNotNil(translations[fr], id) }
    }

    func testAbout() {
        for lang in ["fr", "en", "it", "es"] {
            I18n.setLang(lang)
            XCTAssertTrue(T("about.menu").contains("fOMODSIM"), lang)
            XCTAssertTrue(T("about.version").contains("{v}"), lang)
            XCTAssertTrue(T("about.version").contains("{b}"), lang)
            for k in ["menu", "version", "tagline", "license", "disclaimer", "credit"] { XCTAssertNotEqual(T("about.\(k)"), "about.\(k)", lang) }
        }
        I18n.setLang("fr")
    }

    func testLanguageChoice() {
        XCTAssertEqual(LangChoice.normalize("xx"), "auto")
        XCTAssertEqual(LangChoice.resolve("auto", preferred: ["it-IT"]), "it")
        XCTAssertEqual(LangChoice.resolve("auto", preferred: ["ja-JP"]), "en")
        XCTAssertEqual(LangChoice.resolve("es", preferred: ["fr-FR"]), "es")
    }
}
