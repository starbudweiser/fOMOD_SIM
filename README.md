# FOMOD Simulator

Simulateur d'installation de mods FOMOD pour Skyrim (FR/EN/IT/ES).

## Structure du projet

```
FOMOD_SIM/
├── FOMOD Simulator.app     # application macOS compilée (générée par scripts/build_app.sh)
├── python_app/             # application Python (PyQt6) modulaire
├── standalone/             # version Python tout-en-un (fomod_simulator.py)
├── web/                    # version web (React / Vite) : src, public, package.json…
├── packaging/              # spec PyInstaller
├── scripts/                # build_app.sh, archive_reference.py, lanceurs .command
├── assets/                 # icônes (icon.icns, icon_1024.png)
├── tests/                  # tests unitaires Python
├── docs/                   # documentation FR/EN, fiche Nexus, captures
├── setup.py                # packaging pip (wheel)
└── _ARCHIVES/              # versions de référence (non versionné)
```

## Lancement

- **Application macOS** : `FOMOD Simulator.app`
- **Python (PyQt6)** : `python3 -m python_app.main` ou `./scripts/run_python.command`
- **Script autonome** : `python3 standalone/fomod_simulator.py`
- **Web (React/Vite)** : `cd web && npm install && npm run dev` (ou `./scripts/run_web.command`)

## Build

- Application macOS signée (générée à la racine, temporaires supprimés) : `./scripts/build_app.sh`
- Archive de référence : `python3 scripts/archive_reference.py`

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
