// Fenêtres de dialogue : ouverture d'un mod, dossier Data, infos du mod, résultat du staging, aperçu en taille réelle
// (traduction de python_app/gui/modals.py et mod_info_dialog.py).

import AppKit
import FomodCore
import SwiftUI

/// Cadre commun : titre, bouton de fermeture, filet.
struct SheetFrame<Content: View>: View {
    let title: String
    var titleColor: Color = Socle.C.textStrong
    let close: () -> Void
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title).socle(Socle.T.heading).foregroundStyle(titleColor).lineLimit(2)
                Spacer()
                Button("✕", action: close).buttonStyle(SocleButtonStyle(.secondary, height: 26)).frame(width: 26)
            }
            Divider().overlay(Socle.C.borderSubtle)
            content
        }
        .padding(.horizontal, 22).padding(.vertical, 18)
        .background(Socle.C.surface)
    }
}

// MARK: - Ouvrir un FOMOD

struct OpenModSheet: View {
    @Bindable var model: AppModel

    var body: some View {
        SheetFrame(title: "📦  " + T("modals.openMod.title"), close: { model.showOpenMod = false }) {
            Text(T("modals.openMod.fromComputer").uppercased()).socle(Socle.T.eyebrow).foregroundStyle(Socle.C.textMuted)
            choice(T("ui.browseArchive"), badge: T("ui.fullSupport"), desc: T("ui.archiveDesc")) {
                model.showOpenMod = false
                DispatchQueue.main.async { model.pickArchive() }
            }
            choice(T("ui.browseFolder"), badge: T("ui.localFolder"), desc: T("ui.folderDesc")) {
                model.showOpenMod = false
                DispatchQueue.main.async { model.pickModFolder() }
            }
            Text(T("ui.demoMods")).socle(Socle.T.eyebrow).foregroundStyle(Socle.C.textMuted).padding(.top, 4)
            demo("CBBE - Caliente's Beautiful Bodies Enhancer SE")
            demo("SMIM - Static Mesh Improvement Mod")
            Spacer(minLength: 0)
        }
        .frame(width: 560, height: 520)
    }

    private func choice(_ title: String, badge: String, desc: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(title).socle(Socle.T.label).foregroundStyle(Socle.C.textStrong)
                    Spacer()
                    Text(badge).socle(Socle.T.caption).foregroundStyle(Socle.C.accentText)
                }
                Text(desc).socle(Socle.T.meta).foregroundStyle(Socle.C.textMuted).multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
            }
            .padding(.horizontal, 14).padding(.vertical, 12).frame(maxWidth: .infinity, alignment: .leading)
            .background(Socle.C.control, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            .contentShape(Rectangle())
        }.buttonStyle(.plain)
    }

    private func demo(_ name: String) -> some View {
        Button {
            model.showOpenMod = false
            DispatchQueue.main.async { model.loadDemo() }
        } label: {
            HStack {
                Text(name).socle(Socle.T.label).foregroundStyle(Socle.C.textStrong)
                Spacer()
                Text(T("ui.load")).socle(Socle.T.caption).foregroundStyle(Socle.C.accentText)
            }
            .padding(.horizontal, 14).padding(.vertical, 10).frame(maxWidth: .infinity)
            .background(Socle.C.control, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            .contentShape(Rectangle())
        }.buttonStyle(.plain)
    }
}

// MARK: - Dossier Data

struct DataDirSheet: View {
    @Bindable var model: AppModel
    @State private var path = ""
    @State private var plugins: Set<String> = []
    @State private var scanning = false

    private var shown: [String] { plugins.filter { $0.hasAnySuffix([".esp", ".esm", ".esl", ".dll", ".bsa", ".ba2"]) }.sorted() }

