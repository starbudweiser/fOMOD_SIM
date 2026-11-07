// Réglages : clé « language » (« auto » ou fr/en/es/it). La version Python (QSettings « SkyrimTools/FOMODSimulator »)
// écrivait dans ~/Library/Preferences/com.skyrimtools.fomodsimulator.plist, le même domaine que cette appli : la clé
// est reprise telle quelle, sans migration.

import Foundation

public enum LangChoice {
    public static let auto = "auto"
    /// Entrées du menu Langue, dans leur propre langue.
    public static let menuLangs: [(code: String, label: String)] = [("fr", "Français"), ("en", "English"), ("es", "Español"), ("it", "Italiano")]

    public static func normalize(_ choice: String?) -> String {
        let c = (choice ?? "").trimmingCharacters(in: .whitespaces)
        return I18n.langs[c] != nil ? c : auto
    }

    /// Langue à afficher pour un choix mémorisé.
    public static func resolve(_ choice: String?, preferred: [String] = Locale.preferredLanguages) -> String {
        let c = normalize(choice)
        return c == auto ? I18n.systemLang(preferred) : c
    }
}

public final class AppSettings: @unchecked Sendable {
    private let defaults: UserDefaults

    /// `suite` : domaine de préférences d'essai (jamais celui de l'utilisateur) ; nil = préférences de l'appli.
    public init(suite: String? = nil) {
        defaults = suite.flatMap { UserDefaults(suiteName: $0) } ?? .standard
    }

    public func string(_ key: String, _ def: String = "") -> String { defaults.string(forKey: key) ?? def }
    public func set(_ key: String, _ value: String) { defaults.set(value, forKey: key) }
}

/// Chemin ouvert au lancement : premier argument qui n'est pas une option macOS (-psn_…, -AppleLanguages « (en) »).
public func launchArgumentPath(_ args: [String]) -> String? {
    args.first { !$0.hasPrefix("-") && !$0.hasPrefix("(") }
}
