// Arbre XML minimal qui se comporte comme xml.etree.ElementTree : ordre du document, `text` = texte avant le
// premier enfant (nil s'il n'y en a pas), commentaires et instructions ignorés. Les attributs viennent d'un
// dictionnaire (Foundation ne donne pas leur ordre) : triés par nom, ce qui ne compte que si deux attributs d'un
// même élément ne diffèrent que par la casse.

import Foundation

public final class XNode {
    public var tag: String
    public var attrib: [(key: String, value: String)]
    public var text: String?
    public var children: [XNode] = []

    init(tag: String, attrib: [(key: String, value: String)]) { self.tag = tag; self.attrib = attrib }

    /// `el.attrib.get(name)` : nom exact.
    public func attr(_ name: String) -> String? { attrib.first { $0.key == name }?.value }

    /// `el.iter()` : l'élément puis tous ses descendants, dans l'ordre du document.
    public func iter() -> [XNode] {
        var out: [XNode] = []
        func walk(_ n: XNode) { out.append(n); for c in n.children { walk(c) } }
        walk(self)
        return out
    }
}

struct XMLSyntaxError: Error, CustomStringConvertible {
    let message: String
    var description: String { message }
}

// Foundation supprime certains U+FEFF (espace insécable de largeur nulle) au milieu des textes, Python les garde :
// on les remplace par un caractère d'usage privé avant l'analyse, puis on les rétablit dans les textes et attributs.
private let bomStandIn = "\u{10FFFD}"
private func restoreBOM(_ s: String) -> String { s.contains(bomStandIn) ? s.replacingOccurrences(of: bomStandIn, with: "\u{FEFF}") : s }

private final class TreeBuilder: NSObject, XMLParserDelegate {
    var root: XNode?
    var stack: [XNode] = []
    var sawChild: [Bool] = []
    var error: String?

    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String: String] = [:]) {
        let node = XNode(tag: elementName, attrib: attributeDict.sorted { $0.key < $1.key }.map { ($0.key, restoreBOM($0.value)) })
        if let parent = stack.last {
            parent.children.append(node)
            sawChild[sawChild.count - 1] = true
        } else if root == nil {
            root = node
        }
        stack.append(node)
        sawChild.append(false)
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
        _ = stack.popLast()
        _ = sawChild.popLast()
    }

    private func append(_ s: String) {
        guard let cur = stack.last, sawChild.last == false else { return }
        cur.text = (cur.text ?? "") + restoreBOM(s)
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) { append(string) }
    func parser(_ parser: XMLParser, foundCDATA CDATABlock: Data) { append(String(decoding: CDATABlock, as: UTF8.self)) }

    func parser(_ parser: XMLParser, parseErrorOccurred parseError: Error) {
        if error == nil { error = (parseError as NSError).localizedDescription }
    }
}

/// Analyse un texte XML (sans déclaration d'encodage) ; lève `XMLSyntaxError` si le document n'est pas bien formé.
func parseXMLTree(_ text: String) throws -> XNode {
    let builder = TreeBuilder()
    let parser = XMLParser(data: Data(text.replacingOccurrences(of: "\u{FEFF}", with: bomStandIn).utf8))
    parser.shouldProcessNamespaces = true
    parser.shouldReportNamespacePrefixes = false
    parser.shouldResolveExternalEntities = false
    parser.delegate = builder
    let ok = parser.parse()
    if !ok || builder.error != nil || builder.root == nil {
        throw XMLSyntaxError(message: builder.error ?? parser.parserError?.localizedDescription ?? "document vide")
    }
    return builder.root!
}