    var body: some View {
        SheetFrame(title: T("ui.dataHeading"), close: { model.showDataDir = false }) {
            Text(T("ui.dataDesc")).socle(Socle.T.body).foregroundStyle(Socle.C.textMuted).fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 4) {
                Text(T("ui.linkedFolder")).socle(Socle.T.caption).foregroundStyle(Socle.C.textSubtle)
                Text(path.isEmpty ? T("ui.noFolder") : path).socle(Socle.T.monoSm).foregroundStyle(Socle.C.accentText).lineLimit(2).truncationMode(.middle)
            }
            .padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radius))
            HStack(spacing: 8) {
                Button(T("ui.browseDisk")) { browse() }.buttonStyle(SocleButtonStyle(.secondary, height: 32)).fixedSize()
                Button(T("ui.simulatePlugins")) { simulate() }.buttonStyle(SocleButtonStyle(.secondary, height: 32)).fixedSize()
            }
            Text(T("ui.detected", ["n": shown.count])).socle(Socle.T.label).foregroundStyle(Socle.C.textMuted)
            ScrollView {
                Text(scanning ? T("common.loading") : (shown.isEmpty ? T("ui.noPlugin") : shown.joined(separator: "\n")))
                    .socle(Socle.T.monoSm).foregroundStyle(Socle.C.text)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(10).textSelection(.enabled)
            }
            .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radius))
            HStack {
                Spacer()
                Button(T("ui.validateClose")) {
                    model.applyDataDir(path: path, plugins: plugins)
                    model.showDataDir = false
                }.buttonStyle(SocleButtonStyle(.primary, height: 34)).fixedSize()
            }
        }
        .frame(width: 580, height: 460)
        .onAppear {
            path = model.dataDirPath ?? ""
            plugins = model.installedBasenames
        }
    }

    private func browse() {
        let p = NSOpenPanel()
        p.title = T("ui.pickDataFolder")
        p.canChooseFiles = false
        p.canChooseDirectories = true
        p.allowsMultipleSelection = false
        guard p.runModal() == .OK, let url = p.url else { return }
        path = url.path
        scanning = true
        let folder = url.path
        Task.detached(priority: .userInitiated) {
            let found = scanDataDir(folder)  // lecture seule
            await MainActor.run { plugins = found; scanning = false }
        }
    }

    private func simulate() {
        path = "C:/Program Files/Steam/steamapps/common/Skyrim Special Edition/Data"
        plugins = [
            "skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm", "dragonborn.esm",
            "skyui_se.esp", "cbpc.dll", "skee64.dll", "hdtsmp64.dll", "lanterns of skyrim ii.esm",
            "jks skyrim.esp", "elfx - exteriors.esp", "windhelm_braziers.esp", "gourmettables.esp",
        ]
    }
}

// MARK: - Infos du mod

struct ModInfoSheet: View {
    let metadata: FomodMetadata
    let close: () -> Void

    var body: some View {
        SheetFrame(title: metadata.name, titleColor: Socle.C.action, close: close) {
            HStack(spacing: 16) {
                (Text(T("modals.modInfo.author") + " : ").bold() + Text(metadata.author.isEmpty ? "—" : metadata.author)).foregroundStyle(Socle.C.textMuted)
                (Text(T("modals.modInfo.version") + " : ").bold() + Text(metadata.version.isEmpty ? "1.0" : metadata.version)).foregroundStyle(Socle.C.accentText)
                Spacer()
            }.socle(Socle.T.body)
            if !metadata.website.isEmpty {
                HStack(spacing: 4) {
                    Text(T("modals.modInfo.website") + " :").bold().foregroundStyle(Socle.C.textMuted)
                    if let url = URL(string: metadata.website) { Link(metadata.website, destination: url).foregroundStyle(Socle.C.accentText) }
                    else { Text(metadata.website).foregroundStyle(Socle.C.accentText) }
                }.socle(Socle.T.body)
            }
            Divider().overlay(Socle.C.borderSubtle)
            Text(T("modals.modInfo.description") + " :").socle(Socle.T.labelStrong).foregroundStyle(Socle.C.text)
            ScrollView {
                Text(metadata.description).socle(Socle.T.bodyLg).lineSpacing(4).foregroundStyle(Socle.C.text)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(10).textSelection(.enabled)
            }
            .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            HStack {
                Spacer()
                Button(T("common.close"), action: close).buttonStyle(SocleButtonStyle(.secondary, height: 34)).fixedSize()
            }
        }
        .frame(width: 600, height: 460)
    }
}

// MARK: - Résultat du staging

private struct TreeRow: Identifiable {
    let id: Int
    let depth: Int
    let name: String
    let size: String
    let source: String
    let isFolder: Bool
}

/// Arborescence du staging : les dossiers apparaissent à leur première occurrence, tous dépliés (comme le QTreeWidget).
private func buildRows(_ items: [StagingItem]) -> [TreeRow] {
    final class Node { var name = ""; var size = ""; var source = ""; var folder = false; var children: [Node] = [] }
    let root = Node()
    var dirNodes: [String: Node] = [:]
    for item in items {
        let parts = item.destinationPath.pySplit("/")
        var parent = root
        var cur = ""
        for i in 0..<max(parts.count - 1, 0) {
            cur = cur.isEmpty ? parts[i] : "\(cur)/\(parts[i])"
            if dirNodes[cur] == nil {
                let n = Node()
                n.name = parts[i]; n.size = T("ui.folder"); n.folder = true
                parent.children.append(n)
                dirNodes[cur] = n
            }
            parent = dirNodes[cur]!
        }
        let leaf = Node()
        leaf.name = parts.last ?? ""; leaf.size = formatBytes(item.size); leaf.source = item.matchedFromOption
        parent.children.append(leaf)
    }
    var rows: [TreeRow] = []
    func walk(_ n: Node, _ depth: Int) {
        for c in n.children {
            rows.append(TreeRow(id: rows.count, depth: depth, name: c.name, size: c.size, source: c.source, isFolder: c.folder))
            walk(c, depth + 1)
        }
    }
    walk(root, 0)
    return rows
}

