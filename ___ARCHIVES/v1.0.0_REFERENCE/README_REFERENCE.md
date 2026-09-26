# FOMOD Simulator v1.0.0 - Version de Référence

**Date d'archivage :** 2026-09-26 23:35:08  
**Statut :** Version de référence officielle et immuable.

---

## Contenu du livrable de référence

1. **FOMOD Simulator.app** (macOS) :
   - Application native figée (.app bundle).
   - Intègre l'environnement d'exécution Python 3.12, PyQt6 et py7zr.
   - Icône Apple personnalisée en Flat Design sur fond 100% transparent.
   - Signature cryptographique ad-hoc Gatekeeper macOS (Apple Silicon & Intel).

2. **fomod_simulator.pyz** (Multi-plateforme) :
   - Archive exécutable Python ZipApp (PEP 441, taille ~40 Ko).
   - Exécution immédiate sur Windows, macOS et Linux via 'python3 fomod_simulator.pyz' ou './fomod_simulator.pyz'.

3. **fomod_simulator-1.0.0-py2.py3-none-any.whl** (Wheel universel) :
   - Package binaire standard installable via 'pip install <fichier.whl>'.
   - Fournit la commande globale 'fomod-simulator' dans le terminal.

4. **FOMOD_Simulator_Multiplatform.zip** :
   - Distribution complète pour déploiement utilisateur avec lanceurs en 1 clic :
     - Windows : 'run_windows.bat'
     - macOS : 'run_macos.command'
     - Linux : 'run_linux.sh'
     - Dépendances & scripts autonomes inclus.

5. **fomod_simulator_standalone.py** :
   - Script Python unique tout-en-un (sans dépendance modulaire interne).

6. **assets/** :
   - 'icon.icns' (icône multi-résolution 16x16 à 1024x1024 sur fond transparent).
   - 'icon_1024.png' (master transparent haute résolution).

---

## Empreintes SHA-256 de vérification

- **fomod_simulator.pyz :**
  `4dba29b55f002610a2ab0bad6221ca7a2d23e90d704860377931f112158ae676`
- **fomod_simulator-1.0.0-py2.py3-none-any.whl :**
  `3e620f3bb6ad47cb1b751dfee552631e72a972fc6d3193a80979a63322ab3686`
- **FOMOD_Simulator_Multiplatform.zip :**
  `dfb36ac78937104b1efbb5732e4e25a85b2b917cdccb2134fc299053c25f6c9b`
- **fomod_simulator_standalone.py :**
  `ecfcb1726bbe54878303c24eb45187145db42a45ac327148bb55340d8711b314`
