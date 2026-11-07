// Petites fonctions qui se comportent comme celles de Python (str, re, dict) pour que le moteur Swift
// donne exactement les mêmes résultats que la version Python.

import Foundation

/// Dictionnaire à ordre d'insertion (dict de Python) : une clé réaffectée garde sa place.
public struct OrderedDict<Value> {
    public private(set) var keys: [String] = []
    private var dict: [String: Value] = [:]

    public init() {}

    public var count: Int { keys.count }
    public var isEmpty: Bool { keys.isEmpty }

    public subscript(key: String) -> Value? {
        get { dict[key] }
        set {
            if let v = newValue {
                if dict.updateValue(v, forKey: key) == nil { keys.append(key) }
            } else if dict.removeValue(forKey: key) != nil {
                keys.removeAll { $0 == key }
            }
        }
    }

    public func contains(_ key: String) -> Bool { dict[key] != nil }

    /// Paires dans l'ordre d'insertion.
    public var items: [(key: String, value: Value)] { keys.map { ($0, dict[$0]!) } }
    public var values: [Value] { keys.map { dict[$0]! } }
    public var first: (key: String, value: Value)? { keys.first.map { ($0, dict[$0]!) } }
}

// MARK: - str

/// Caractères que `str.strip()` de Python retire (espaces Unicode, séparateurs de contrôle \x1c-\x1f).
private let pyWhitespace: Set<Unicode.Scalar> = {
    var s = Set<Unicode.Scalar>()
    for v: UInt32 in [0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x85, 0xA0, 0x1680,
                      0x2028, 0x2029, 0x202F, 0x205F, 0x3000] { s.insert(Unicode.Scalar(v)!) }
    for v in UInt32(0x2000)...UInt32(0x200A) { s.insert(Unicode.Scalar(v)!) }
    return s
}()

extension String {
    /// `str.strip()`
    public var pyStrip: String { pyStrip(chars: nil) }

    /// `str.strip(chars)` (jeu de caractères donné) ou espaces Python si `chars` est nil.
    public func pyStrip(chars: String?) -> String {
        let set: Set<Unicode.Scalar> = chars.map { Set($0.unicodeScalars) } ?? pyWhitespace
        let u = Array(unicodeScalars)
        var a = 0, b = u.count
        while a < b, set.contains(u[a]) { a += 1 }
        while b > a, set.contains(u[b - 1]) { b -= 1 }
        var v = String.UnicodeScalarView()
        v.append(contentsOf: u[a..<b])
        return String(v)
    }

    /// `str.lstrip(chars)`
    public func pyLStrip(_ chars: String) -> String {
        let set = Set(chars.unicodeScalars)
        var v = unicodeScalars[...]
        while let f = v.first, set.contains(f) { v = v.dropFirst() }
        return String(String.UnicodeScalarView(v))
    }

    /// `str.rstrip(chars)`
    public func pyRStrip(_ chars: String) -> String {
        let set = Set(chars.unicodeScalars)
        var v = unicodeScalars[...]
        while let l = v.last, set.contains(l) { v = v.dropLast() }
        return String(String.UnicodeScalarView(v))
    }

    /// `len(str)` : nombre de points de code.
    public var pyLen: Int { unicodeScalars.count }

    /// Tranche par points de code : `s[a:b]` (indices positifs).
    public func pySlice(_ a: Int, _ b: Int? = nil) -> String {
        let u = unicodeScalars
        let start = u.index(u.startIndex, offsetBy: min(a, u.count))
        let end = b.map { u.index(u.startIndex, offsetBy: min($0, u.count)) } ?? u.endIndex
        guard start <= end else { return "" }
        return String(u[start..<end])
    }

    /// Comparaison par points de code, comme `<` sur des `str` Python.
    public func pyLess(_ other: String) -> Bool {
        unicodeScalars.lexicographicallyPrecedes(other.unicodeScalars)
    }

    /// `str.split("/")` : garde les segments vides.
    public func pySplit(_ sep: Character) -> [String] {
        split(separator: sep, omittingEmptySubsequences: false).map(String.init)
    }

    /// `str.rpartition(sep)` -> (avant, sep ou "", après)
    public func pyRPartition(_ sep: String) -> (String, String, String) {
        guard let r = range(of: sep, options: .backwards) else { return ("", "", self) }
        return (String(self[..<r.lowerBound]), sep, String(self[r.upperBound...]))
    }

    /// Dernier segment après « / » (`s.split("/")[-1]`).
    public var lastSlashComponent: String {
        if let r = range(of: "/", options: .backwards) { return String(self[r.upperBound...]) }
        return self
    }

    /// `s.lower()` : les minuscules de Python (le « İ » donne « i̇ » dans les deux).
    public var pyLower: String { lowercased() }

    /// `str.capitalize()` d'un mot
    public var pyCapitalized: String {
        guard let f = first else { return self }
        return String(f).uppercased() + String(dropFirst()).lowercased()
    }

    public func hasAnySuffix(_ suffixes: [String]) -> Bool { suffixes.contains { hasSuffix($0) } }
}

// MARK: - re

/// Expression régulière compilée une fois (module `re` de Python, ICU derrière).
public final class Rx: @unchecked Sendable {
    let re: NSRegularExpression
    public init(_ pattern: String, ignoreCase: Bool = false) {
        re = try! NSRegularExpression(pattern: pattern, options: ignoreCase ? [.caseInsensitive] : [])
    }

    public func search(_ s: String) -> Bool {
        re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }

    /// `re.sub(pattern, repl, s)` (repl littéral, sans références) ; `count` 0 = tout remplacer.
    public func sub(_ repl: String, _ s: String, count: Int = 0) -> String {
        let ns = s as NSString
        var out = ""
        var last = 0
        var n = 0
        for m in re.matches(in: s, range: NSRange(location: 0, length: ns.length)) {
            if count > 0, n >= count { break }
            out += ns.substring(with: NSRange(location: last, length: m.range.location - last))
            out += repl
            last = m.range.location + m.range.length
            n += 1
        }
        return out + ns.substring(from: last)
    }

    /// Premier groupe de capture de la première correspondance.
    public func firstGroup(_ s: String) -> String? {
        guard let m = re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)), m.numberOfRanges > 1,
              let r = Range(m.range(at: 1), in: s) else { return nil }
        return String(s[r])
    }
}
