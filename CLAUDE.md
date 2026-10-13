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
./build_app.sh                            # compile, signe (certificat local) et place l'app à la racine
cd web && npm run dev                     # web sur http://localhost:3000
cd web && npm run lint                    # tsc --noEmit
cd web && npm run build                   # sortie dans ../dist (racine du projet)
```

- Les tests GUI tournent avec `QT_QPA_PLATFORM=offscreen`.
- `npm` vient de Homebrew (`/opt/homebrew/bin`) : il n'est pas dans le PATH de bash, utiliser zsh.

## Structure

- `python_app/fomod/` : moteur — `parser.py` (ModuleConfig.xml), `plugins.py` (scan Data, masters des .esp), `session.py` (déroulé de l'installeur : visibilité, sélections, règles), `staging.py`, `preview.py` (choix de l'image d'aperçu), `extractor.py` (archives, lecture différée), `types.py`, `demo_mod.py`.
- `python_app/gui/` : `main_window.py`, `modals.py`, `mod_info_dialog.py`, `preview_generator.py`, `workers.py` (QThread), `theme.py` (QSS).
- `python_app/locales/` et `web/src/locales/` : un fichier par langue (`fr`, `en`, `es`, `it`).
- `web/src/utils/` : équivalents TypeScript du moteur (`fomodParser.ts`, `fomodSession.ts`, `fomodStaging.ts`, `fomodPreview.ts`, `fomodPlugins.ts`, `archiveExtractor.ts` via libarchive.js en WebAssembly).
- `packaging/fOMODSIM.spec` : PyInstaller, chemins calculés depuis `SPECPATH`.
- `docs/` : README FR/EN, `LINUX_PORT.md`, `NEXUS_PAGE.md`, captures.
- `_ARCHIVES/` : versions de référence (v1.0.0), non versionné. Ne pas y toucher.

## Règles du projet

- **Langue** : français par défaut. Tout texte d'interface passe par les fichiers de langue, dans les 4 langues, des deux côtés (persistance : `QSettings` en Python, `localStorage` en web).
- **Interface** : sombre, flat, sans bordures superflues — l'utilisateur rejette les contours décoratifs. Suivre le design system **Socle** (voir `~/.claude/CLAUDE.md`). Les couleurs Tailwind sont encore écrites en dur dans `web/src/App.tsx` ; les migrer vers les tokens Socle quand on touche à ces zones.
- **Racine propre** : l'utilisateur veut une arborescence rangée en dossiers. Aucun fichier temporaire à la racine ; `build_app.sh` travaille dans `.build_tmp.*` et nettoie tout via `trap EXIT`.
- **Ne jamais supprimer `dist/`** (build web servi par la preview Vite) ni `fOMODSIM.app`, `.venv`, `.vscode`, `Icon?`, `_ARCHIVES/` sans demander.
- **Git** : messages en français, préfixes `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `build:`. Le tag `v1.0.0` est la version de référence.
- **Dépendances** : `PyQt6`, `py7zr` (requis). Optionnels, absents de `requirements.txt` : `Pillow` (images DDS/TGA, BC7 compris ; déclaré dans la spec PyInstaller car importé dynamiquement) et `rarfile` (RAR). Sans `rarfile`, l'extraction RAR se rabat sur les outils système `7z`, `unrar` ou `bsdtar`.

## Points techniques à connaître

- **Session d'installation** (`session.py` / `fomodSession.ts`) : source de vérité des sélections. Une étape n'est visible que si sa condition `<visible>` est vraie avec les flags posés par les options cochées des étapes visibles **précédentes** ; seules les étapes visibles installent et posent des flags. Règles des groupes (ExactlyOne, AtMostOne, AtLeastOne, Any, All) et types d'options (Required verrouillée, NotUsable refusée) appliqués dans `toggle`. Les étapes non touchées par l'utilisateur recalculent leurs choix par défaut après chaque clic. La GUI ne manipule jamais directement les sélections ni les flags.
- **Sémantique FOMOD retenue** (comportement de Mod Organizer 2) : valeur d'un flag = texte de `<flag>` ; attribut `order` appliqué, absent = ordre du document ; destination absente = chemin source, destination vide = racine ; source de dossier vide = racine du mod (hors `fomod/`) ; `alwaysInstall` / `installIfUsable` installés même non cochés ; `gameDependency`, `fommDependency`… supposées vraies ; plugins présents dans Data supposés actifs (`state="Inactive"` donc faux).
- **Recherche de fichiers** : correspondances par suffixe uniquement sur des segments entiers (« mod.esp » ne trouve pas « mymod.esp ») ; un `<folder>` ne copie que le contenu de son propre dossier. `find_image_in_index` tolère une extension d'image différente de celle déclarée (.png annoncé, .jpg fourni).
- **Aperçus** (`preview.py`) : image déclarée si elle est propre à l'option ; sinon image tirée des fichiers que l'option installe (capture, puis texture principale hors cartes techniques `_n`, `_s`…), sinon bannière partagée. Les textures `.dds`/`.tga` hors `fomod/` ne sont **pas** chargées à l'ouverture : `read_entries_bytes` les lit à la demande (une passe par archive, car un 7z « solide » coûte jusqu'à ~5 s par lecture) via `PreviewLoadWorker`, avec un cache de vignettes par chemin.

