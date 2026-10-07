#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'archivage de la version de référence v1.0.0.
"""

import os
import shutil
import hashlib
import zipfile
import datetime

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
ARCHIVE_BASE = os.path.join(
    PROJECT_DIR,
    "_ARCHIVES" if os.path.isdir(os.path.join(PROJECT_DIR, "_ARCHIVES")) else "___ARCHIVES",
)
REF_DIR = os.path.join(ARCHIVE_BASE, "v1.0.0_REFERENCE")


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 60)
    print("  ARCHIVAGE DE LA VERSION DE RÉFÉRENCE v1.0.0")
    print("=" * 60)

    os.makedirs(REF_DIR, exist_ok=True)

    # 1. Copie de l'application macOS compilée et signée
    app_dest = os.path.join(REF_DIR, "FOMOD Simulator.app")
    app_src = os.path.join(PROJECT_DIR, "FOMOD Simulator.app")
    if not os.path.exists(app_src):
        app_src = os.path.join(PROJECT_DIR, "dist", "FOMOD Simulator.app")
    if os.path.exists(app_src) and app_src != app_dest:
        if os.path.exists(app_dest):
            shutil.rmtree(app_dest)
        shutil.copytree(app_src, app_dest, symlinks=True)
        print("✅ FOMOD Simulator.app copié dans le dossier de référence.")

    # 2. Copie / Résolution des livrables Python
    # 2.1 ZipApp pyz
    pyz_dest = os.path.join(REF_DIR, "fomod_simulator.pyz")
    for cand in [os.path.join(PROJECT_DIR, "dist", "fomod_simulator.pyz"), pyz_dest]:
        if os.path.exists(cand) and cand != pyz_dest:
            shutil.copy(cand, pyz_dest)
            break
    if not os.path.exists(pyz_dest):
        import tempfile
        import zipapp
        standalone_src = "fomod_simulator.py" if os.path.exists(os.path.join(PROJECT_DIR, "fomod_simulator.py")) else "fomod_simulator_standalone.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(PROJECT_DIR, standalone_src), "r", encoding="utf-8") as sf:
                with open(os.path.join(tmpdir, "__main__.py"), "w", encoding="utf-8") as df:
                    df.write(sf.read())
            zipapp.create_archive(tmpdir, pyz_dest, interpreter="/usr/bin/env python3", compressed=True)
            os.chmod(pyz_dest, 0o755)

    # 2.2 Wheel .whl
    whl_dest = os.path.join(REF_DIR, "fomod_simulator-1.0.0-py2.py3-none-any.whl")
    for cand in [
        os.path.join(PROJECT_DIR, "dist", "fomod_simulator-1.0.0-py2.py3-none-any.whl"),
        os.path.join(PROJECT_DIR, "dist", "fomod_simulator-1.0.0-py3-none-any.whl"),
        whl_dest,
    ]:
        if os.path.exists(cand) and cand != whl_dest:
            shutil.copy(cand, whl_dest)
            break

    # 2.3 Archive multi-plateforme
    zip_dest = os.path.join(REF_DIR, "FOMOD_Simulator_Multiplatform.zip")
    for cand in [
        os.path.join(PROJECT_DIR, "dist", "downloads", "FOMOD_Simulator_Multiplatform.zip"),
        os.path.join(PROJECT_DIR, "public", "downloads", "FOMOD_Simulator_Multiplatform.zip"),
        os.path.join(PROJECT_DIR, "dist", "FOMOD_Simulator_Multiplatform.zip"),
        zip_dest,
    ]:
        if os.path.exists(cand) and cand != zip_dest:
            shutil.copy(cand, zip_dest)
            break

    # 2.4 Standalone Python script
    standalone_src = (
        "fomod_simulator.py"
        if os.path.exists(os.path.join(PROJECT_DIR, "fomod_simulator.py"))
        else "fomod_simulator_standalone.py"
    )
    shutil.copy(os.path.join(PROJECT_DIR, standalone_src), os.path.join(REF_DIR, "fomod_simulator.py"))
    print("✅ Livrables Python (pyz, whl, zip, standalone) synchronisés.")

    # 3. Copie des assets
    assets_dest = os.path.join(REF_DIR, "assets")
    if os.path.exists(assets_dest):
        shutil.rmtree(assets_dest)
    shutil.copytree(os.path.join(PROJECT_DIR, "assets"), assets_dest)
    print("✅ Assets d'icône copiés.")

    # 4. Calcul des hash SHA-256
    pyz_hash = sha256_file(os.path.join(REF_DIR, "fomod_simulator.pyz"))
    whl_hash = sha256_file(os.path.join(REF_DIR, "fomod_simulator-1.0.0-py2.py3-none-any.whl"))
    zip_hash = sha256_file(os.path.join(REF_DIR, "FOMOD_Simulator_Multiplatform.zip"))
    standalone_hash = sha256_file(os.path.join(REF_DIR, "fomod_simulator.py"))

    # 5. Création du README_REFERENCE.md
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    readme_content = f"""# FOMOD Simulator v1.0.0 - Version de Référence

**Date d'archivage :** {now_str}  
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

5. **fomod_simulator.py** :
   - Script Python unique tout-en-un (sans dépendance modulaire interne).

6. **assets/** :
   - 'icon.icns' (icône multi-résolution 16x16 à 1024x1024 sur fond transparent).
   - 'icon_1024.png' (master transparent haute résolution).

---

## Empreintes SHA-256 de vérification

- **fomod_simulator.pyz :**
  `{pyz_hash}`
- **fomod_simulator-1.0.0-py2.py3-none-any.whl :**
  `{whl_hash}`
- **FOMOD_Simulator_Multiplatform.zip :**
  `{zip_hash}`
- **fomod_simulator.py :**
  `{standalone_hash}`
"""

    readme_path = os.path.join(REF_DIR, "README_REFERENCE.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("✅ Documentation de référence README_REFERENCE.md créée.")

    # 6. Nettoyage préventif des .DS_Store dans le dossier de référence
    for root, _, files in os.walk(REF_DIR):
        for f in files:
            if f == ".DS_Store":
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass

    # 7. Création de l'archive zip globale de référence
    zip_out = os.path.join(ARCHIVE_BASE, "FOMOD_Simulator_v1.0.0_REFERENCE.zip")
    if os.path.exists(zip_out):
        os.remove(zip_out)

    shutil.make_archive(
        os.path.join(ARCHIVE_BASE, "FOMOD_Simulator_v1.0.0_REFERENCE"),
        "zip",
        root_dir=ARCHIVE_BASE,
        base_dir="v1.0.0_REFERENCE",
    )
    size_mb = os.path.getsize(zip_out) / (1024 * 1024)
    print(f"✅ Archive ZIP de référence créée : {zip_out} ({size_mb:.2f} Mo)")
    print("=" * 60)
    print("🎉 ARCHIVAGE TERMINÉ AVEC SUCCÈS !")
    print("=" * 60)


if __name__ == "__main__":
    main()
