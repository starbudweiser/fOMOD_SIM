// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "fOMODSIM",
    platforms: [.macOS(.v15)],
    targets: [
        // Moteur FOMOD (analyse de ModuleConfig.xml, session d'installation, staging, archives par bsdtar), sans interface
        .target(name: "FomodCore"),
        // Exécutable de comparaison avec la version Python : sort en JSON l'arbre, le déroulé et le staging d'une archive
        .executableTarget(name: "fomod-parity", dependencies: ["FomodCore"]),
        .executableTarget(name: "fOMODSIM", dependencies: ["FomodCore"]),
        .testTarget(name: "FomodCoreTests", dependencies: ["FomodCore"]),
    ],
    swiftLanguageModes: [.v5]
)
