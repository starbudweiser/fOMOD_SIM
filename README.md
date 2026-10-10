# fOMODSIM

Simulateur d'installation de mods FOMOD pour Skyrim (FR/EN/IT/ES).

## Structure du projet

```
fOMOD_SIM/
├── fOMODSIM.app     # application macOS compilée (générée par build_app.sh)
├── build_app.sh            # compilation + signature + nettoyage
├── python_app/             # application Python (PyQt6) modulaire
├── web/                    # version web (React / Vite) : src, public, package.json…
├── dist/                   # build web (généré par npm run build, non versionné)
├── packaging/              # spec PyInstaller
├── scripts/                # lanceurs .command (Python, Web)
├── assets/                 # icônes (icon.icns, icon_1024.png)
├── tests/                  # tests unitaires Python
├── docs/                   # documentation FR/EN, fiche Nexus, captures
└── _ARCHIVES/              # versions de référence (non versionné)
```

## Lancement

- **Application macOS** : `fOMODSIM.app`
- **Python (PyQt6)** : `python3 -m python_app.main` ou `./scripts/run_python.command`
- **Web (React/Vite)** : `cd web && npm install && npm run dev` (ou `./scripts/run_web.command`)

## Build

- Application macOS signée (générée à la racine, temporaires supprimés) : `./build_app.sh`

## Tests

```bash
python3 -m unittest discover tests
cd web && npm run lint
```

## Documentation

- [Français](docs/README.fr.md)
- [English](docs/README.en.md)
- [Linux](docs/LINUX_PORT.md)
- [Fiche Nexus Mods](docs/NEXUS_PAGE.md)
