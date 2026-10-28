# Étude : ce que le moteur FOMOD officiel (Nexus) peut apporter à fOMOD_SIM

Source étudiée : `github.com/Nexus-Mods/fomod-installer` (C#, GPL-3.0). C'est le moteur utilisé par Vortex, compilé en NativeAOT (`ModInstaller.Native`) pour Windows et Linux x64. Comparaison faite avec `python_app/fomod/` (environ 2 700 lignes).

## Verdict

**Ne pas remplacer notre moteur, mais l'aligner sur l'officiel et réutiliser ses données de test.**
- Notre moteur Python couvre déjà l'essentiel : les étapes visibles, les flags, les types d'option, l'ordre `Explicit/Ascending/Descending`, `alwaysInstall` et `installIfUsable`, les dépendances de fichier.
- Embarquer le moteur C# (dylib NativeAOT osx-arm64 appelée par ctypes) ajouterait une chaîne de build .NET pour un gain limité. Ce gain se résume aux scripts C# et aux vieux formats CPL et OMOD, qui sont rares.
- Pas de copie de code : fOMOD_SIM est sous MIT et le moteur sous GPL-3.0. On réimplémente le **comportement**, ce qui est permis, sans recopier les sources.

## 1. Écarts de comportement à corriger (priorité haute)

Ces écarts font que l'aperçu de fOMOD_SIM peut différer de ce que Vortex installe réellement.

| # | Cas | Moteur officiel (`XmlScriptInstaller.cs`) | fOMOD_SIM (`staging.py`) | Correctif |
|---|---|---|---|---|
| 1 | **Priorité des `requiredInstallFiles`** | priorité − 10⁹ : ils perdent toujours face aux autres fichiers | priorité brute | soustraire un grand décalage |
| 2 | **Priorité des `conditionalFileInstalls`** | priorité + 10⁹ : ils gagnent toujours, quelle que soit la priorité des options | priorité brute (une option `priority="5"` bat un conditionnel `priority="0"`) | ajouter un grand décalage |
| 3 | **Égalité de priorité** | le fichier dont le **chemin source est le plus grand** (`CompareTo`, ordre ordinal) gagne, quel que soit l'ordre de traitement | le dernier traité écrase le précédent | départager par `source` (comparaison ordinale) |
| 4 | Destination d'un `<file>` | `destination` est le **chemin complet du fichier** ; une destination vide donne le nom du fichier à la racine | heuristique : la destination est traitée comme un dossier si elle n'a pas d'extension | garder l'heuristique (plus tolérante) mais **signaler** dans le journal quand elle s'écarte du comportement officiel |

Points vérifiés et **déjà conformes** :
- ordre par défaut `Explicit` quand l'attribut `order` est absent (le XSD dit `Ascending`, mais le moteur officiel et le nôtre suivent l'ordre du document) ;
- `alwaysInstall`, et `installIfUsable` sauf si l'option est `NotUsable` ;
- les flags d'une option retirés quand on la décoche ;
- seules les étapes visibles comptent.

## 2. Corpus de tests réutilisable (gain le plus fort)

Dans le dépôt officiel, `test/TestData/` contient :
- `FomodComplianceTests.zip` (47 fichiers, cas de conformité ciblés), `InvisibleStepTest.zip`, `CSharpTestCase.zip` ;
- de vraies archives : Skyrim (`Spell Perk Item Distributor`, `XP32 Maximum Skeleton Special Extended`), Fallout 4 et Fallout NV ;
- les **résultats attendus** en JSON (`Shared/fallout4.json`, `falloutnv.json`, `csharp-script.json`) : choix, puis liste exacte des instructions `copy` avec leur priorité.

Idée : un `tests/test_conformite_officielle.py` qui télécharge ce corpus (sans le committer : licences des mods et GPL), rejoue chaque cas dans notre moteur et compare la liste des fichiers finaux. Cela sert de filet de sécurité pour les correctifs du §1.

## 3. Fonctions à reprendre (priorité moyenne)

- **Préréglages (presets)** : le moteur officiel accepte un jeu de choix pré-rempli, celui que les collections Vortex enregistrent dans `choices`. fOMOD_SIM pourrait **exporter et importer ses choix au format Vortex** pour rejouer une installation de collection ou partager une configuration.
- **Conditions de version** (`gameDependency`, `fommDependency`, `foseDependency`) : l'officiel compare des versions, et une version illisible vaut `0.0.0.0`. Nous les supposons satisfaites. On pourrait ajouter un réglage « version du jeu / de SKSE » (ex. SE 1.5.97 ou AE 1.6.x), utile pour les FOMOD qui choisissent les DLL SKSE selon la version.
- **Messages d'erreur** : l'officiel avertit quand une source est absente de l'archive, ou quand un `<file>` pointe vers un dossier. Les reprendre dans notre journal.

## 4. À ne pas reprendre

- **Scripts C#** (`CSharpScript`) et formats **CPL / OMOD** (`AntlrUtil`) : rares sur Skyrim SE, demandent un runtime .NET, et l'exécution de code fourni par l'archive pose un problème de sécurité.
- Le moteur natif comme dépendance d'exécution, sauf si un jour mORTEX le compile pour osx-arm64. fOMOD_SIM pourrait alors l'utiliser comme **oracle de test** (comparer les deux moteurs sur la même archive), jamais comme moteur principal.

## Ordre proposé

1. Ajouter les tests de conformité (§2), qui échoueront au début.
2. Corriger les écarts 1 à 3 de `staging.py`, puis les mêmes dans `web/src/utils/fomodStaging.ts` (version web).
3. Ajouter l'export et l'import des choix au format Vortex, et le réglage de version du jeu.

Effort estimé : 1 à 2 jours pour 1 et 2, 1 à 2 jours pour 3.
