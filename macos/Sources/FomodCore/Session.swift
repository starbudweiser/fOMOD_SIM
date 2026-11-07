// Session d'installation FOMOD : état des sélections, flags, visibilité des étapes et règles des groupes
// (traduction de python_app/fomod/session.py).
//
// Reproduit le déroulé d'un installeur (Mod Organizer 2 / Vortex) :
// - une étape n'est affichée que si sa condition <visible> est vraie avec les flags posés par les options cochées
//   dans les étapes visibles qui la précèdent ;
// - seules les options des étapes visibles sont installées et posent des flags ;
// - chaque groupe respecte son type et chaque option son type effectif.

import Foundation

public final class InstallSession {
    public let steps: [FomodStep]
    public let requiredFiles: [FomodItem]
    public let conditionalInstalls: [ConditionalInstallPattern]
    public private(set) var installedBasenames: Set<String>
    public private(set) var selected: Set<String> = []
    private var touchedSteps: Set<Int> = []

    public init(steps: [FomodStep], requiredFiles: [FomodItem] = [], conditionalInstalls: [ConditionalInstallPattern] = [],
                installedBasenames: Set<String> = []) {
        self.steps = steps
        self.requiredFiles = requiredFiles
        self.conditionalInstalls = conditionalInstalls
        self.installedBasenames = installedBasenames
        resetDefaults()
    }

    // MARK: flags et visibilité

    private func stepVisible(_ idx: Int, with flags: [String: String]) -> Bool {
        evaluateDependencies(steps[idx].visibility, installedBasenames, flags)
    }

    /// Parcourt les étapes dans l'ordre et renvoie (flags, étapes visibles) avant l'étape `until`.
    private func walk(until: Int? = nil) -> ([String: String], [Int]) {
        var flags: [String: String] = [:]
        var visible: [Int] = []
        let stop = until ?? steps.count
        var i = 0
        while i < stop {
            defer { i += 1 }
            if !stepVisible(i, with: flags) { continue }
            visible.append(i)
            for opt in stepOptions(i) where selected.contains(opt.id) {
                for (k, v) in opt.flags { flags[k] = v }
            }
        }
        return (flags, visible)
    }

    public func stepOptions(_ idx: Int) -> [FomodOption] { steps[idx].groups.flatMap(\.options) }

    public func flagsBefore(_ idx: Int) -> [String: String] { walk(until: idx).0 }
    public var activeFlags: [String: String] { walk().0 }
    public func visibleStepIndices() -> [Int] { walk().1 }
    public func isStepVisible(_ idx: Int) -> Bool { stepVisible(idx, with: flagsBefore(idx)) }

    public func stepIndex(of optionID: String) -> Int {
        for (i, step) in steps.enumerated() where step.groups.contains(where: { $0.options.contains { $0.id == optionID } }) {
            return i
        }
        return -1
    }

    // MARK: types d'options

    public func optionType(_ opt: FomodOption, stepIdx: Int? = nil) -> String {
        let idx = stepIdx ?? stepIndex(of: opt.id)
        let flags = idx >= 0 ? flagsBefore(idx) : activeFlags
        return computeOptionType(opt, installedBasenames, flags)
    }

    /// Option non modifiable : requise, inutilisable ou groupe « tout sélectionner ».
    public func isLocked(_ opt: FomodOption, group: FomodGroup, stepIdx: Int? = nil) -> Bool {
        let t = optionType(opt, stepIdx: stepIdx).pyLower
        return group.type == .selectAll || t == "required" || t == "notusable"
    }

    // MARK: sélections par défaut

    private func defaultsForGroup(_ group: FomodGroup, _ flags: [String: String]) -> Set<String> {
        var types: [String: String] = [:]
        for o in group.options { types[o.id] = computeOptionType(o, installedBasenames, flags).pyLower }
        let usable = group.options.filter { types[$0.id] != "notusable" }
        let required = usable.filter { types[$0.id] == "required" }
        let recommended = usable.filter { types[$0.id] == "recommended" || isOptionRecommended($0, installedBasenames, flags) }
        // Options justifiées par le dossier Data d'abord (tri stable)
        let matching = recommended.filter { optionMatchesInstalled($0, installedBasenames, flags) }
        let others = recommended.filter { !optionMatchesInstalled($0, installedBasenames, flags) }
        let recSorted = matching + others

        switch group.type {
        case .selectAll:
            return Set(group.options.map(\.id))
        case .selectExactlyOne:
            let pick = !required.isEmpty ? required : (!recSorted.isEmpty ? recSorted : (!usable.isEmpty ? usable : group.options))
            return Set(pick.prefix(1).map(\.id))
        case .selectAtMostOne:
            let pick = !required.isEmpty ? required : recSorted
            return Set(pick.prefix(1).map(\.id))
        case .selectAtLeastOne:
            let reqIDs = Set(required.map(\.id))
            let chosen = required + recSorted.filter { !reqIDs.contains($0.id) }
            if !chosen.isEmpty { return Set(chosen.map(\.id)) }
            if !usable.isEmpty { return Set(usable.prefix(1).map(\.id)) }
            return Set(group.options.prefix(1).map(\.id))
        case .selectAny:
            let reqIDs = Set(required.map(\.id))
            return Set((required + recSorted.filter { !reqIDs.contains($0.id) }).map(\.id))
        }
    }

