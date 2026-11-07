// État et actions de la fenêtre principale (traduction de python_app/gui/main_window.py) : mod ouvert, session
// d'installation, navigation entre étapes, aperçus d'images, dossier Data, staging et export.

import AppKit
import FomodCore
import SwiftUI

let APP_NAME = "fOMODSIM"
/// Bleu du logo : le « f » du nom de l'appli (hors menus déroulants)
let LOGO_BLUE = Color(red: 0x16 / 255, green: 0x77 / 255, blue: 0xdc / 255)
let WINDOW_SIZE = CGSize(width: 1340, height: 840)

/// Passe un objet non « Sendable » d'une tâche d'arrière-plan à l'autre (les objets du moteur ne sont lus que par un fil à la fois).
final class Box<T>: @unchecked Sendable {
    let value: T
    init(_ value: T) { self.value = value }
}

struct AlertItem: Identifiable {
    let id = UUID()
    var title: String
    var message: String
    var details: String?
}

struct ConfirmItem: Identifiable {
    let id = UUID()
    var title: String
    var message: String
    var confirmLabel: String
    var cancelLabel: String
    var destructive = false
    var action: () -> Void
}

struct StagingDone: Identifiable {
    let id = UUID()
    var result: StagingResult
    var target: String
}

struct ImagePreviewItem: Identifiable {
    let id = UUID()
    var image: NSImage
    var title: String
}

@MainActor @Observable
final class AppModel {
    /// Essais : FOMODSIM_SUITE=<domaine> remplace les préférences de l'utilisateur par un domaine jetable
    let settings = AppSettings(suite: ProcessInfo.processInfo.environment["FOMODSIM_SUITE"])

    // Mod ouvert
    var inSimulator = false
    var metadata = FomodMetadata(name: APP_NAME)
    var steps: [FomodStep] = []
    var requiredFiles: [FomodItem] = []
    var conditionalInstalls: [ConditionalInstallPattern] = []
    var archiveIndex = ArchiveIndex()
    var session: InstallSession?
    var currentStepIdx = 0
    var modSourcePath: String?

    // Aperçu
    var activePreviewOption: FomodOption?
    var previewImage: NSImage?
    var previewDescription = ""
    private var previewCache: [String: NSImage] = [:]
    private var previewLoading = false
    private var previewPending = false

    // Environnement
    var dataDirPath: String?
    var installedBasenames: Set<String> = []
    var stagingDirPath = ""
    var stagingDirChosen = false

    // Activité et fenêtres de dialogue
    var loadingStatus: String?
    var exporting = false
    var isDragging = false
    var showOpenMod = false
    var showDataDir = false
    var showModInfo = false
    var stagingDone: StagingDone?
    var imagePreview: ImagePreviewItem?
    var alert: AlertItem?
    var confirm: ConfirmItem?
    var tick = 0  // force le redessin des textes après un changement de langue

    weak var window: NSWindow?
    private var loadGeneration = 0

    var busy: Bool { loadingStatus != nil || exporting }

    /// Ferme les feuilles ouvertes (avant de quitter : un NSApp.terminate reste sans effet tant qu'une feuille est attachée).
    func dismissSheets() {
        showOpenMod = false; showDataDir = false; showModInfo = false
        stagingDone = nil; imagePreview = nil; alert = nil; confirm = nil
    }

    // MARK: Langue

    var languageChoice: String { LangChoice.normalize(settings.string("language", LangChoice.auto)) }

    func setLanguage(_ choice: String) {
        let c = LangChoice.normalize(choice)
        settings.set("language", c)
        I18n.setLang(LangChoice.resolve(c))
        tick += 1
        if inSimulator { refreshPreview() } else { previewDescription = T("ui.optionDesc") }
    }

    // MARK: Session

    var selectedIDs: Set<String> { session?.selected ?? [] }
    var activeFlags: [String: String] { session?.activeFlags ?? [:] }

    private func startSession(_ steps: [FomodStep], _ req: [FomodItem], _ cond: [ConditionalInstallPattern]) {
        self.steps = steps
        requiredFiles = req
        conditionalInstalls = cond
        annotateOptionMasters(archiveIndex, steps)  // pré-sélection des patchs selon le dossier Data
        session = InstallSession(steps: steps, requiredFiles: req, conditionalInstalls: cond, installedBasenames: installedBasenames)
        currentStepIdx = session?.visibleStepIndices().first ?? 0
    }

    var visibleSteps: [Int] { session?.visibleStepIndices() ?? [] }

