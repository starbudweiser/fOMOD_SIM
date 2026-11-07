// Interface : en-tête, accueil, simulateur à 3 colonnes (actions, étapes, aperçu), recouvrements (dépôt, chargement)
// — traduction de python_app/gui/main_window.py.

import AppKit
import FomodCore
import SwiftUI
import UniformTypeIdentifiers

/// Mini rendu des textes à balises des fichiers de langue : <b>…</b> en gras, <span …>…</span> en valeur mise en avant,
/// &bull; en puce, <br/> en retour à la ligne.
func richText(_ html: String, mono: Bool = false) -> Text {
    var out = Text("")
    var rest = html.replacingOccurrences(of: "&bull;", with: "•").replacingOccurrences(of: "<br/>", with: "\n")
        .replacingOccurrences(of: "<br>", with: "\n")
    let rx = try! NSRegularExpression(pattern: "<(b|span)[^>]*>(.*?)</\\1>", options: [.dotMatchesLineSeparators])
    while let m = rx.firstMatch(in: rest, range: NSRange(rest.startIndex..., in: rest)) {
        let r = Range(m.range, in: rest)!
        out = out + Text(String(rest[..<r.lowerBound]))
        let tag = String(rest[Range(m.range(at: 1), in: rest)!])
        let inner = String(rest[Range(m.range(at: 2), in: rest)!])
        if tag == "b" {
            out = out + Text(inner).bold()
        } else {
            out = out + Text(inner).font(.system(size: Socle.T.meta.pointSize, weight: .semibold, design: .monospaced)).foregroundColor(Socle.C.accentText)
        }
        rest = String(rest[r.upperBound...])
    }
    return out + Text(rest)
}

func formatBytes(_ sz: Int) -> String {
    if sz <= 0 { return "0 o" }
    if sz < 1024 { return "\(sz) o" }
    if sz < 1024 * 1024 { return String(format: "%.1f Ko", Double(sz) / 1024) }
    return String(format: "%.2f Mo", Double(sz) / (1024 * 1024))
}

struct ContentView: View {
    @Bindable var model: AppModel

    var body: some View {
        let _ = model.tick
        ZStack {
            VStack(spacing: Socle.M.space1_5) {
                HeaderBar(model: model)
                if model.inSimulator { SimulatorView(model: model) } else { WelcomeView(model: model) }
            }
            .padding(Socle.M.space2)
            .id(model.tick)  // changement de langue : toute l'interface est reconstruite

            if model.isDragging { DragOverlay() }
            if let status = model.loadingStatus { LoadingOverlay(status: status) }
        }
        .background(Socle.C.bg)
        .frame(minWidth: 1000, minHeight: 680)
        .onDrop(of: [.fileURL], isTargeted: $model.isDragging) { providers in
            guard let p = providers.first else { return false }
            _ = p.loadObject(ofClass: URL.self) { url, _ in
                guard let path = url?.path else { return }
                Task { @MainActor in model.loadArchive(path) }
            }
            return true
        }
        .sheet(isPresented: $model.showOpenMod) { OpenModSheet(model: model) }
        .sheet(isPresented: $model.showDataDir) { DataDirSheet(model: model) }
        .sheet(isPresented: $model.showModInfo) { ModInfoSheet(metadata: model.metadata) { model.showModInfo = false } }
        .sheet(item: $model.stagingDone) { done in StagingResultSheet(model: model, done: done) }
        .sheet(item: $model.imagePreview) { item in ImagePreviewSheet(item: item) { model.imagePreview = nil } }
        .alert(item: $model.alert) { a in
            if let d = a.details {
                Alert(title: Text(a.title), message: Text(a.message + "\n\n" + d), dismissButton: .default(Text(T("ui.ok"))))
            } else {
                Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text(T("ui.ok"))))
            }
        }
        .alert(item: $model.confirm) { c in
            Alert(title: Text(c.title), message: Text(c.message),
                  primaryButton: c.destructive ? .destructive(Text(c.confirmLabel), action: c.action) : .default(Text(c.confirmLabel), action: c.action),
                  secondaryButton: .cancel(Text(c.cancelLabel)))
        }
    }
}

// MARK: - En-tête

struct HeaderBar: View {
    @Bindable var model: AppModel

