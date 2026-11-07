# fOMODSIM

Simulateur d'installation de mods FOMOD pour Skyrim (FR/EN/IT/ES).

## Structure du projet

```
fOMOD_SIM/
├── fOMODSIM.app     # application macOS compilée (générée par build_app.sh)
├── build_app.sh            # lance macos/build_app.sh (traductions, tests, compilation, signature)
├── macos/                  # application Swift (SwiftUI) : Package.swift, Sources, Tests
│   └── Sources/FomodCore/  # moteur FOMOD (analyse, session, staging, archives par bsdtar), sans interface
├── i18n/                   # traductions fr/en/it/es (strings.json, ids.json) : source de macos/…/Strings.swift
├── web/                    # version web (React / Vite) : src, public, package.json…
├── dist/                   # build web (généré par npm run build, non versionné)
├── scripts/                # lanceur .command (Web)
├── assets/                 # icônes (icon.icns, icon.png)
├── docs/                   # documentation FR/EN, fiche Nexus, captures
└── _ARCHIVES/              # versions de référence (non versionné)
```

## Lancement

- **Application macOS** : `fOMODSIM.app`
- **Web (React/Vite)** : `cd web && npm install && npm run dev` (ou `./scripts/run_web.command`)

## Build

- Application macOS signée (générée à la racine) : `./build_app.sh` (ou `../_tools/build_all.sh fOMOD_SIM`, qui l'installe dans `~/Applications/Skyrim Tools`)

## Tests

```bash
cd macos && swift test      # moteur FOMOD, session, staging, plugins, traductions
cd web && npm run lint
```

## Documentation

- [Français](README.fr.md)
- [English](README.en.md)
- [Fiche Nexus Mods](NEXUS_PAGE.md)
