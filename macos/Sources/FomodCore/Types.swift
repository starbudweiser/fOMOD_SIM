// Types du moteur FOMOD (traduction de python_app/fomod/types.py).

import Foundation

public enum GroupType: String, CaseIterable {
    case selectExactlyOne = "SelectExactlyOne"
    case selectAtLeastOne = "SelectAtLeastOne"
    case selectAtMostOne = "SelectAtMostOne"
    case selectAny = "SelectAny"
    case selectAll = "SelectAll"
}

/// Fichier ou dossier à installer (`FomodFileItem` et `FomodFolderItem` de la version Python : mêmes champs).
public struct FomodItem {
    public enum Kind { case file, folder }
    public var kind: Kind
    public var source: String
    public var destination: String
    public var priority: Int = 0
    /// alwaysInstall : installé même si l'option n'est pas cochée (étape visible)
    public var alwaysInstall = false
    /// installIfUsable : installé même non coché, sauf si l'option est « NotUsable »
    public var installIfUsable = false

    public init(kind: Kind, source: String, destination: String, priority: Int = 0, alwaysInstall: Bool = false, installIfUsable: Bool = false) {
        self.kind = kind; self.source = source; self.destination = destination
        self.priority = priority; self.alwaysInstall = alwaysInstall; self.installIfUsable = installIfUsable
    }
}

public struct FileDependency: Equatable {
    public var file: String
    public var state: String  // 'Active' | 'Inactive' | 'Missing'
    public init(_ file: String, _ state: String) { self.file = file; self.state = state }
}

public struct FlagDependency: Equatable {
    public var flag: String
    public var value: String
    public init(_ flag: String, _ value: String) { self.flag = flag; self.value = value }
}

public final class FomodDependencies {
    public var op: String = "And"  // 'And' | 'Or' | 'Not'
    public var fileDependencies: [FileDependency] = []
    public var flagDependencies: [FlagDependency] = []
    public var nestedDependencies: [FomodDependencies] = []
    /// Conditions non simulables (version du jeu, de FOMM, de SKSE…) : considérées satisfaites
    public var assumedTrue = 0

    public init(op: String = "And", fileDependencies: [FileDependency] = [], flagDependencies: [FlagDependency] = [],
                nestedDependencies: [FomodDependencies] = [], assumedTrue: Int = 0) {
        self.op = op; self.fileDependencies = fileDependencies; self.flagDependencies = flagDependencies
        self.nestedDependencies = nestedDependencies; self.assumedTrue = assumedTrue
    }
}

public struct TypeDescriptorPattern {
    public var dependencies: FomodDependencies
    public var typeName: String = "Optional"  // 'Recommended' | 'Optional' | 'Required' | 'NotUsable' | 'CouldBeUsable'
    public init(dependencies: FomodDependencies, typeName: String = "Optional") { self.dependencies = dependencies; self.typeName = typeName }
}

public struct TypeDescriptor {
    public var defaultType = "Optional"
    public var patterns: [TypeDescriptorPattern] = []
    public init(defaultType: String = "Optional", patterns: [TypeDescriptorPattern] = []) { self.defaultType = defaultType; self.patterns = patterns }
}

public struct ConditionalInstallPattern {
    public var dependencies: FomodDependencies
    public var files: [FomodItem] = []
    public var folders: [FomodItem] = []
    public init(dependencies: FomodDependencies, files: [FomodItem] = [], folders: [FomodItem] = []) {
        self.dependencies = dependencies; self.files = files; self.folders = folders
    }
}

public final class FomodOption {
    public let id: String
    public var name: String
    public var description: String = ""
    public var imagePath: String?
    public var files: [FomodItem] = []
    public var folders: [FomodItem] = []
    /// Flags posés par l'option (nom -> valeur)
    public var flags: [String: String] = [:]
    public var dependencies: FomodDependencies?
    public var typeDescriptor: TypeDescriptor?
    public var isDefault = false
    /// Masters des plugins de l'option hors jeu de base et hors mod (voir Plugins.annotateOptionMasters)
    public var requiredMasters: Set<String> = []

    public init(id: String, name: String, description: String = "", imagePath: String? = nil, files: [FomodItem] = [],
                folders: [FomodItem] = [], flags: [String: String] = [:], dependencies: FomodDependencies? = nil,
                typeDescriptor: TypeDescriptor? = nil, isDefault: Bool = false) {
        self.id = id; self.name = name; self.description = description; self.imagePath = imagePath
        self.files = files; self.folders = folders; self.flags = flags; self.dependencies = dependencies
        self.typeDescriptor = typeDescriptor; self.isDefault = isDefault
    }
}

