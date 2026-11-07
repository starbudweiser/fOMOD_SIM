# fOMODSIM

Simulateur d'installateurs FOMOD pour Skyrim SE/AE sur macOS : on ouvre une archive de mod (ZIP, 7Z, RAR ou dossier), on parcourt ses étapes d'installation, on teste les conditions et les flags, puis on génère un staging (la liste des fichiers qui seraient installés), sans jamais toucher au jeu. Distribué sur Nexus Mods.

Deux implémentations du même produit, à garder en parité fonctionnelle et visuelle :
- **`macos/`** — application Swift (SwiftUI, design Socle), compilée en `fOMODSIM.app`. C'est la version livrée. Elle remplace l'ancienne version Python/PyQt6 (retirée en novembre 2026 : les applis PyInstaller partaient en quarantaine sur Nexus).
- **`web/`** — version React 19 + Vite + Tailwind v4 (prévisualisation, démo).

Toute évolution d'interface ou de moteur se fait **dans les deux versions** sauf mention contraire.

## Commandes

```bash
cd macos && swift test                    # tests du moteur (62)
./build_app.sh                            # traductions, tests, compilation, signature (Developer ID) : fOMODSIM.app à la racine
../_tools/build_all.sh fOMOD_SIM          # idem, puis installe dans ~/Applications/Skyrim Tools
cd web && npm run dev                     # web sur http://localhost:3000
cd web && npm run lint                    # tsc --noEmit
cd web && npm run build                   # sortie dans ../dist (racine du projet)
```

- `npm` vient de Homebrew (`/opt/homebrew/bin`) : il n'est pas dans le PATH de bash, utiliser zsh.
- Essais sans fenêtre au premier plan : `SPLASH_QUIET=1 FOMODSIM_NOUPDATE=1 FOMODSIM_SUITE=<domaine jetable>` avec `FOMODSIM_RUN` (étapes : `demo`, `open:<chemin>`, `next`, `prev`, `pick:<étape>.<groupe>.<option>`, `data:<dossier>`, `stage:<dossier>`, `info`, `dataSheet`, `openSheet`, `about`, `preview`, `lang:<code>`), `FOMODSIM_SNAPSHOT=<png>`, `FOMODSIM_DELAY`, `FOMODSIM_DUMP=<fichier>`, `FOMODSIM_SPLASH_SHOTS=<préfixe>` (voir `scripted()` dans `main.swift`). `FOMODSIM_SUITE` isole les réglages : sans lui, `lang:` écrirait dans les préférences réelles.

## Structure