    private func initStep(_ idx: Int, _ flags: [String: String]) {
        for g in steps[idx].groups {
            for o in g.options { selected.remove(o.id) }
            selected.formUnion(defaultsForGroup(g, flags))
        }
    }

    /// Sélections par défaut de toutes les étapes, dans l'ordre, chacune avec les flags des étapes visibles précédentes.
    public func resetDefaults() {
        selected.removeAll()
        touchedSteps.removeAll()
        refreshUntouched(after: -1)
    }

    /// Recalcule les sélections par défaut des étapes situées après `after` que l'utilisateur n'a pas modifiées.
    private func refreshUntouched(after: Int) {
        var flags: [String: String] = after >= 0 ? flagsBefore(after + 1) : [:]
        var i = after + 1
        while i < steps.count {
            defer { i += 1 }
            if !touchedSteps.contains(i) { initStep(i, flags) }
            if stepVisible(i, with: flags) {
                for opt in stepOptions(i) where selected.contains(opt.id) {
                    for (k, v) in opt.flags { flags[k] = v }
                }
            }
        }
    }

    public func setInstalledBasenames(_ basenames: Set<String>) {
        installedBasenames = basenames
        resetDefaults()
    }

    // MARK: interaction

    /// Clic sur une option. Renvoie false si le clic est refusé par les règles du groupe.
    @discardableResult
    public func toggle(_ opt: FomodOption, group: FomodGroup) -> Bool {
        let stepIdx = stepIndex(of: opt.id)
        let t = optionType(opt, stepIdx: stepIdx).pyLower
        if group.type == .selectAll || t == "required" { return false }
        if t == "notusable" && !selected.contains(opt.id) { return false }

        let ids = Set(group.options.map(\.id))
        let chosen = selected.intersection(ids)
        switch group.type {
        case .selectExactlyOne:
            if chosen.contains(opt.id) { return false }
            selected.subtract(ids)
            selected.insert(opt.id)
        case .selectAtMostOne:
            let was = chosen.contains(opt.id)
            selected.subtract(ids)
            if !was { selected.insert(opt.id) }
        case .selectAtLeastOne:
            if chosen.contains(opt.id) {
                if chosen.count == 1 { return false }
                selected.remove(opt.id)
            } else {
                selected.insert(opt.id)
            }
        default:  // SelectAny
            if chosen.contains(opt.id) { selected.remove(opt.id) } else { selected.insert(opt.id) }
        }
        touchedSteps.insert(stepIdx)
        refreshUntouched(after: stepIdx)
        return true
    }

    public func isSelected(_ opt: FomodOption) -> Bool { selected.contains(opt.id) }

    // MARK: résultat

    /// Options cochées des étapes visibles, dans l'ordre d'installation.
    public func selectedOptions() -> [FomodOption] {
        visibleStepIndices().flatMap { stepOptions($0).filter { selected.contains($0.id) } }
    }

    /// Fichiers alwaysInstall / installIfUsable des options non cochées des étapes visibles.
    public func forcedItems() -> [(item: FomodItem, optionName: String)] {
        var out: [(FomodItem, String)] = []
        for i in visibleStepIndices() {
            let flags = flagsBefore(i)
            for opt in stepOptions(i) where !selected.contains(opt.id) {
                let usable = computeOptionType(opt, installedBasenames, flags).pyLower != "notusable"
                for item in opt.files + opt.folders where item.alwaysInstall || (item.installIfUsable && usable) {
                    out.append((item, opt.name))
                }
            }
        }
        return out
    }

    public func buildStaging(_ archiveIndex: ArchiveIndex) -> StagingResult {
        FomodCore.buildStaging(
            selectedOptions: selectedOptions(), requiredFiles: requiredFiles, archiveIndex: archiveIndex,
            conditionalInstalls: conditionalInstalls, activeFlags: activeFlags, installedBasenames: installedBasenames,
            forcedItems: forcedItems())
    }
}
