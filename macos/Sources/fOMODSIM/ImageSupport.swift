// Images d'aperçu : lecture robuste (PNG, JPEG, BMP, WebP, GIF, mais aussi DDS et TGA par ImageIO) et visuel généré
// pour les options sans image (traduction de python_app/gui/preview_generator.py).

import AppKit
import FomodCore
import ImageIO

/// Charge une image depuis un fichier ou des octets ; `maxSize` réduit les grandes images (vignette de 1280 px).
func loadImage(path: String?, data: Data?, maxSize: Int? = nil) -> NSImage? {
    var source: CGImageSource?
    if let p = path, FileManager.default.fileExists(atPath: p) {
        source = CGImageSourceCreateWithURL(URL(fileURLWithPath: p) as CFURL, nil)
    } else if let d = data, !d.isEmpty {
        source = CGImageSourceCreateWithData(d as CFData, nil)
    }
    guard let src = source, CGImageSourceGetCount(src) > 0 else { return nil }
    let cg: CGImage?
    if let m = maxSize {
        let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true,
                                     kCGImageSourceThumbnailMaxPixelSize: m]
        cg = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary)
    } else {
        cg = CGImageSourceCreateImageAtIndex(src, 0, nil)
    }
    guard let image = cg else { return nil }
    return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
}

/// Visuel vectoriel pour une option sans image : emblème, titre, première phrase de la description.
@MainActor
func generatedPreview(option: FomodOption, index: ArchiveIndex?) -> NSImage {
    var sub = option.description.isEmpty ? T("preview.defaultSubtitle") : (option.description.components(separatedBy: ".")[0] + ".")
    if sub.count > 65 { sub = String(sub.prefix(62)) + "..." }
    return drawPreview(title: option.name, subtitle: sub)
}

@MainActor
func drawPreview(title: String, subtitle: String, bg: NSColor = NSColor(srgbRed: 0x1e / 255, green: 0x29 / 255, blue: 0x3b / 255, alpha: 1),
                 accent: NSColor = NSColor(srgbRed: 0x38 / 255, green: 0xbd / 255, blue: 0xf8 / 255, alpha: 1),
                 width: CGFloat = 640, height: CGFloat = 400) -> NSImage {
    NSImage(size: NSSize(width: width, height: height), flipped: true) { rect in
        NSGradient(starting: bg, ending: NSColor(srgbRed: 0x11 / 255, green: 0x11 / 255, blue: 0x11 / 255, alpha: 1))?.draw(in: rect, angle: -atan2(height, width) * 180 / .pi)
        let cx = width / 2, cy: CGFloat = 130
        accent.setStroke()
        let circle = NSBezierPath(ovalIn: NSRect(x: cx - 55, y: cy - 55, width: 110, height: 110))
        circle.lineWidth = 2.5
        circle.stroke()
        let diamond = NSBezierPath()
        diamond.move(to: NSPoint(x: cx - 32, y: cy))
        diamond.line(to: NSPoint(x: cx, y: cy - 32))
        diamond.line(to: NSPoint(x: cx + 32, y: cy))
        diamond.line(to: NSPoint(x: cx, y: cy + 32))
        diamond.close()
        accent.withAlphaComponent(200 / 255).setFill()
        diamond.fill()
        let para = NSMutableParagraphStyle()
        para.alignment = .center
        para.lineBreakMode = .byTruncatingTail
        NSAttributedString(string: title, attributes: [.font: NSFont.boldSystemFont(ofSize: 16), .foregroundColor: NSColor.white, .paragraphStyle: para])
            .draw(in: NSRect(x: 20, y: 210, width: width - 40, height: 32))
        NSAttributedString(string: subtitle, attributes: [.font: NSFont.systemFont(ofSize: 12),
                                                          .foregroundColor: NSColor(srgbRed: 0xa1 / 255, green: 0xa1 / 255, blue: 0xaa / 255, alpha: 1),
                                                          .paragraphStyle: para])
            .draw(in: NSRect(x: 20, y: 246, width: width - 40, height: 28))
        return true
    }
}