- `macos/Sources/FomodCore/` : moteur sans interface — `Parser.swift` (ModuleConfig.xml, recherche de fichiers), `XMLTree.swift` (arbre XML à la ElementTree), `Session.swift` (déroulé de l'installeur), `Staging.swift` (staging, export, nom du dossier), `Plugins.swift` (scan Data, masters des .esp), `Preview.swift` (image d'aperçu), `Extractor.swift` (dossier, archives, lecture différée), `Archive.swift` (bsdtar), `Types.swift`, `DemoMod.swift`, `PyCompat.swift`/`PyPath.swift` (fonctions à la Python : `strip`, `lower`, dict ordonné, chemins), `I18n.swift`, `Settings.swift`, `Strings.swift` (généré).
- `macos/Sources/fOMODSIM/` : interface — `AppModel.swift` (état et actions), `ContentView.swift` (en-tête, accueil, 3 colonnes), `Sheets.swift` (modales), `ImageSupport.swift`, `About.swift`, `main.swift` (menus, splash, essais) ; `Socle.swift`, `SplashScreen.swift`, `Updater*.swift`, `WindowPresent.swift` sont des copies de modèles communs (Socle est resynchronisé par `sync_apps.sh`).
- `macos/Sources/fomod-parity/` : sortie JSON complète d'une analyse (arbre, déroulé, staging, export) pour comparer à une autre implémentation. Les scripts de comparaison avec l'ancien Python sont dans les notes de session (`fOMODSIM_parite/` : `parity_py.py` demande l'ancien code, `git show 0009bf6:python_app/…`).
- `i18n/strings.json` ({texte français: [en, it, es]}) et `i18n/ids.json` ({identifiant: texte français}) : source unique des textes de l'appli ; `macos/gen_strings.py` en tire `Strings.swift` (lancé par `build_app.sh`). `T("section.clé")` cherche par identifiant, `L("texte français")` par texte. La version web garde ses propres fichiers (`web/src/locales/`).
- `web/src/utils/` : équivalents TypeScript du moteur (`fomodParser.ts`, `fomodSession.ts`, `fomodStaging.ts`, `fomodPreview.ts`, `fomodPlugins.ts`, `archiveExtractor.ts` via libarchive.js en WebAssembly).
- `docs/` : README FR/EN, `NEXUS_PAGE.md`, captures.
- `_ARCHIVES/` : versions de référence (v1.0.0), non versionné. Ne pas y toucher.

## Règles du projet

- **Langue** : français par défaut. Tout texte d'interface passe par `i18n/` (4 langues) côté Swift et par les fichiers de langue côté web. Langue du Mac par défaut (anglais sinon), menu « Langue » ; réglage `language` de `UserDefaults` (domaine `com.skyrimtools.fomodsimulator`, le même que l'ancien QSettings : repris tel quel).
- **Interface** : sombre, flat, sans bordures superflues — l'utilisateur rejette les contours décoratifs. Design system **Socle** (voir `~/.claude/CLAUDE.md`) ; « f » de fOMODSIM dans le bleu du logo (#1677dc), pas de couleur dans les menus. Les couleurs Tailwind sont encore écrites en dur dans `web/src/App.tsx` ; les migrer vers les tokens Socle quand on touche à ces zones.
- **Racine propre** : l'utilisateur veut une arborescence rangée en dossiers. Aucun fichier temporaire à la racine.
- **Ne jamais supprimer `dist/`** (build web servi par la preview Vite) ni `fOMODSIM.app`, `.venv`, `.vscode`, `Icon?`, `_ARCHIVES/` sans demander.
- **Git** : messages en français, préfixes `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `build:`. Le tag `v1.0.0` est la version de référence. `ETAT.md` (note de travail) n'est jamais committé.
- **Dépendances** : aucune à embarquer côté Swift (Foundation, SwiftUI, ImageIO, `/usr/bin/bsdtar`). Identifiant de paquet `com.skyrimtools.fomodsimulator` (inchangé : macOS garde les autorisations), signature `../_tools/sign_app.sh` (Developer ID).
- **Sécurité** : l'appli ne touche jamais au jeu ; archives de mods et dossier Data en lecture seule ; extractions dans des dossiers temporaires jetables ; les chemins d'archive ou de FOMOD avec `..` ou absolus sont ramenés dans le dossier de sortie.

## Points techniques à connaître

- **Session d'installation** (`Session.swift` / `fomodSession.ts`) : source de vérité des sélections. Une étape n'est visible que si sa condition `<visible>` est vraie avec les flags posés par les options cochées des étapes visibles **précédentes** ; seules les étapes visibles installent et posent des flags. Règles des groupes (ExactlyOne, AtMostOne, AtLeastOne, Any, All) et types d'options (Required verrouillée, NotUsable refusée) appliqués dans `toggle`. Les étapes non touchées par l'utilisateur recalculent leurs choix par défaut après chaque clic. L'interface ne manipule jamais directement les sélections ni les flags.
- **Sémantique FOMOD retenue** (comportement de Mod Organizer 2) : valeur d'un flag = texte de `<flag>` ; attribut `order` appliqué, absent = ordre du document ; destination absente = chemin source, destination vide = racine ; source de dossier vide = racine du mod (hors `fomod/`) ; `alwaysInstall` / `installIfUsable` installés même non cochés ; `gameDependency`, `fommDependency`… supposées vraies ; plugins présents dans Data supposés actifs (`state="Inactive"` donc faux).
- **Recherche de fichiers** : correspondances par suffixe uniquement sur des segments entiers (« mod.esp » ne trouve pas « mymod.esp ») ; un `<folder>` ne copie que le contenu de son propre dossier. `findImageInIndex` tolère une extension d'image différente de celle déclarée (.png annoncé, .jpg fourni).
- **Aperçus** (`Preview.swift`) : image déclarée si elle est propre à l'option ; sinon image tirée des fichiers que l'option installe (capture, puis texture principale hors cartes techniques `_n`, `_s`…), sinon bannière partagée. Les textures `.dds`/`.tga` hors `fomod/` ne sont **pas** chargées à l'ouverture : `readEntriesBytes` les lit à la demande (une passe par archive, car un 7z « solide » coûte cher) en arrière-plan (`AppModel.prefetchPreviews`), avec un cache d'images par chemin. ImageIO décode PNG, JPEG, BMP, WebP, GIF, DDS (BC7 compris) et TGA.
- **Export du staging** : les fichiers non chargés à l'indexation (textures, meshes : `member` sans `data`) sont lus dans l'archive à l'export, en une passe (`extractMembersToDir`). Un contenu illisible est signalé et le fichier n'est pas créé : jamais de fichier vide (bug du 13/10/2026 : 126 `MainMenu.dds` de 0 octet pour LMMC). Écriture en arrière-plan.
- **Dossier par mod** : le staging est écrit dans `<dossier choisi>/<NOM EN MAJUSCULES>` (`stagingFolderName`) : nom de l'archive nettoyé par `cleanArchiveName` (formats Nexus ancien `-<id>-<version>-<horodatage>`, récent `<id> <version> AAAA-MM-JJTHH-MMZ <code>`, collections `_<version>_<code>`, copie « (1) » ; validé sur les 16 664 noms du corpus), sinon nom du mod. Pas le nom du mod d'abord : les variantes d'un même mod (LMMC 16-9 / 16-10 / 21-9) portent le même. Dossier existant non vide : contenu remplacé après confirmation.
- **Parsing FOMOD** : `XMLParser` de Foundation, enveloppé par `XMLTree.swift` (texte avant le premier enfant, ordre du document, espaces de noms retirés). Avant l'analyse : BOM, déclaration `<?xml encoding?>` retirée, caractères de contrôle retirés, esperluettes nues échappées, et U+FEFF remplacés par un caractère d'usage privé puis rétablis (Foundation les supprime au milieu des textes, Python les gardait). Les images d'options sont cherchées dans de nombreux attributs et sous-balises, sans tenir compte de la casse. Texte XML décodé par `decodeXMLText` (UTF-8 avec/sans BOM, UTF-16 avec ou sans BOM, Latin-1).
- **Résolution des chemins** : `reanchorIndex` réaligne la racine quand `fomod/ModuleConfig.xml` est dans un sous-dossier de l'archive. `findFileInIndex` essaie plusieurs variantes (préfixes `fomod/` et `images/`, suffixe, basename) ; `ArchiveIndex.basenameMap` rend la recherche en O(1). `selectFomodXML` privilégie le fichier rangé dans un dossier `fomod/`, puis le moins profond.
- **Archives = `/usr/bin/bsdtar`** (libarchive 3.7 : ZIP, 7Z, RAR4/RAR5, TAR) : liste par `-tvf`, lecture des fichiers « essentiels » (XML FOMOD, images légères, plugins, INI, textes) en une passe par extraction vers un dossier jetable (`-T` liste de noms). Pièges rencontrés : les noms à `* ? [ \` sont des motifs pour bsdtar (échappés par `escapePattern`) ; sur macOS libarchive affiche les noms en NFD (convertis en NFC pour les chemins du moteur, le nom d'origine sert à extraire) ; les noms de ZIP sans indicateur UTF-8 ni champ Unicode s'affichent en octets échappés (`\202`) et sont relus avec `--options hdrcharset=CP437` (ne pas l'appliquer partout : il ignore le champ Unicode des ZIP) ; un membre que bsdtar ne décompresse pas (ZIP deflate64, filtre RAR VM, dictionnaire RAR5 trop grand) laisse un fichier vide ou faux, détecté par la sortie d'erreur (`nom: raison`). L'ordre des entrées est celui de l'archive.
- **Threads** : extraction, export et lecture des aperçus tournent dans des `Task.detached` ; les objets du moteur passent d'une tâche à l'autre dans une `Box` (un seul fil les lit à la fois). Une génération (`loadGeneration`) écarte les résultats d'une ouverture périmée.
- **Quitter avec une feuille ouverte** : `NSApp.terminate` reste sans effet tant qu'une feuille SwiftUI est attachée ; le menu « Quitter » ferme d'abord les feuilles (`quit`).
- **Mise à jour automatique** : `Updater.swift` (dépôt `fOMOD_SIM`, une requête par jour), jamais pendant une extraction ou un export (`canInstall`).
- **Signature** : `build_app.sh` appelle `../_tools/sign_app.sh` (certificat Developer ID, jamais ad hoc, sinon macOS redemande les autorisations à chaque build).

## Parité avec l'ancienne version Python

Comparaison automatique Swift/Python (JSON complet : arbre analysé, déroulé des étapes pour 3 + 3 à 4 scénarios dont des clics tirés au hasard à graine fixe, staging avec hachage des octets, aperçus choisis, types d'options, export réel) sur 962 archives réelles du corpus Vortex (ZIP, 7Z, RAR, de quelques Ko à 1,6 Go) : identique, sauf là où Python se trompait (ZIP/7Z/RAR que `py7zr` ou l'extraction RAR de l'ancien code lisait mal ou à moitié ; 4 archives sur 962). Différences voulues : `.rar` listé en entier sans l'extraire (ordre de l'archive), erreur explicite pour une archive illisible au lieu de « ModuleConfig.xml introuvable », chemins de destination FOMOD confinés au dossier de staging.

## Historique (repris d'Antigravity, sept.–oct. 2026 ; Swift en nov. 2026)

- Moteur FOMOD et interface 3 colonnes (barre latérale, étapes, aperçu) ; overlay de glisser-déposer et fenêtre de chargement avec spinner, reproduits d'après des maquettes fournies par l'utilisateur.
- Correction de l'affichage des images de preview (namespaces, variantes de balises, DDS, réancrage).
- Suppression systématique des contours (« borderless »).
- Internationalisation FR/EN/IT/ES des deux versions ; menu « Langue ».
- Icône : colis isométrique flat design sur fond transparent (`assets/icon.png`, `assets/icon.icns`).
- v1.0.0 archivée et taguée ; puis audits, suppression du code mort, réorganisation en dossiers, docs FR/EN et fiche Nexus.
- 7 novembre 2026 : conversion en Swift (cœur `FomodCore` + 62 tests, `fomod-parity`, interface SwiftUI Socle, splash, À propos, mise à jour), retrait du Python.

## Pistes ouvertes

- **Aperçus web** : `fomodPreview.ts` reprend `Preview.swift` mais ignore les textures `.dds`/`.tga` (illisibles par le navigateur) ; une option sans autre image retombe sur la bannière ou le visuel généré.
- `npm audit` signalait 1 vulnérabilité haute non examinée.
- La fiche Nexus (`docs/NEXUS_PAGE.md`) est en Markdown : Nexus attend du BBCode, et les champs auteur et licence sont à compléter. Rien n'est publié sur Nexus tant que le support n'a pas répondu.
- `docs/images` contient des captures IT/ES inutilisées.
- `_tools/sync_shared.sh` cite encore `fOMOD_SIM/python_app` (ignoré : « absent ») ; à retirer des listes `UPDATER` et `LANG_MENU`.
