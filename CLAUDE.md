# fOMODSIM

Simulateur d'installateurs FOMOD pour Skyrim SE/AE sur macOS : on ouvre une archive de mod (ZIP, 7Z, RAR ou dossier), on parcourt ses étapes d'installation, on teste les conditions et les flags, puis on génère un staging (la liste des fichiers qui seraient installés), sans jamais toucher au jeu. Distribué sur Nexus Mods.

Deux implémentations du même produit, à garder en parité fonctionnelle et visuelle :
- **`python_app/`** — application desktop PyQt6, compilée en `fOMODSIM.app`. C'est la version livrée.
- **`web/`** — version React 19 + Vite + Tailwind v4 (prévisualisation, démo).

Toute évolution d'interface ou de moteur se fait **dans les deux versions** sauf mention contraire.

## Commandes

```bash
python3 -m unittest discover tests        # tests Python (moteur + GUI hors écran)
python3 -m python_app.main                # lancer la version desktop
./build_app.sh                            # compile, signe ad hoc et place l'app à la racine
cd web && npm run dev                     # web sur http://localhost:3000
cd web && npm run lint                    # tsc --noEmit
cd web && npm run build                   # sortie dans ../dist (racine du projet)
```

- Les tests GUI tournent avec `QT_QPA_PLATFORM=offscreen`.
- `npm` vient de Homebrew (`/opt/homebrew/bin`) : il n'est pas dans le PATH de bash, utiliser zsh.

## Structure

- `python_app/fomod/` : moteur — `parser.py` (ModuleConfig.xml), `extractor.py` (archives), `staging.py`, `types.py`, `demo_mod.py`.
- `python_app/gui/` : `main_window.py`, `modals.py`, `mod_info_dialog.py`, `preview_generator.py`, `workers.py` (QThread), `theme.py` (QSS).
- `python_app/locales/` et `web/src/locales/` : un fichier par langue (`fr`, `en`, `es`, `it`).
- `web/src/utils/` : équivalents TypeScript du moteur (`fomodParser.ts`, `fomodStaging.ts`, `archiveExtractor.ts` via libarchive.js en WebAssembly).
- `packaging/fOMODSIM.spec` : PyInstaller, chemins calculés depuis `SPECPATH`.
- `docs/` : README FR/EN, `LINUX_PORT.md`, `NEXUS_PAGE.md`, captures.
- `_ARCHIVES/` : versions de référence (v1.0.0), non versionné. Ne pas y toucher.

## Règles du projet

- **Langue** : français par défaut. Tout texte d'interface passe par les fichiers de langue, dans les 4 langues, des deux côtés (persistance : `QSettings` en Python, `localStorage` en web).
- **Interface** : sombre, flat, sans bordures superflues — l'utilisateur rejette les contours décoratifs. Suivre le design system **Socle** (voir `~/.claude/CLAUDE.md`). Les couleurs Tailwind sont encore écrites en dur dans `web/src/App.tsx` ; les migrer vers les tokens Socle quand on touche à ces zones.
- **Racine propre** : l'utilisateur veut une arborescence rangée en dossiers. Aucun fichier temporaire à la racine ; `build_app.sh` travaille dans `.build_tmp.*` et nettoie tout via `trap EXIT`.
- **Ne jamais supprimer `dist/`** (build web servi par la preview Vite) ni `fOMODSIM.app`, `.venv`, `.vscode`, `Icon?`, `_ARCHIVES/` sans demander.
- **Git** : messages en français, préfixes `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `build:`. Le tag `v1.0.0` est la version de référence.
- **Dépendances** : `PyQt6`, `py7zr` (requis). Optionnels, absents de `requirements.txt` : `Pillow` (images DDS/TGA, chargé via `importlib`) et `rarfile` (RAR). Sans `rarfile`, l'extraction RAR se rabat sur les outils système `7z`, `unrar` ou `bsdtar`.

## Points techniques à connaître

- **Parsing FOMOD** : les namespaces XML (`xmlns="…ModConfig5.0.xsd"`) sont retirés de tous les tags avant les recherches. Les images d'options sont cherchées dans de nombreux attributs (`image`, `path`, `file`, `src`…) et sous-balises (`image`, `previewImage`, `headerImage`), sans tenir compte de la casse.
- **Résolution des chemins** : `reanchor_index` réaligne la racine quand `fomod/ModuleConfig.xml` est dans un sous-dossier de l'archive. `find_file_in_index` essaie plusieurs variantes (préfixes `fomod/` et `images/`, suffixe, basename) ; `ArchiveIndex.basename_map` rend la recherche en O(1).
- **Images DDS/TGA** : `QPixmap` ne les lit pas ; repli sur Pillow → RGBA → `QPixmap`.
- **Scan du dossier Data** : seuls `.esp`, `.esm`, `.esl`, `.dll`, `.bsa`, `.ba2` comptent pour la détection des dépendances (badge « Auto »).
- **Threads** : ne pas utiliser `QThread.terminate()` (interblocages GIL qui figeaient les tests).
- **Polices Qt** : police système `.AppleSystemUIFont` et `'Menlo', monospace` pour éviter les avertissements `qt.qpa.fonts` et ~1,5 s de blocage au démarrage.
- **Signature** : ad hoc uniquement, pas de notarisation. Sur un autre Mac : clic droit → Ouvrir. `build_app.sh` retire les attributs étendus (`xattr`) avant de signer.

## Historique (repris d'Antigravity, sept.–oct. 2026)

- Moteur FOMOD et interface 3 colonnes (barre latérale, étapes, aperçu) ; overlay de glisser-déposer et fenêtre de chargement avec spinner, reproduits d'après des maquettes fournies par l'utilisateur.
- Correction de l'affichage des images de preview (namespaces, variantes de balises, DDS, réancrage).
- Suppression systématique des contours dans le thème Qt (« borderless »), fond de l'aperçu de droite retiré.
- Correction d'un crash `SIGABRT` à la génération du staging (`VirtualFileEntry.is_dir` manquant).
- Internationalisation FR/EN/IT/ES des deux versions ; sélecteur de langue en pastilles compactes centrées sur l'accueil, sans icône ni libellé.
- Icône : colis isométrique flat design sur fond transparent (`assets/icon_1024.png`, `assets/icon.icns`).
- v1.0.0 archivée et taguée ; puis audits, suppression du code mort (`standalone/`, `setup.py`, scripts ponctuels, dépendances npm inutilisées), réorganisation en dossiers, docs FR/EN et fiche Nexus.

## Pistes ouvertes

- `npm audit` signalait 1 vulnérabilité haute non examinée.
- La fiche Nexus (`docs/NEXUS_PAGE.md`) est en Markdown : Nexus attend du BBCode, et les champs auteur et licence sont à compléter.
- Portage Linux documenté mais jamais testé.
- `docs/images` contient des captures IT/ES inutilisées.