public final class FomodGroup {
    public let id: String
    public var name: String
    public var type: GroupType
    public var options: [FomodOption]
    public init(id: String, name: String, type: GroupType, options: [FomodOption] = []) {
        self.id = id; self.name = name; self.type = type; self.options = options
    }
}

public final class FomodStep {
    public let id: String
    public var name: String
    public var groups: [FomodGroup]
    /// Condition <visible> de l'étape (nil = toujours visible)
    public var visibility: FomodDependencies?
    public init(id: String, name: String, groups: [FomodGroup] = [], visibility: FomodDependencies? = nil) {
        self.id = id; self.name = name; self.groups = groups; self.visibility = visibility
    }
}

public struct FomodMetadata {
    public var name = "Mod Skyrim"
    public var author = ""
    public var version = "1.0.0"
    public var website = ""
    public var description = ""
    public init(name: String = "Mod Skyrim", author: String = "", version: String = "1.0.0", website: String = "", description: String = "") {
        self.name = name; self.author = author; self.version = version; self.website = website; self.description = description
    }
}

public final class VirtualFileEntry {
    public var path: String
    public var isDir: Bool
    public var size: Int
    public var data: Data?
    public var extractedDiskPath: String?
    /// Nom exact du membre dans l'archive (pour une lecture différée, ex. aperçu d'une texture)
    public var member: String?

    public init(path: String, isDir: Bool = false, size: Int = 0, data: Data? = nil, extractedDiskPath: String? = nil, member: String? = nil) {
        self.path = path; self.isDir = isDir; self.size = size; self.data = data
        self.extractedDiskPath = extractedDiskPath; self.member = member
    }
}

public final class ArchiveIndex {
    public var files: OrderedDict<VirtualFileEntry>  // chemin en minuscules -> entrée
    public var dirs: OrderedDict<String>  // chemin en minuscules -> chemin d'origine
    public var archivePath: String?
    public var tempDir: String?
    private var _basenameMap: [String: [VirtualFileEntry]]?

    public init(files: OrderedDict<VirtualFileEntry> = OrderedDict(), dirs: OrderedDict<String> = OrderedDict(),
                archivePath: String? = nil, tempDir: String? = nil) {
        self.files = files; self.dirs = dirs; self.archivePath = archivePath; self.tempDir = tempDir
    }

    public var basenameMap: [String: [VirtualFileEntry]] {
        if let m = _basenameMap { return m }
        var bm: [String: [VirtualFileEntry]] = [:]
        for (relKey, entry) in files.items {
            if relKey.contains("__macosx") { continue }
            bm[relKey.lastSlashComponent, default: []].append(entry)
        }
        for k in Array(bm.keys) {
            // tri stable par longueur du chemin (en points de code)
            bm[k] = bm[k]!.enumerated().sorted { a, b in
                let la = a.element.path.pyLen, lb = b.element.path.pyLen
                return la != lb ? la < lb : a.offset < b.offset
            }.map(\.element)
        }
        _basenameMap = bm
        return bm
    }

    public func clearCache() { _basenameMap = nil }
}

public final class StagingItem {
    public var sourcePath: String
    public var destinationPath: String
    public var type: String  // 'file' | 'folder'
    public var size: Int
    public var matchedFromOption: String
    public var data: Data?
    public var priority: Int
    public var extractedDiskPath: String?
    /// Membre de l'archive à lire à l'export quand le contenu n'a pas été chargé à l'indexation
    public var member: String?

    public init(sourcePath: String, destinationPath: String, type: String, size: Int, matchedFromOption: String,
                data: Data? = nil, priority: Int = 0, extractedDiskPath: String? = nil, member: String? = nil) {
        self.sourcePath = sourcePath; self.destinationPath = destinationPath; self.type = type; self.size = size
        self.matchedFromOption = matchedFromOption; self.data = data; self.priority = priority
        self.extractedDiskPath = extractedDiskPath; self.member = member
    }
}

public struct StagingResult {
    public var items: [StagingItem]
    public var totalSize: Int
    public var copiedCount: Int
    public var missingCount: Int
    public var log: [String]
}