    /// (position 1-based de l'étape courante parmi les étapes visibles, nombre d'étapes visibles)
    var stepPosition: (Int, Int) {
        let vis = visibleSteps
        if vis.isEmpty { return (0, 0) }
        let pos = (vis.firstIndex(of: currentStepIdx).map { $0 + 1 }) ?? 1
        return (pos, vis.count)
    }

    var isLastStep: Bool {
        let vis = visibleSteps
        return vis.isEmpty || currentStepIdx >= vis.last!
    }

    var currentStep: FomodStep? { steps.indices.contains(currentStepIdx) ? steps[currentStepIdx] : nil }

    /// Étape devenue invisible après un changement de choix : on se replace sur la plus proche.
    private func fixCurrentStep() {
        let vis = visibleSteps
        if !vis.isEmpty && !vis.contains(currentStepIdx) {
            let earlier = vis.filter { $0 < currentStepIdx }
            currentStepIdx = earlier.last ?? vis[0]
        }
    }

    func groupOf(_ option: FomodOption) -> FomodGroup? {
        for step in steps { for g in step.groups where g.options.contains(where: { $0.id == option.id }) { return g } }
        return nil
    }

    func matchesDependency(_ opt: FomodOption) -> Bool {
        guard let s = session else { return false }
        return optionMatchesInstalled(opt, installedBasenames, s.flagsBefore(currentStepIdx))
    }

    func nextStep() {
        if let later = visibleSteps.first(where: { $0 > currentStepIdx }) {
            currentStepIdx = later
            stepChanged()
        } else {
            generateStaging()
        }
    }

    func prevStep() {
        if let earlier = visibleSteps.last(where: { $0 < currentStepIdx }) {
            currentStepIdx = earlier
            stepChanged()
        }
    }

    private func stepChanged() {
        fixCurrentStep()
        guard let step = currentStep else { return }
        // Aperçu : première option cochée de l'étape, sinon la première
        var target: FomodOption?
        outer: for g in step.groups { for o in g.options where selectedIDs.contains(o.id) { target = o; break outer } }
        target = target ?? step.groups.first?.options.first
        if let t = target { hover(t) } else { activePreviewOption = nil; previewImage = nil }
    }

    func select(_ option: FomodOption, in group: FomodGroup) {
        guard let s = session, s.toggle(option, group: group) else { hover(option); return }
        stepChanged()
        hover(option)
    }

    func hover(_ option: FomodOption) {
        activePreviewOption = option
        refreshPreview()
    }

    // MARK: Ouverture d'un mod

    func pickArchive() {
        let p = NSOpenPanel()
        p.title = T("ui.pickArchive")
        p.canChooseFiles = true
        p.canChooseDirectories = false
        p.allowsMultipleSelection = false
        guard p.runModal() == .OK, let url = p.url else { return }
        loadArchive(url.path)
    }

    func pickModFolder() {
        let p = NSOpenPanel()
        p.title = T("ui.pickModFolder")
        p.canChooseFiles = false
        p.canChooseDirectories = true
        p.allowsMultipleSelection = false
        guard p.runModal() == .OK, let url = p.url else { return }
        loadArchive(url.path)
    }

    func loadDemo() {
        let demo = getDemoMod()
        modSourcePath = nil
        archiveIndex = demo.index
        metadata = parseInfoXML(demo.infoXML)
        do {
            let c = try parseModuleConfigXML(demo.moduleConfigXML)
            if !c.moduleName.isEmpty { metadata.name = c.moduleName }
            startSession(c.steps, c.requiredFiles, c.conditionalInstalls)
            enterSimulator()
        } catch {
            alert = AlertItem(title: T("ui.processingError"), message: T("ui.analysisError", ["e": "\(error)"]))
        }
    }

    func loadArchive(_ path: String) {
        modSourcePath = path
        loadGeneration += 1
        let gen = loadGeneration
        loadingStatus = T("ui.extractingFile", ["name": pyName(path)])
        Task.detached(priority: .userInitiated) { [weak self] in
            let result: Result<Box<ExtractedArchive>, Error>
            do {
                let r = try extractArchive(path, progress: { msg in
                    Task { @MainActor [weak self] in if self?.loadGeneration == gen { self?.loadingStatus = msg } }
                })
                result = .success(Box(r))
            } catch { result = .failure(error) }
            await MainActor.run { [weak self] in
                guard let self, self.loadGeneration == gen else { return }
                self.loadingStatus = nil
                switch result {
                case .success(let r): self.archiveExtracted(r.value)
                case .failure(let e): self.alert = AlertItem(title: T("ui.error"), message: "\(e)")
                }
            }
        }
    }

