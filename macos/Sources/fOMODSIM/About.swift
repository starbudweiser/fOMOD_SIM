// Fenêtre « À propos de fOMODSIM » : modèle Socle (DESIGN/Socle/swift/AboutWindow.swift), textes dans les 4 langues.

import AppKit
import FomodCore

@MainActor
enum About {
    private static var window: NSWindow?

    private static let sideMargin: CGFloat = 28
    private static let textWidth: CGFloat = 300

    static func show() {
        window?.close()  // reconstruite à chaque ouverture : suit la langue choisie dans le menu Langue
        window = makeWindow()
        window?.updaterCenter()
        if ProcessInfo.processInfo.environment["SPLASH_QUIET"] != nil { window?.orderBack(nil) } else { window?.present() }  // essais discrets
    }

    private static func label(_ text: String, size: CGFloat = 12, bold: Bool = false, secondary: Bool = false) -> NSTextField {
        let field = NSTextField(wrappingLabelWithString: text)
        field.font = bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size)
        field.textColor = secondary ? .secondaryLabelColor : .labelColor
        field.alignment = .center
        field.preferredMaxLayoutWidth = textWidth
        field.isSelectable = false
        field.translatesAutoresizingMaskIntoConstraints = false
        field.widthAnchor.constraint(lessThanOrEqualToConstant: textWidth).isActive = true
        return field
    }

    /// Nom de l'appli : le « m » prend la couleur du logo (règle Socle « Nom de l'appli »).
    private static func nameLabel() -> NSTextField {
        let field = label(APP_NAME, size: 17, bold: true)
        let text = NSMutableAttributedString(string: APP_NAME, attributes: [
            .font: NSFont.boldSystemFont(ofSize: 17), .foregroundColor: NSColor.labelColor])
        text.addAttribute(.foregroundColor, value: NSColor(srgbRed: 0x16 / 255, green: 0x77 / 255, blue: 0xdc / 255, alpha: 1),
                          range: NSRange(location: 0, length: 1))
        let para = NSMutableParagraphStyle()
        para.alignment = .center
        text.addAttribute(.paragraphStyle, value: para, range: NSRange(location: 0, length: text.length))
        field.attributedStringValue = text
        return field
    }

    private static func makeWindow() -> NSWindow {
        let info = Bundle.main.infoDictionary ?? [:]
        let version = info["CFBundleShortVersionString"] as? String ?? "?"
        let build = info["CFBundleVersion"] as? String ?? "?"

        let icon = NSImageView(image: NSApp.applicationIconImage)
        icon.imageScaling = .scaleProportionallyUpOrDown
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.widthAnchor.constraint(equalToConstant: 84).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 84).isActive = true

        let views: [NSView] = [
            icon,
            nameLabel(),
            label(T("about.version", ["v": version, "b": build]), secondary: true),
            label(T("about.tagline")),
            label("Starbudweiser & Claude Code (Anthropic)", bold: true),
            label(T("about.license")),
            label(T("about.disclaimer"), secondary: true),
            label(T("about.credit"), secondary: true),
        ]
        let stack = NSStackView(views: views)
        stack.orientation = .vertical
        stack.alignment = .centerX
        stack.spacing = 12
        stack.setCustomSpacing(6, after: views[1])
        stack.setCustomSpacing(18, after: views[2])
        stack.edgeInsets = NSEdgeInsets(top: 28, left: sideMargin, bottom: 28, right: sideMargin)
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.widthAnchor.constraint(equalToConstant: textWidth + 2 * sideMargin).isActive = true

        let window = NSWindow(contentRect: .zero, styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = T("about.menu")
        window.isReleasedWhenClosed = false
        let content = NSView()
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: content.topAnchor),
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor),
        ])
        window.contentView = content
        content.layoutSubtreeIfNeeded()
        content.layoutSubtreeIfNeeded()
        window.setContentSize(content.fittingSize)
        return window
    }
}