    var body: some View {
        HStack(spacing: Socle.M.space2_5) {
            Text("⚡").font(.system(size: 14))
            Group {
                if model.inSimulator { Text(model.metadata.name) } else { Text(branded: APP_NAME) }
            }
            .socle(Socle.T.title).foregroundStyle(Socle.C.textStrong).lineLimit(1)
            Spacer(minLength: 0)
            if model.inSimulator {
                Button(T("header.closeMod")) { model.closeMod() }
                    .buttonStyle(SocleButtonStyle(.secondary, height: 26)).fixedSize()
                    .help(T("header.closeModTooltip"))
                Text("|").foregroundStyle(Socle.C.borderStrong)
                let (pos, total) = model.stepPosition
                Text(T("header.stepCounter", ["current": pos, "total": total])).socle(Socle.T.monoSm).foregroundStyle(Socle.C.textSubtle)
                Text("|").foregroundStyle(Socle.C.borderStrong)
                Text(model.activeFlags.isEmpty ? T("header.skyrimEnv") : T("header.flagsCount", ["count": model.activeFlags.count]))
                    .socle(Socle.T.meta).foregroundStyle(Socle.C.textMuted)
            } else {
                Text(T("header.waitingArchive")).socle(Socle.T.meta).foregroundStyle(Socle.C.textMuted)
            }
        }
        .padding(.horizontal, Socle.M.space3)
        .frame(height: Socle.M.sizeBar)
        .background(Socle.C.surfaceRaised, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }
}

// MARK: - Accueil

struct WelcomeView: View {
    @Bindable var model: AppModel
    @State private var hoverDrop = false

    var body: some View {
        ZStack {
            Socle.C.bgSunken
            VStack(spacing: 14) {
                Image(nsImage: NSApp.applicationIconImage).resizable().frame(width: 64, height: 64)
                Text(branded: APP_NAME).socle(Socle.T.display).foregroundStyle(Socle.C.textStrong)
                Text(T("welcome.subtitle")).socle(Socle.T.body).foregroundStyle(Socle.C.textSubtle)
                    .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)

                VStack(spacing: Socle.M.space2_5) {
                    Text("📥").font(.system(size: 30))
                    Text(T("welcome.dropTitle")).socle(Socle.T.title).foregroundStyle(Socle.C.textStrong)
                    richText(T("welcome.supportedFormats")).font(.system(size: Socle.T.meta.pointSize)).foregroundStyle(Socle.C.textSubtle)
                        .multilineTextAlignment(.center)
                    Button("📁  " + T("welcome.loadArchiveBtn")) { model.pickArchive() }
                        .buttonStyle(SocleButtonStyle(.action, height: 38)).fixedSize()
                }
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 20).padding(.vertical, 24)
                .background(hoverDrop ? Socle.C.surfaceHover : Socle.C.bgInset, in: RoundedRectangle(cornerRadius: Socle.M.radiusLg))
                .overlay(RoundedRectangle(cornerRadius: Socle.M.radiusLg)
                    .strokeBorder(hoverDrop ? Socle.C.accent : Socle.C.borderStrong, style: StrokeStyle(lineWidth: 2, dash: [6, 4])))
                .onHover { hoverDrop = $0 }
                .contentShape(Rectangle())
                .onTapGesture { model.pickArchive() }

                HStack(spacing: 12) {
                    linkButton("📂  " + T("welcome.loadFolderBtn")) { model.pickModFolder() }
                    Text("•").foregroundStyle(Socle.C.borderStrong)
                    linkButton("🧪  " + T("welcome.loadDemoBtn")) { model.loadDemo() }
                }

                Divider().overlay(Socle.C.borderSubtle).padding(.top, 6)
                HStack {
                    Text(T("welcome.standaloneEngine")).socle(Socle.T.meta).foregroundStyle(Socle.C.textSubtle)
                    Spacer()
                    Text(T("welcome.noGameRequired")).socle(Socle.T.meta).foregroundStyle(Socle.C.textSubtle)
                }
            }
            .padding(.horizontal, 28).padding(.top, 20).padding(.bottom, 24)
            .frame(width: 580)
            .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusXl))
        }
        .clipShape(RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }

    private func linkButton(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).socle(Socle.T.label).foregroundStyle(Socle.C.textSubtle).underline()
        }.buttonStyle(.plain)
    }
}

// MARK: - Simulateur

struct SimulatorView: View {
    @Bindable var model: AppModel

    var body: some View {
        HSplitView {
            LeftColumn(model: model).frame(minWidth: 185, idealWidth: 195, maxWidth: 320)
            CenterColumn(model: model).frame(minWidth: 300, idealWidth: 345)
            RightColumn(model: model).frame(minWidth: 380, idealWidth: 460)
        }
    }
}