    private func archiveExtracted(_ ex: ExtractedArchive) {
        let cfg = ex.moduleConfigXML
        if cfg.isEmpty {
            alert = AlertItem(title: T("ui.noConfigTitle"), message: T("ui.noConfigMessage"))
            return
        }
        do {
            archiveIndex = ex.index
            metadata = ex.infoXML.isEmpty ? FomodMetadata(name: "Mod FOMOD") : parseInfoXML(ex.infoXML)
            let c = try parseModuleConfigXML(cfg)
            var steps = c.steps
            if steps.isEmpty {
                steps = [FomodStep(id: "step_default", name: T("ui.modInstall"), groups: [
                    FomodGroup(id: "grp_default", name: T("ui.modComponents"), type: .selectExactlyOne, options: [
                        FomodOption(id: "opt_default", name: T("ui.installDefaults"), description: T("ui.autoInstallDesc"),
                                    files: c.requiredFiles.filter { $0.kind == .file }, folders: c.requiredFiles.filter { $0.kind == .folder },
                                    isDefault: true)])])]
            }
            if !c.moduleName.isEmpty { metadata.name = c.moduleName }
            startSession(steps, c.requiredFiles, c.conditionalInstalls)
            enterSimulator()
        } catch {
            alert = AlertItem(title: T("ui.processingError"), message: T("ui.analysisError", ["e": "\(error)"]))
        }
    }

    private func enterSimulator() {
        previewCache.removeAll()
        inSimulator = true
        stepChanged()
    }

    func closeMod() {
        loadGeneration += 1
        loadingStatus = nil
        steps = []
        metadata = FomodMetadata(name: APP_NAME)
        session = nil
        activePreviewOption = nil
        previewImage = nil
        inSimulator = false
    }

    // MARK: Dossier Data

    func applyDataDir(path: String, plugins: Set<String>) {
        dataDirPath = path
        installedBasenames = plugins
        session?.setInstalledBasenames(plugins)  // les choix par défaut sont recalculés
        if inSimulator { stepChanged() }
    }

    // MARK: Aperçu des images

    func refreshPreview() {
        guard let option = activePreviewOption else { return }
        previewDescription = option.description.isEmpty ? T("ui.noDesc") : option.description
        previewImage = pixmap(for: option)
    }

    private func pixmap(for option: FomodOption) -> NSImage {
        let (primary, fallback) = pickPreviewEntries(archiveIndex, option, group: groupOf(option))
        for entry in [primary, fallback] {
            guard let entry else { continue }
            let key = entry.path.lowercased()
            if let img = previewCache[key] { return img }
            if (entry.data?.isEmpty == false) || entry.extractedDiskPath != nil {
                if let img = loadImage(path: entry.extractedDiskPath, data: entry.data) { return img }
            } else if entry === primary {
                prefetchPreviews()
            }
        }
        return generatedPreview(option: option, index: archiveIndex)
    }

    /// Charge en une passe les aperçus différés de toutes les options de l'étape courante (textures d'un 7z…).
    private func prefetchPreviews() {
        guard let step = currentStep else { return }
        if previewLoading { previewPending = true; return }
        var entries: [VirtualFileEntry] = []
        for g in step.groups {
            for o in g.options {
                let (primary, _) = pickPreviewEntries(archiveIndex, o, group: g)
                if let p = primary, p.data?.isEmpty != false, p.extractedDiskPath == nil, previewCache[p.path.lowercased()] == nil {
                    entries.append(p)
                }
            }
        }
        if entries.isEmpty { return }
        previewLoading = true
        let box = Box(entries), index = Box(archiveIndex)
        Task.detached(priority: .userInitiated) { [weak self] in
            var out: [String: NSImage] = [:]
            for (key, data) in readEntriesBytes(index.value, box.value) {
                if let img = loadImage(path: nil, data: data, maxSize: 1280) { out[key] = img }
            }
            let images = Box(out)
            await MainActor.run { [weak self] in
                guard let self else { return }
                self.previewLoading = false
                self.previewCache.merge(images.value) { $1 }
                if self.activePreviewOption != nil { self.refreshPreview() }
                if self.previewPending { self.previewPending = false; self.prefetchPreviews() }
            }
        }
    }

    func openImagePreview() {
        guard let o = activePreviewOption, let img = previewImage else { return }
        imagePreview = ImagePreviewItem(image: img, title: o.name)
    }

    // MARK: Staging

