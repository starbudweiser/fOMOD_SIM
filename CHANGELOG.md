# Changelog — fOMODSIM

Notes de version / release notes (EN + FR). Translations in IT and ES: see the Nexus Mods page.

## 2.0.0

**English**

- Version number aligned across the Skyrim Mac Toolkit: every app of the kit is now a native Swift app, at version 2.0.0.

**Français**

- Numéro de version commun à tout le Skyrim Mac Toolkit : toutes les applis du kit sont désormais des applis Swift natives, en version 2.0.0.

## 1.3.1

**English**

- The app is now a native macOS (Swift) application, rewritten from the Python version: same behaviour (checked against the previous engine on about a thousand real mod archives), no PyInstaller bundle, so antivirus scanners no longer flag it.
- Archives (ZIP, 7Z, RAR) are read with the macOS system tool `bsdtar`: nothing to install for `.rar` files, and a few archives the old engine could not read now open.
- Your settings carry over; the bundle identifier is unchanged.
- Opening a FOMOD passed to the app at launch (for example with “Open With” in the Finder) works again: the app used to quit instead of loading it.

**Français**

- L'appli est désormais une application macOS native (Swift), réécrite à partir de la version Python : même comportement (vérifié contre l'ancien moteur sur environ un millier d'archives de mods réelles), plus de paquet PyInstaller, donc plus de signalement par les antivirus.
- Les archives (ZIP, 7Z, RAR) sont lues par l'outil système de macOS `bsdtar` : rien à installer pour les `.rar`, et quelques archives que l'ancien moteur ne savait pas lire s'ouvrent maintenant.
- Vos réglages sont conservés ; l'identifiant de l'appli ne change pas.
- Ouvrir un FOMOD passé à l'appli au lancement (par exemple avec « Ouvrir avec » dans le Finder) fonctionne de nouveau : l'appli se fermait au lieu de le charger.

## 1.3.0

**English**

- Signed with a Developer ID and notarized by Apple: macOS now opens the app without a security warning.
- The app's launcher is now compiled from source when the app is built, instead of using PyInstaller's generic prebuilt launcher, which antivirus scanners tend to flag. No change in features.
- New animated splash screen at launch.
- The first letter of the app's name now uses the colour of its logo everywhere it appears.
- Version number aligned across the Skyrim Mac Toolkit.

**Français**

- Signée avec un certificat Developer ID et notarisée par Apple : macOS ouvre désormais l'appli sans avertissement de sécurité.
- Le lanceur de l'appli est maintenant compilé depuis les sources à la construction de l'appli, au lieu du lanceur générique précompilé de PyInstaller, souvent signalé par les antivirus. Aucun changement de fonctionnalités.
- Nouvel écran de lancement animé.
- La première lettre du nom de l'appli prend la couleur de son logo partout où il est écrit.
- Numéro de version commun à tout le Skyrim Mac Toolkit.

<!-- gen_changelogs : entrées ci-dessous conservées -->

## 1.0.0

First public release. / Première version publique.