struct StagingResultSheet: View {
    @Bindable var model: AppModel
    let done: StagingDone
    @State private var tab = 0
    @State private var rows: [TreeRow] = []

    var body: some View {
        SheetFrame(title: "✓  " + T("ui.stagingDoneBang"), titleColor: Socle.C.success, close: { model.stagingDone = nil }) {
            richText(T("ui.stagingSummary", ["count": done.result.copiedCount, "size": formatBytes(done.result.totalSize), "dest": done.target]))
                .socle(Socle.T.body).foregroundStyle(Socle.C.textMuted).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            SocleSegmented(options: [0, 1], selection: tab, label: { $0 == 0 ? T("ui.filesTab") : T("ui.logTab") }, tone: { _ in .strong }) { tab = $0 }
            if tab == 0 {
                VStack(spacing: 0) {
                    HStack {
                        Text(T("ui.colDest")).frame(maxWidth: .infinity, alignment: .leading)
                        Text(T("ui.colSize")).frame(width: 90, alignment: .trailing)
                        Text(T("ui.colSource")).frame(width: 220, alignment: .leading).padding(.leading, 12)
                    }
                    .socle(Socle.T.caption).foregroundStyle(Socle.C.textMuted).padding(.horizontal, 10).padding(.vertical, 6)
                    Divider().overlay(Socle.C.borderSubtle)
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(rows) { r in
                                HStack {
                                    Text(r.name).foregroundStyle(r.isFolder ? Socle.C.accentText : Socle.C.text)
                                        .padding(.leading, CGFloat(r.depth) * 16).lineLimit(1).truncationMode(.middle)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text(r.size).foregroundStyle(Socle.C.textMuted).frame(width: 90, alignment: .trailing)
                                    Text(r.source).foregroundStyle(Socle.C.textMuted).lineLimit(1).frame(width: 220, alignment: .leading).padding(.leading, 12)
                                }
                                .socle(Socle.T.meta).padding(.horizontal, 10).padding(.vertical, 3)
                            }
                        }
                    }
                }
                .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            } else {
                ScrollView {
                    Text(done.result.log.isEmpty ? T("ui.cleanInstall") : done.result.log.joined(separator: "\n"))
                        .socle(Socle.T.monoSm).foregroundStyle(Socle.C.text).frame(maxWidth: .infinity, alignment: .leading).padding(10).textSelection(.enabled)
                }
                .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            }
            HStack {
                Button(T("ui.exportZip")) { model.exportZip(done) }.buttonStyle(SocleButtonStyle(.secondary, height: 34)).fixedSize().disabled(model.busy)
                Spacer()
                Button(T("common.close")) { model.stagingDone = nil }.buttonStyle(SocleButtonStyle(.secondary, height: 34)).fixedSize()
            }
        }
        .frame(width: 860, height: 620)
        .onAppear { rows = buildRows(done.result.items) }
    }
}

// MARK: - Aperçu en taille réelle

struct ImagePreviewSheet: View {
    let item: ImagePreviewItem
    let close: () -> Void

    var body: some View {
        let size = item.image.size
        VStack(spacing: 8) {
            ScrollView([.horizontal, .vertical]) {
                Image(nsImage: item.image).resizable().frame(width: size.width, height: size.height)
                    .padding(12).frame(minWidth: 380)
            }
            .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
            HStack {
                Text(T("ui.dimensions", ["w": Int(size.width), "h": Int(size.height)])).socle(Socle.T.meta).foregroundStyle(Socle.C.textMuted)
                Spacer()
                Button(T("common.close"), action: close).buttonStyle(SocleButtonStyle(.secondary, height: 32)).fixedSize()
            }
        }
        .padding(10)
        .background(Socle.C.surface)
        .frame(width: min(max(size.width + 40, 500), (NSScreen.main?.visibleFrame.width ?? 1280) - 80),
               height: min(max(size.height + 70, 400), (NSScreen.main?.visibleFrame.height ?? 900) - 100))
    }
}