struct LeftColumn: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: Socle.M.space2) {
            Button("📦  " + T("sidebar.openFomod")) { model.showOpenMod = true }
                .buttonStyle(SocleButtonStyle(.action, height: 46)).help(T("sidebar.openFomodTooltip"))
            Button("ℹ️  " + T("sidebar.modInfo")) { model.showModInfo = true }
                .buttonStyle(SocleButtonStyle(.secondary, height: 34))
            Button("📁  " + T("sidebar.chooseDataDir")) { model.showDataDir = true }
                .buttonStyle(SocleButtonStyle(.secondary, height: 34))
            dataStatus
            Spacer(minLength: 0)
            Button("📁  " + T("sidebar.chooseStagingDir")) { _ = model.chooseStagingDir() }
                .buttonStyle(SocleButtonStyle(.secondary, height: 34))
            VStack(spacing: 2) {
                Text(T("common.destination")).socle(Socle.T.caption).foregroundStyle(Socle.C.textSubtle)
                Text(model.stagingDirChosen ? model.stagingDirPath : T("sidebar.targetDesktop"))
                    .socle(Socle.T.monoSm).foregroundStyle(Socle.C.accentText).lineLimit(2).truncationMode(.middle).multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 8).padding(.horizontal, 6)
            .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radius))
            Button(T("sidebar.generateStaging")) { model.generateStaging() }
                .buttonStyle(SocleButtonStyle(.primary, height: 40)).disabled(model.busy)
        }
        .padding(Socle.M.space2_5)
        .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }

    private var dataStatus: some View {
        VStack(spacing: 2) {
            if let path = model.dataDirPath {
                (Text(T("common.dataFolder")).bold().foregroundColor(Socle.C.text) + Text(" " + pyName(path)).foregroundColor(Socle.C.textMuted))
                    .socle(Socle.T.meta)
                Text("(\(model.installedBasenames.count) \(T("common.filesDetected")))").socle(Socle.T.caption).foregroundStyle(Socle.C.accentText)
            } else {
                (Text(T("common.dataFolder")).bold().foregroundColor(Socle.C.text) + Text(" " + T("common.notSet")).italic().foregroundColor(Socle.C.textMuted))
                    .socle(Socle.T.meta)
                Text(T("common.clickToSimulate")).socle(Socle.T.caption).foregroundStyle(Socle.C.textSubtle)
            }
        }
        .multilineTextAlignment(.center).frame(maxWidth: .infinity).padding(.top, 4)
        .onTapGesture { model.showDataDir = true }
    }
}

struct CenterColumn: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            let (pos, total) = model.stepPosition
            HStack {
                Text(model.currentStep?.name ?? T("steps.noStepsFound")).socle(Socle.T.title).foregroundStyle(Socle.C.textStrong).lineLimit(2)
                Spacer()
                Text("\(pos) / \(total)").socle(Socle.T.monoSm).foregroundStyle(Socle.C.textMuted)
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            Divider().overlay(Socle.C.borderSubtle)

            ScrollView {
                VStack(spacing: Socle.M.space2_5) {
                    if let step = model.currentStep {
                        ForEach(step.groups, id: \.id) { g in GroupCard(model: model, group: g) }
                    }
                }
                .padding(12)
            }

            Divider().overlay(Socle.C.borderSubtle)
            HStack(spacing: Socle.M.space2_5) {
                Button(T("steps.prevStep")) { model.prevStep() }
                    .buttonStyle(SocleButtonStyle(.secondary, height: 38)).disabled(pos <= 1)
                Button(model.isLastStep ? T("steps.finishStep") : T("steps.nextStep")) { model.nextStep() }
                    .buttonStyle(SocleButtonStyle(.primary, height: 38)).disabled(total == 0)
            }
            .padding(12)
        }
        .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }
}

struct GroupCard: View {
    @Bindable var model: AppModel
    let group: FomodGroup