- **Export du staging** : les fichiers non chargés à l'indexation (textures, meshes : `member` sans `data`) sont lus dans l'archive à l'export, en une passe et en flux (`extract_members_to_dir` ; web : `getBlob`). Un contenu illisible est signalé et le fichier n'est pas créé : jamais de fichier vide (bug du 13/10/2026 : 126 `MainMenu.dds` de 0 octet pour LMMC). RAR : `bsdtar` avant `7z`, le 7-Zip de Homebrew n'ayant pas le décodeur RAR. Écriture dans un `StagingExportWorker`.
- **Dossier par mod** : le staging est écrit dans `<dossier choisi>/<NOM EN MAJUSCULES>` (`staging_folder_name` / `stagingFolderName`) : nom de l'archive nettoyé par `clean_archive_name` / `cleanArchiveName` (formats Nexus ancien `-<id>-<version>-<horodatage>`, récent `<id> <version> AAAA-MM-JJTHH-MMZ <code>`, collections `_<version>_<code>`, copie « (1) » ; validé sur les 16 664 noms du corpus, parité Python/web), sinon nom du mod. Pas le nom du mod d'abord : les variantes d'un même mod (LMMC 16-9 / 16-10 / 21-9) portent le même. Dossier existant non vide : contenu remplacé après confirmation.
- **Parsing FOMOD** : les namespaces XML (`xmlns="…ModConfig5.0.xsd"`) sont retirés de tous les tags avant les recherches. Les images d'options sont cherchées dans de nombreux attributs (`image`, `path`, `file`, `src`…) et sous-balises (`image`, `previewImage`, `headerImage`), sans tenir compte de la casse.
- **Résolution des chemins** : `reanchor_index` réaligne la racine quand `fomod/ModuleConfig.xml` est dans un sous-dossier de l'archive. `find_file_in_index` essaie plusieurs variantes (préfixes `fomod/` et `images/`, suffixe, basename) ; `ArchiveIndex.basename_map` rend la recherche en O(1).
- **Choix de ModuleConfig.xml / info.xml** : `select_fomod_xml` (Python) et `selectFomodXml` (web) privilégient le fichier rangé dans un dossier `fomod/`, puis le moins profond. Les extracteurs ne lisent plus ces XML au fil de l'eau : ils passent tous par cette sélection après le réancrage.
- **Archives 7z** : `py7zr` ≥ 1.0 a supprimé `SevenZipFile.read()`. `_read_7z_members` utilise `extract(factory=BytesIOFactory(...))`, avec repli sur `read()` pour les anciennes versions. Une erreur à cet endroit faisait passer toutes les archives 7z pour « sans ModuleConfig.xml ».
- **Images DDS/TGA** : `QPixmap` ne les lit pas ; repli sur Pillow → RGBA → `QPixmap`.
- **Scan du dossier Data** (`plugins.scan_data_dir` / `fomodPlugins.scanDataDirHandle`) : seuls `.esp`, `.esm`, `.esl`, `.dll`, `.bsa`, `.ba2` comptent ; les dossiers d'assets (`textures`, `meshes`, `sound`…) ne sont pas parcourus. Les 5 masters du jeu de base sont supposés présents.
- **Pré-sélection selon Data** : `annotate_option_masters` lit l'en-tête TES4 (MAST) des plugins de chaque option ; `required_masters` = masters hors jeu de base et hors plugins du mod. Data défini : masters tous présents → option cochée, un manquant → jamais cochée d'office (sauf type Recommended/Required de l'auteur). Dans un choix unique, l'option justifiée par Data passe devant la recommandation générique. Badge « Auto » = `option_matches_installed` (parser), pas `is_option_recommended`. Changer de Data recalcule tous les choix par défaut (les choix manuels sont perdus).
- **Threads** : ne pas utiliser `QThread.terminate()` (interblocages GIL qui figeaient les tests).
- **Polices Qt** : police système `.AppleSystemUIFont` et `'Menlo', monospace` pour éviter les avertissements `qt.qpa.fonts` et ~1,5 s de blocage au démarrage.
- **Signature** : `build_app.sh` appelle `../_tools/sign_app.sh` (certificat local stable « sKYCRASH Local Signing », jamais ad hoc, sinon macOS redemande les autorisations à chaque build). Pas de notarisation : sur un autre Mac, clic droit → Ouvrir.

## Historique (repris d'Antigravity, sept.–oct. 2026)

- Moteur FOMOD et interface 3 colonnes (barre latérale, étapes, aperçu) ; overlay de glisser-déposer et fenêtre de chargement avec spinner, reproduits d'après des maquettes fournies par l'utilisateur.
- Correction de l'affichage des images de preview (namespaces, variantes de balises, DDS, réancrage).
- Suppression systématique des contours dans le thème Qt (« borderless »), fond de l'aperçu de droite retiré.
- Correction d'un crash `SIGABRT` à la génération du staging (`VirtualFileEntry.is_dir` manquant).
- Internationalisation FR/EN/IT/ES des deux versions ; sélecteur de langue en pastilles compactes centrées sur l'accueil, sans icône ni libellé.
- Icône : colis isométrique flat design sur fond transparent (`assets/icon.png`, `assets/icon.icns`).
- v1.0.0 archivée et taguée ; puis audits, suppression du code mort (`standalone/`, `setup.py`, scripts ponctuels, dépendances npm inutilisées), réorganisation en dossiers, docs FR/EN et fiche Nexus.

## Pistes ouvertes

- **Aperçus web** : `fomodPreview.ts` reprend `preview.py` mais ignore les textures `.dds`/`.tga` (illisibles par le navigateur) ; une option sans autre image retombe sur la bannière ou le visuel généré.

- `npm audit` signalait 1 vulnérabilité haute non examinée.
- La fiche Nexus (`docs/NEXUS_PAGE.md`) est en Markdown : Nexus attend du BBCode, et les champs auteur et licence sont à compléter.
- Portage Linux documenté mais jamais testé.
- `docs/images` contient des captures IT/ES inutilisées.
