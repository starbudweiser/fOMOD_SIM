# FOMOD Simulator — Documentation (English)

🇫🇷 [Version française](README.fr.md) · 🐧 [Linux port / Portage Linux](LINUX_PORT.md)

![Welcome screen](images/01_welcome_en.png)

## 1. Overview

**FOMOD Simulator** is a desktop application that opens a Skyrim mod archive containing a **FOMOD** installer (`fomod/ModuleConfig.xml`), lets you walk through its installation steps, tests its logical conditions, and then **generates the result ("staging") in a folder of your choice**, without ever touching your Skyrim installation.

Key features:

- Opens `.zip`, `.7z`, `.rar` or an **unpacked folder** (drag & drop supported).
- Step-by-step navigation, single/multiple choice, recommended options pre-selected.
- Evaluation of FOMOD **conditions and flags**, required files and conditional installs.
- Description and image preview for every option.
- **Staging** generation (copy of the resulting files) to a destination folder.
- Mod information (name, author, version) in one click.
- UI in **French, English, Italian and Spanish**.
- Built-in demo mod (CBBE) to try the app without any archive.

## 2. Why this application?

- FOMOD installers normally run **only inside a mod manager** (Mod Organizer 2, Vortex…), making it hard to know *what will really be installed* before committing.
- On **macOS and Linux** those managers are missing or hard to set up: no simple tool existed to work with a FOMOD.
- Goals: **understand** an installer, **preview** its outcome, and **prepare** files in a safe, reproducible way, with no Skyrim install required.

## 3. Requirements

| Edition | Requirements |
|---|---|
| **macOS app** (`FOMOD Simulator.app`) | macOS on Apple Silicon (arm64). No Python needed. |
| **Python (cross-platform)** | Python ≥ 3.9, `PyQt6 ≥ 6.4`, `py7zr ≥ 0.20` |
| **`.rar` files** (optional) | `7-Zip`/`p7zip`, `unrar` or `bsdtar` installed (e.g. `brew install p7zip`) |

Skyrim does **not** need to be installed.

## 4. Installation

### macOS (compiled app)

1. Unzip `FOMOD_Simulator_macOS_arm64.zip` (or use `FOMOD Simulator.app`).
2. Drag `FOMOD Simulator.app` into `/Applications`.
3. First launch: the app is **ad-hoc signed** (not notarized). If macOS blocks it: **right-click → Open → Open**, or *System Settings → Privacy & Security → Open Anyway*.

### Python (macOS / Windows / Linux)

```bash
pip install -r python_app/requirements.txt
python3 -m python_app.main          # modular version
python3 fomod_simulator.py          # standalone script
```

## 5. User guide

### Step 1 — Pick a language and open a mod

On the welcome screen choose your language (🇫🇷 🇬🇧 🇮🇹 🇪🇸), then:

- drag & drop an archive, **or**
- click **Load an archive**, **or**
- **Load an unpacked folder**, **or**
- **Load the CBBE demo mod** to try it out.

### Step 2 — Walk through the installer

![Step 1 options](images/02_options_en.png)

- Click an option to see its **description** and **image** on the right.
- Recommended options are already ticked.
- Use **Continue** / **Back** to move between steps.

![Next step](images/03_step2_en.png)

### Step 3 — Generate the staging

1. **Staging destination…**: pick the output folder (default: Desktop).
2. *(Optional)* **Skyrim Data folder…**: simulates your `Data` folder.
3. Click **GENERATE STAGING**: the files resulting from your choices are copied to the destination.

### Other actions

- **Mod info**: mod metadata.
- **Close mod**: back to the welcome screen.
- Language menu (top right): switch on the fly.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| "App is damaged / unidentified developer" | Right-click → Open (ad-hoc signature). |
| Cannot open a `.rar` | Install `p7zip` or `unrar`. |
| `ModuleNotFoundError: PyQt6` | `pip install -r python_app/requirements.txt`. |
| Archive has no FOMOD installer | The mod has no wizard: copy it directly. |

## 7. Build it yourself (macOS)

```bash
./build_macos.sh     # produces dist/FOMOD Simulator.app (ad-hoc signed, with icon)
```
