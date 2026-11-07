// Point d'entrée : fenêtre AppKit unique (1340 × 840, redimensionnable) qui héberge l'interface SwiftUI, splash animé,
// menus (Fichier, Édition, Langue, Fenêtre), À propos et mise à jour automatique.

import AppKit
import FomodCore
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    let model = AppModel()
    let env = ProcessInfo.processInfo.environment

    // Le splash part avant que SwiftUI ouvre la fenêtre principale, pour pouvoir la retenir jusqu'à t = 2 s.
    func applicationWillFinishLaunching(_ notification: Notification) {
        Socle.brand(APP_NAME, "fOMOD_SIM", color: LOGO_BLUE)  // « f » dans le bleu du logo
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
        Splash.shared.start(Splash.Config(title: APP_NAME, subtitle: T("splash.subtitle"),
                                          footer: version.isEmpty ? T("splash.footer") : T("splash.footer") + " · v" + version, accent: LOGO_BLUE))
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        Socle.apply()
        buildMenu()

        let host = NSHostingView(rootView: ContentView(model: model).splashGated())
        window = NSWindow(contentRect: NSRect(origin: .zero, size: WINDOW_SIZE),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = APP_NAME
        window.contentView = host
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.backgroundColor = NSColor(Socle.C.bg)
        window.contentMinSize = NSSize(width: 1000, height: 680)
        let avail = NSScreen.main?.visibleFrame.height ?? 1080
        window.setContentSize(NSSize(width: WINDOW_SIZE.width, height: min(WINDOW_SIZE.height, max(680, avail - 60))))
        window.socleCenter()
        model.window = window

        // Un chemin passé au lancement (les options macOS -psn_…, -AppleLanguages sont ignorées)
        if let path = launchArgumentPath(Array(CommandLine.arguments.dropFirst())) {
            if FileManager.default.fileExists(atPath: path) { model.loadArchive(path) }
        }

        // Essais discrets : FOMODSIM_NOUPDATE=1 saute la recherche de mise à jour
        if env["FOMODSIM_NOUPDATE"] == nil {
            UpdateEngine.shared.configure(repo: "fOMOD_SIM", lang: { I18n.lang })
            UpdateEngine.shared.canInstall = { [weak self] in !(self?.model.busy ?? false) }  // jamais pendant une extraction ou un export
            UpdateEngine.shared.start()  // nouvelle version ? (au plus une fois par jour)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { UpdateEngine.shared.installAppMenuItem() }
        }
        scripted()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        // Écriture du staging en cours : on la laisse finir pour ne pas laisser de fichiers tronqués
        model.exporting ? .terminateCancel : .terminateNow
    }

    // MARK: Menus

    @objc func chooseLanguage(_ sender: NSMenuItem) {
        model.setLanguage(sender.representedObject as? String ?? "auto")
        buildMenu()
        UpdateEngine.shared.installAppMenuItem()
    }
    @objc func showAbout(_ sender: Any?) { About.show() }
    @objc func openFomod(_ sender: Any?) { model.showOpenMod = true }
    /// Quitter : les feuilles ouvertes sont fermées d'abord, sinon macOS ne termine pas l'appli.
    @objc func quit(_ sender: Any?) {
        model.dismissSheets()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { NSApp.terminate(nil) }
    }

    private func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        // Pas de couleur dans les menus : le nom de l'appli y est en texte normal
        appMenu.addItem(withTitle: T("about.menu"), action: #selector(showAbout), keyEquivalent: "").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: T("menu.hide"), action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let others = appMenu.addItem(withTitle: T("menu.hideOthers"), action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        others.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: T("menu.showAll"), action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: T("menu.quit"), action: #selector(quit), keyEquivalent: "q").target = self
        appItem.submenu = appMenu
        main.addItem(appItem)

        let fileItem = NSMenuItem()
        let fileMenu = NSMenu(title: T("menu.file"))
        fileMenu.addItem(withTitle: T("menu.openFomod"), action: #selector(openFomod), keyEquivalent: "o").target = self
        fileItem.submenu = fileMenu
        main.addItem(fileItem)

        let editItem = NSMenuItem()
        let editMenu = NSMenu(title: T("menu.edit"))
        editMenu.addItem(withTitle: T("menu.cut"), action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: T("menu.copy"), action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: T("menu.paste"), action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: T("menu.selectAll"), action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = editMenu
        main.addItem(editItem)

        // Menu « Langue » : Automatique + 4 langues, coche sur le choix courant
        let langItem = NSMenuItem()
        let langMenu = NSMenu(title: T("menu.language"))
        let current = model.languageChoice
        func add(_ title: String, _ code: String) {
            let item = langMenu.addItem(withTitle: title, action: #selector(chooseLanguage), keyEquivalent: "")
            item.target = self
            item.representedObject = code
            item.state = code == current ? .on : .off
        }
        add(T("menu.auto"), LangChoice.auto)
        langMenu.addItem(.separator())
        for (code, label) in LangChoice.menuLangs { add(label, code) }
        langItem.submenu = langMenu
        main.addItem(langItem)

        let winItem = NSMenuItem()
        let winMenu = NSMenu(title: T("menu.window"))
        winMenu.addItem(withTitle: T("menu.minimize"), action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        winItem.submenu = winMenu
        main.addItem(winItem)
        NSApp.mainMenu = main
        NSApp.windowsMenu = winMenu
    }

    // MARK: Essais pilotés par l'environnement (aucune interaction, aucune fenêtre au premier plan)

    /// FOMODSIM_RUN : étapes séparées par « ; » parmi demo, open:<chemin>, next, prev, pick:<étape>.<groupe>.<option> (clic),
    /// data:<dossier Data> (scan), stage:<dossier> (écrit le staging), info, dataSheet, openSheet, lang:<code>.
    /// FOMODSIM_SNAPSHOT=<png> (après FOMODSIM_DELAY s, 3,5 par défaut) enregistre la fenêtre ; FOMODSIM_DUMP=<fichier> écrit l'état ; puis l'appli quitte.
    private func scripted() {
        if let run = env["FOMODSIM_RUN"] {
            for (i, step) in run.components(separatedBy: ";").enumerated() {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5 + Double(i) * 1.2) { [self] in
                    if step == "demo" { model.loadDemo() }
                    else if step == "next" { model.nextStep() }
                    else if step == "prev" { model.prevStep() }
                    else if step == "info" { model.showModInfo = true }
                    else if step == "dataSheet" { model.showDataDir = true }
                    else if step == "openSheet" { model.showOpenMod = true }
                    else if step == "about" { About.show() }
                    else if step == "preview" { model.openImagePreview() }
                    else if step.hasPrefix("open:") { model.loadArchive(String(step.dropFirst(5))) }
                    else if step.hasPrefix("lang:") { model.setLanguage(String(step.dropFirst(5))); buildMenu() }
                    else if step.hasPrefix("data:") {
                        let dir = String(step.dropFirst(5))
                        model.applyDataDir(path: dir, plugins: scanDataDir(dir))
                    }
                    else if step.hasPrefix("stage:") { model.scriptedStage(String(step.dropFirst(6))) }
                    else if step.hasPrefix("pick:") {
                        let p = step.dropFirst(5).split(separator: ".").compactMap { Int($0) }
                        if p.count == 3, model.steps.indices.contains(p[0]), model.steps[p[0]].groups.indices.contains(p[1]),
                           model.steps[p[0]].groups[p[1]].options.indices.contains(p[2]) {
                            model.currentStepIdx = p[0]
                            let g = model.steps[p[0]].groups[p[1]]
                            model.select(g.options[p[2]], in: g)
                        }
                    }
                }
            }
        }
        // Splash (essais) : FOMODSIM_SPLASH_SHOTS=<préfixe> enregistre le panneau du splash à 0,4 / 1 / 1,6 / 2,4 s
        if let prefix = env["FOMODSIM_SPLASH_SHOTS"] {
            for (i, at) in [0.4, 1.0, 1.6, 2.4].enumerated() {
                DispatchQueue.main.asyncAfter(deadline: .now() + at) {
                    guard let v = NSApp.windows.first(where: { $0 is NSPanel && $0.frame.width == 500 })?.contentView else { return }
                    v.layoutSubtreeIfNeeded()
                    if let rep = v.bitmapImageRepForCachingDisplay(in: v.bounds) {
                        v.cacheDisplay(in: v.bounds, to: rep)
                        try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: "\(prefix)-\(i).png"))
                    }
                }
            }
        }
        guard let out = env["FOMODSIM_SNAPSHOT"] else { return }
        let delay = Double(env["FOMODSIM_DELAY"] ?? "") ?? 3.5
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [self] in
            if let dump = env["FOMODSIM_DUMP"] {
                var t = "menus:\n"
                for item in NSApp.mainMenu?.items ?? [] {
                    t += " [\(item.submenu?.title ?? "")] " + (item.submenu?.items.map { ($0.state == .on ? "✓" : "") + ($0.isSeparatorItem ? "-" : $0.title) }.joined(separator: " | ") ?? "") + "\n"
                }
                t += "langue: \(I18n.lang) (choix \(model.languageChoice))\nsimulateur: \(model.inSimulator)\nmod: \(model.metadata.name)\n"
                t += "étape: \(model.currentStepIdx) visibles \(model.visibleSteps) flags \(model.activeFlags)\n"
                t += "sélection: \(model.selectedIDs.sorted())\ndata: \(model.installedBasenames.count) fichiers\n"
                t += "aperçu: \(model.activePreviewOption?.name ?? "-") image \(model.previewImage.map { "\(Int($0.size.width))x\(Int($0.size.height))" } ?? "-")\n"
                t += "alerte: \(model.alert.map { $0.title + " / " + $0.message } ?? "-")\n" + model.scriptLog
                try? t.write(toFile: dump, atomically: true, encoding: .utf8)
            }
            func shot(_ view: NSView, _ file: String) {
                view.layoutSubtreeIfNeeded()
                if let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                    view.cacheDisplay(in: view.bounds, to: rep)
                    try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: file))
                }
            }
            shot(window.contentView!, out)
            var n = 0
            for w in NSApp.windows where w !== window && w.contentView != nil && w.frame.width > 100 && !(w is NSPanel) {
                n += 1
                shot(w.contentView!, out.replacingOccurrences(of: ".png", with: "-\(n).png"))
            }
            quit(nil)
        }
    }
}

I18n.setLang(LangChoice.resolve(AppSettings(suite: ProcessInfo.processInfo.environment["FOMODSIM_SUITE"]).string("language", LangChoice.auto)))

MainActor.assumeIsolated {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.delegate = delegate
    app.setActivationPolicy(.regular)
    app.run()
}
