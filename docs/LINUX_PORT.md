# Portage Linux / Linux Port

🇫🇷 [Documentation FR](README.fr.md) · 🇬🇧 [Documentation EN](README.en.md)

> **Statut / Status** : étude de faisabilité — non testé sur Linux. / Feasibility study — not tested on Linux.

---

## 🇫🇷 Français

### Faisabilité : excellente

Le code est en **Python + PyQt6 + py7zr**, sans API spécifique à macOS (seule la police système `.AppleSystemUIFont` est conditionnée à `sys.platform == "darwin"`). Le portage consiste surtout à **empaqueter** l'application.

### Option 1 — Exécution Python (immédiate)

```bash
sudo apt install python3 python3-pip python3-venv p7zip-full   # Debian/Ubuntu
python3 -m venv venv && . venv/bin/activate
pip install -r python_app/requirements.txt
python3 -m python_app.main
```

Alternative : l'archive `FOMOD_Simulator_Multiplatform.zip` contient `run_linux.sh` (lance `fomod_simulator.pyz`).

Paquets système éventuels pour Qt (Ubuntu/Debian) : `libxcb-cursor0 libxkbcommon-x11-0 libegl1`.

### Option 2 — Binaire autonome (PyInstaller)

À exécuter **sur Linux** (PyInstaller ne fait pas de compilation croisée) :

```bash
pip install pyinstaller py7zr PyQt6
pyinstaller --noconfirm --windowed --name FOMOD_Simulator \
  --add-data "assets/icon_1024.png:assets" python_app/main.py
```

Résultat : `dist/FOMOD_Simulator/` (dossier distribuable). Adapter `packaging/FOMOD_Simulator.spec` en retirant le bloc `BUNDLE` (spécifique macOS).

### Option 3 — AppImage / Flatpak

- **AppImage** : empaqueter `dist/FOMOD_Simulator/` avec `appimagetool` + fichier `.desktop` + `icon_1024.png`.
- **Flatpak** : manifeste avec runtime `org.kde.Platform` + dépendances Python (`PyQt6`, `py7zr`).

### Points d'attention

| Sujet | Détail |
|---|---|
| Polices | Qt utilise la police système ; vérifier le rendu des emojis (`fonts-noto-color-emoji`). |
| Wayland | Si besoin : `QT_QPA_PLATFORM=xcb`. |
| RAR | Installer `unrar` ou `p7zip-full`. |
| Icône | `.png` (1024) pour `.desktop` ; `.icns` inutile sous Linux. |
| Test | `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` en CI. |

### Fichier `.desktop` d'exemple

```ini
[Desktop Entry]
Type=Application
Name=FOMOD Simulator
Exec=/opt/fomod-simulator/FOMOD_Simulator %f
Icon=/opt/fomod-simulator/assets/icon_1024.png
Categories=Utility;Game;
MimeType=application/zip;application/x-7z-compressed;application/vnd.rar;
```

---

## 🇬🇧 English

### Feasibility: excellent

The code is **Python + PyQt6 + py7zr** with no macOS-specific API (only the `.AppleSystemUIFont` system font is guarded by `sys.platform == "darwin"`). Porting is mostly about **packaging**.

### Option 1 — Run from Python (immediate)

```bash
sudo apt install python3 python3-pip python3-venv p7zip-full   # Debian/Ubuntu
python3 -m venv venv && . venv/bin/activate
pip install -r python_app/requirements.txt
python3 -m python_app.main
```

Alternative: `FOMOD_Simulator_Multiplatform.zip` ships `run_linux.sh` (runs `fomod_simulator.pyz`).

Possible Qt system packages (Ubuntu/Debian): `libxcb-cursor0 libxkbcommon-x11-0 libegl1`.

### Option 2 — Standalone binary (PyInstaller)

Run **on Linux** (PyInstaller cannot cross-compile):

```bash
pip install pyinstaller py7zr PyQt6
pyinstaller --noconfirm --windowed --name FOMOD_Simulator \
  --add-data "assets/icon_1024.png:assets" python_app/main.py
```

Output: `dist/FOMOD_Simulator/` (distributable folder). If you reuse `packaging/FOMOD_Simulator.spec`, remove the `BUNDLE` block (macOS-only).

### Option 3 — AppImage / Flatpak

- **AppImage**: package `dist/FOMOD_Simulator/` with `appimagetool` + a `.desktop` file + `icon_1024.png`.
- **Flatpak**: manifest using the `org.kde.Platform` runtime + Python deps (`PyQt6`, `py7zr`).

### Caveats

| Topic | Detail |
|---|---|
| Fonts | Qt uses the system font; check emoji rendering (`fonts-noto-color-emoji`). |
| Wayland | If needed: `QT_QPA_PLATFORM=xcb`. |
| RAR | Install `unrar` or `p7zip-full`. |
| Icon | Use the 1024 `.png` for `.desktop`; `.icns` is not needed on Linux. |
| Testing | `QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests` in CI. |

### Sample `.desktop` file

```ini
[Desktop Entry]
Type=Application
Name=FOMOD Simulator
Exec=/opt/fomod-simulator/FOMOD_Simulator %f
Icon=/opt/fomod-simulator/assets/icon_1024.png
Categories=Utility;Game;
MimeType=application/zip;application/x-7z-compressed;application/vnd.rar;
```