    var body: some View {
        let single = group.type == .selectExactlyOne || group.type == .selectAtMostOne
        VStack(spacing: 6) {
            HStack {
                Text(group.name).socle(Socle.T.labelStrong).foregroundStyle(Socle.C.text)
                Spacer()
                Text(single ? T("common.singleChoice") : T("common.multipleChoice")).socle(Socle.T.caption).foregroundStyle(Socle.C.textMuted)
            }
            Divider().overlay(Socle.C.borderSubtle)
            ForEach(group.options, id: \.id) { opt in
                OptionRow(option: opt, single: single, selected: model.selectedIDs.contains(opt.id), auto: model.matchesDependency(opt),
                          onSelect: { model.select(opt, in: group) }, onHover: { model.hover(opt) })
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Socle.C.bgInset, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }
}

/// Radio rond (choix unique) ou case carrée (choix multiple) : l'accent est sur le contrôle, pas sur la ligne.
struct ChoiceIndicator: View {
    let single: Bool
    let checked: Bool

    var body: some View {
        ZStack {
            if single {
                Circle().fill(checked ? Socle.C.accent : Socle.C.bgInset)
                Circle().strokeBorder(checked ? Socle.C.accent : Socle.C.borderControl, lineWidth: 1.2)
                if checked { Circle().fill(Socle.C.onAccent).frame(width: 6, height: 6) }
            } else {
                RoundedRectangle(cornerRadius: 4).fill(checked ? Socle.C.accent : Socle.C.bgInset)
                RoundedRectangle(cornerRadius: 4).strokeBorder(checked ? Socle.C.accent : Socle.C.borderControl, lineWidth: 1.2)
                if checked {
                    Image(systemName: "checkmark").font(.system(size: 9, weight: .heavy)).foregroundStyle(Socle.C.onAccent)
                }
            }
        }
        .frame(width: 18, height: 18)
    }
}

struct OptionRow: View {
    let option: FomodOption
    let single: Bool
    let selected: Bool
    let auto: Bool
    let onSelect: () -> Void
    let onHover: () -> Void
    @State private var hovered = false

    var body: some View {
        HStack(spacing: 10) {
            ChoiceIndicator(single: single, checked: selected)
            Text(option.name).socle(Socle.T.label)
                .fontWeight(selected ? .semibold : .regular)
                .foregroundStyle(selected ? Socle.C.textStrong : (hovered ? Socle.C.textStrong : Socle.C.text))
                .frame(maxWidth: .infinity, alignment: .leading)
            if auto {
                Text(T("common.auto")).socle(Socle.T.caption).fontWeight(.semibold)
                    .foregroundStyle(Socle.C.accentText)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(Socle.C.accent.opacity(0.15), in: RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(selected || hovered ? Socle.C.surfaceHover : Color.clear, in: RoundedRectangle(cornerRadius: 5))
        .contentShape(Rectangle())
        .onHover { h in
            hovered = h
            if h { onHover() }
        }
        .onTapGesture(perform: onSelect)
    }
}

struct RightColumn: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("📖  " + T("preview.instructionsTitle").uppercased()).socle(Socle.T.eyebrow).foregroundStyle(Socle.C.textMuted)
            ScrollView {
                Text(model.previewDescription).socle(Socle.T.bodyLg).lineSpacing(4).foregroundStyle(Socle.C.textStrong)
                    .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
            }
            .frame(maxHeight: 180)
            if let img = model.previewImage {
                Image(nsImage: img).resizable().interpolation(.high).aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                    .contentShape(Rectangle())
                    .onTapGesture { model.openImagePreview() }
                    .help(T("preview.clickToEnlarge"))
            } else {
                Spacer(minLength: 0)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusMd))
    }
}

// MARK: - Recouvrements

struct DragOverlay: View {
    var body: some View {
        ZStack {
            Color(red: 10 / 255, green: 25 / 255, blue: 45 / 255).opacity(0.76)
            Rectangle().strokeBorder(Color(red: 3 / 255, green: 105 / 255, blue: 161 / 255), style: StrokeStyle(lineWidth: 3, dash: [6, 6])).padding(6)
            VStack(spacing: 10) {
                Text("📥").font(.system(size: 36))
                Text(T("ui.dropTitle")).socle(Socle.T.heading).foregroundStyle(Color.white)
                Text(T("ui.dropSub")).socle(Socle.T.label).foregroundStyle(Socle.C.accent)
            }
            .padding(.horizontal, 24).padding(.vertical, 28).frame(width: 520)
            .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusXl))
        }
        .allowsHitTesting(false)
    }
}

struct LoadingOverlay: View {
    let status: String

    var body: some View {
        ZStack {
            Color.black.opacity(0.8)
            VStack(spacing: 12) {
                ProgressView().controlSize(.large).tint(Socle.C.accentText)
                Text(T("loading.title")).socle(Socle.T.title).foregroundStyle(Socle.C.textStrong)
                Text(status).socle(Socle.T.monoSm).foregroundStyle(Socle.C.accentText).lineLimit(3).multilineTextAlignment(.center)
                    .padding(.horizontal, 14).padding(.vertical, 10).frame(maxWidth: .infinity)
                    .background(Socle.C.bg, in: RoundedRectangle(cornerRadius: Socle.M.radius))
                Text(T("loading.sub")).socle(Socle.T.meta).foregroundStyle(Socle.C.textSubtle).multilineTextAlignment(.center)
            }
            .padding(28).frame(width: 480)
            .background(Socle.C.surface, in: RoundedRectangle(cornerRadius: Socle.M.radiusXl))
        }
    }
}
