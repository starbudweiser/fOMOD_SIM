// Le colis de l'icône fOMODSIM, dessiné en vectoriel pour le splash (reprise de l'animation de la version Python,
// `_paint_logo` de splash.py) : carré bleu, faces du colis qui tombent une à une et s'emboîtent, pastille verte avec
// rebond puis coche tracée. L'arrivée en tourbillon du carré est faite par SplashScreen. « Réduire les animations » :
// icône fixe.
import AppKit
import SwiftUI

struct AnimatedBoxIcon: View {
    @State private var start = Date()
    private let reduce = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion

    var body: some View {
        TimelineView(.animation(paused: reduce)) { ctx in
            let t = reduce ? 1e7 : ctx.date.timeIntervalSince(start) * 1000
            Canvas { g, size in Self.draw(&g, size, t) }
        }
    }

    // courbes cubic-bezier comme les animations CSS
    private static func bezier(_ x1: Double, _ y1: Double, _ x2: Double, _ y2: Double) -> (Double) -> Double {
        func c(_ t: Double, _ a: Double, _ b: Double) -> Double { 3 * a * t * (1 - t) * (1 - t) + 3 * b * t * t * (1 - t) + t * t * t }
        return { x in
            if x <= 0 { return 0 }; if x >= 1 { return 1 }
            var lo = 0.0, hi = 1.0
            for _ in 0..<30 { let m = (lo + hi) / 2; if c(m, x1, x2) < x { lo = m } else { hi = m } }
            return c((lo + hi) / 2, y1, y2)
        }
    }
    private static let easeDrop = bezier(0.34, 1.3, 0.5, 1)
    private static let easeOut = bezier(0, 0, 0.58, 1)
    private static func progress(_ t: Double, _ delay: Double, _ dur: Double, _ ease: (Double) -> Double) -> Double {
        t <= delay ? 0 : t >= delay + dur ? 1 : ease((t - delay) / dur)
    }

    private static func color(_ hex: UInt32) -> Color {
        Color(red: Double(hex >> 16 & 0xff) / 255, green: Double(hex >> 8 & 0xff) / 255, blue: Double(hex & 0xff) / 255)
    }
    private static let blue = color(0x1677dc), ring = color(0x0f5fc4), badge = color(0x4ade80)

    /// Pièces du colis de icon.svg (canevas de 1024, carré utile de 824 centré), dans l'ordre d'arrivée :
    /// faces gauche, droite, dessus, puis ruban.
    private static let pieces: [(UInt32, [CGPoint])] = [
        (0xe4effc, [CGPoint(x: 272, y: 400), CGPoint(x: 512, y: 538), CGPoint(x: 512, y: 800), CGPoint(x: 272, y: 662)]),
        (0xb6d3f5, [CGPoint(x: 512, y: 538), CGPoint(x: 752, y: 400), CGPoint(x: 752, y: 662), CGPoint(x: 512, y: 800)]),
        (0xffffff, [CGPoint(x: 512, y: 262), CGPoint(x: 752, y: 400), CGPoint(x: 512, y: 538), CGPoint(x: 272, y: 400)]),
        (0x7cc2ff, [CGPoint(x: 372, y: 342), CGPoint(x: 412, y: 319), CGPoint(x: 652, y: 457), CGPoint(x: 612, y: 480)]),
        (0x5aa6ec, [CGPoint(x: 612, y: 480), CGPoint(x: 652, y: 457), CGPoint(x: 652, y: 719), CGPoint(x: 612, y: 742)]),
    ]

    private static func draw(_ g: inout GraphicsContext, _ size: CGSize, _ t: Double) {
        let s = size.width, unit = s / 824
        g.fill(Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 24 * s / 108, style: .continuous),
               with: .color(blue))
        g.translateBy(x: s / 2, y: s / 2)

        for (i, (hex, pts)) in pieces.enumerated() {
            let delay = 150 + Double(i) * 90
            let fade = progress(t, delay, 450, easeOut)
            guard fade > 0 else { continue }
            let d = progress(t, delay, 900, easeDrop)
            var p = Path()
            p.addLines(pts.map { CGPoint(x: ($0.x - 512) * unit, y: ($0.y - 512) * unit - 70 * (1 - d)) })
            p.closeSubpath()
            var c = g
            c.opacity = fade
            c.fill(p, with: .color(color(hex)))
        }

        let k = progress(t, 700, 600, easeDrop)
        guard k > 0 else { return }
        var b = g
        b.translateBy(x: (724 - 512) * unit, y: (724 - 512) * unit)
        b.scaleBy(x: k, y: k)
        b.fill(Path(ellipseIn: CGRect(x: -132 * unit, y: -132 * unit, width: 264 * unit, height: 264 * unit)), with: .color(ring))
        b.fill(Path(ellipseIn: CGRect(x: -108 * unit, y: -108 * unit, width: 216 * unit, height: 216 * unit)), with: .color(badge))
        let c = progress(t, 1000, 450, easeOut)
        guard c > 0 else { return }
        var check = Path()
        check.addLines([CGPoint(x: -52 * unit, y: 2 * unit), CGPoint(x: -16 * unit, y: 38 * unit), CGPoint(x: 54 * unit, y: -34 * unit)])
        b.stroke(check.trimmedPath(from: 0, to: c), with: .color(.white),
                 style: StrokeStyle(lineWidth: 30 * unit, lineCap: .round, lineJoin: .round))
    }
}
