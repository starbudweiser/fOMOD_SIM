# FOMOD Simulator — Documentation (Français)

🇬🇧 [English version](README.en.md) · 🐧 [Portage Linux / Linux port](LINUX_PORT.md)

![Écran d'accueil](images/01_welcome_fr.png)

## 1. Présentation

**FOMOD Simulator** est une application de bureau qui permet d'ouvrir l'archive d'un mod Skyrim contenant un installeur **FOMOD** (`fomod/ModuleConfig.xml`), de parcourir ses étapes d'installation, de tester les conditions logiques, puis de **générer le résultat (« staging ») dans un dossier de votre choix**, sans jamais toucher à votre installation de Skyrim.

Fonctionnalités principales :

- Ouverture de `.zip`, `.7z`, `.rar` ou d'un **dossier décompressé** (glisser-déposer possible).
- Navigation étape par étape, choix uniques ou multiples, options recommandées présélectionnées.
- Évaluation des **conditions et drapeaux (flags)** du FOMOD, fichiers requis et installations conditionnelles.
- Aperçu de la description et des images de chaque option.
- Génération du **staging** (copie des fichiers résultants) vers un dossier de destination.
- Informations du mod (nom, auteur, version) en un clic.
- Interface en **français, anglais, italien et espagnol**.
- Mod de démonstration intégré (CBBE) pour tester sans archive.

## 2. Pourquoi cette application ?

- Les installeurs FOMOD sont normalement exécutés **uniquement depuis un gestionnaire de mods** (Mod Organizer 2, Vortex…), ce qui rend difficile de savoir *ce qui sera réellement installé* avant de s'engager.
- Sous **macOS et Linux**, ces gestionnaires sont absents ou difficiles à installer : il n'existait pas d'outil simple pour exploiter un FOMOD.
- Objectifs : **comprendre** un installeur, **prévisualiser** le résultat, et **préparer** les fichiers de façon sûre et reproductible, sans installation de Skyrim.

## 3. Prérequis

| Version | Prérequis |
|---|---|
| **Application macOS** (`FOMOD Simulator.app`) | macOS sur Apple Silicon (arm64). Aucun Python à installer. |
| **Python (multi-plateforme)** | Python ≥ 3.9, `PyQt6 ≥ 6.4`, `py7zr ≥ 0.20` |
| **Fichiers `.rar`** (optionnel) | `7-Zip`/`p7zip`, `unrar` ou `bsdtar` installé (ex. `brew install p7zip`) |

Skyrim n'a **pas** besoin d'être installé.

## 4. Installation

### macOS (application compilée)

1. Décompressez `FOMOD_Simulator_macOS_arm64.zip` (ou utilisez `FOMOD Simulator.app`).
2. Glissez `FOMOD Simulator.app` dans `/Applications`.
3. Premier lancement : l'application est signée **ad hoc** (non notariée). Si macOS la bloque : **clic droit → Ouvrir → Ouvrir**, ou *Réglages Système → Confidentialité et sécurité → Ouvrir quand même*.

### Python (macOS / Windows / Linux)

```bash
pip install -r python_app/requirements.txt
python3 -m python_app.main
```

## 5. Mode d'emploi

### Étape 1 — Choisir la langue et ouvrir un mod

Sur l'écran d'accueil, choisissez la langue (🇫🇷 🇬🇧 🇮🇹 🇪🇸), puis :

- glissez-déposez une archive, **ou**
- cliquez sur **Charger une archive**, **ou**
- **Charger un dossier décompressé**, **ou**
- **Charger le mod démo CBBE** pour essayer.

### Étape 2 — Parcourir l'installeur

![Options de l'étape 1](images/02_options_fr.png)

- Cliquez sur une option pour afficher sa **description** et son **image** à droite.
- Les options recommandées sont déjà cochées.
- **Continuer** / **Retour** pour naviguer entre les étapes.

![Étape suivante](images/03_step2_fr.png)

### Étape 3 — Générer le staging

1. **Destination du Staging…** : choisissez le dossier de sortie (par défaut : le Bureau).
2. *(Optionnel)* **Dossier Skyrim Data…** : simule la présence de votre dossier `Data`.
3. Cliquez sur **GÉNÉRER LE STAGING** : les fichiers résultant de vos choix sont copiés dans la destination.

### Autres actions

- **Infos du mod** : métadonnées du mod.
- **Fermer le mod** : retour à l'accueil.
- Menu de langue en haut à droite : changement à la volée.

## 6. Dépannage

| Problème | Solution |
|---|---|
| « L'application est endommagée / développeur non identifié » | Clic droit → Ouvrir (signature ad hoc). |
| Impossible d'ouvrir un `.rar` | Installer `p7zip` ou `unrar`. |
| `ModuleNotFoundError: PyQt6` | `pip install -r python_app/requirements.txt`. |
| L'archive n'a pas d'installeur FOMOD | Le mod s'installe sans assistant : copiez-le directement. |

## 7. Compiler soi-même (macOS)

```bash
./build_app.sh     # génère ./FOMOD Simulator.app (signé ad hoc, avec icône)
```