    func chooseStagingDir() -> Bool {
        let p = NSOpenPanel()
        p.title = T("ui.pickStagingDir")
        p.canChooseFiles = false
        p.canChooseDirectories = true
        p.canCreateDirectories = true
        p.allowsMultipleSelection = false
        guard p.runModal() == .OK, let url = p.url else { return false }
        stagingDirPath = url.path
        stagingDirChosen = true
        return true
    }

    /// Génère physiquement les fichiers dans le dossier choisi, puis ouvre le résultat.
    func generateStaging() {
        guard let session else { return }
        if !(stagingDirChosen && isDir(stagingDirPath)) {
            confirm = ConfirmItem(title: T("stagingWarning.title"), message: T("stagingWarning.message"),
                                  confirmLabel: T("stagingWarning.choose"), cancelLabel: T("stagingWarning.cancel")) { [weak self] in
                guard let self, self.chooseStagingDir() else { return }
                self.generateStaging()
            }
            return
        }
        let res = session.buildStaging(archiveIndex)
        let target = pyJoin(stagingDirPath, stagingFolderName(modSourcePath, modName: metadata.name))
        confirmReplace(target) { [weak self] in self?.writeStaging(res, target) }
    }

    /// Dossier du mod déjà présent et non vide : remplacer son contenu après confirmation.
    private func confirmReplace(_ target: String, then proceed: @escaping () -> Void) {
        let fm = FileManager.default
        guard isDir(target), !((try? fm.contentsOfDirectory(atPath: target))?.isEmpty ?? true) else { proceed(); return }
        confirm = ConfirmItem(title: T("stagingExport.existsTitle", ["name": pyName(target)]), message: T("stagingExport.existsMessage"),
                              confirmLabel: T("stagingExport.replace"), cancelLabel: T("stagingWarning.cancel"), destructive: true) { [weak self] in
            do { try fm.removeItem(atPath: target) } catch {
                self?.alert = AlertItem(title: T("ui.stagingError"), message: T("ui.cannotEmpty", ["target": target, "e": "\(error)"]))
                return
            }
            proceed()
        }
    }

    private func writeStaging(_ res: StagingResult, _ target: String) {
        loadingStatus = T("stagingExport.writing")
        exporting = true
        let r = Box(res), index = Box(archiveIndex)
        Task.detached(priority: .userInitiated) { [weak self] in
            let failures = exportStagingToDirectory(r.value, targetDir: target, archiveIndex: index.value, progress: { msg in
                Task { @MainActor [weak self] in if self?.exporting == true { self?.loadingStatus = msg } }
            })
            await MainActor.run { [weak self] in
                guard let self else { return }
                self.loadingStatus = nil
                self.exporting = false
                if !failures.isEmpty {
                    self.alert = AlertItem(title: T("stagingExport.failedTitle", ["count": failures.count]),
                                           message: T("stagingExport.failedMessage"), details: failures.joined(separator: "\n"))
                }
                self.stagingDone = StagingDone(result: res, target: target)
            }
        }
    }

    /// Export du staging en archive ZIP (bouton du résultat).
    func exportZip(_ done: StagingDone) {
        let p = NSSavePanel()
        p.title = T("ui.saveModTitle")
        p.nameFieldStringValue = "Staging_Skyrim_Mod.zip"
        p.allowedContentTypes = [.zip]
        guard p.runModal() == .OK, let url = p.url else { return }
        let r = Box(done.result), index = Box(archiveIndex)
        loadingStatus = T("stagingExport.writing")
        exporting = true
        Task.detached(priority: .userInitiated) { [weak self] in
            let failures = exportStagingToZip(r.value, zipPath: url.path, archiveIndex: index.value)
            await MainActor.run { [weak self] in
                self?.loadingStatus = nil
                self?.exporting = false
                if !failures.isEmpty {
                    self?.alert = AlertItem(title: T("ui.zipExportTitle"), message: T("ui.zipMissing", ["n": failures.count]),
                                            details: failures.prefix(15).joined(separator: "\n"))
                }
            }
        }
    }

    /// Essais : staging écrit sans fenêtre de dialogue dans un dossier donné.
    func scriptedStage(_ dir: String) {
        guard let session else { return }
        stagingDirPath = dir
        stagingDirChosen = true
        let res = session.buildStaging(archiveIndex)
        let target = pyJoin(dir, stagingFolderName(modSourcePath, modName: metadata.name))
        try? FileManager.default.removeItem(atPath: target)
        let failures = exportStagingToDirectory(res, targetDir: target, archiveIndex: archiveIndex)
        scriptLog += "staging: \(res.items.count) éléments, \(failures.count) échec(s) -> \(target)\n"
        stagingDone = StagingDone(result: res, target: target)
    }

    var scriptLog = ""
}
