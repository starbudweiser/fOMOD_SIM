# FOMOD Simulator

Simulateur d'installation de mods FOMOD pour Skyrim (FR/EN/IT/ES).

## Versions

- **Python (PyQt6)** : `python_app/` — lancement : `python3 -m python_app.main` ou `./run_macos_python.command`
- **Script autonome** : `fomod_simulator.py`
- **Web (React/Vite)** : `npm install && npm run dev` (ou `./run-macos.command`)

## Build

- macOS signé : `./build_macos.sh`
- Archive de référence : `python3 archive_reference.py`

## Tests

```bash
python3 -m unittest discover tests
npm run lint
```
