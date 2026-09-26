#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de compilation et d'empaquetage multi-plateforme du Simulateur FOMOD.
Génère :
1. dist/fomod_simulator.pyz (Archive exécutable Python ZipApp PEP 441)
2. dist/fomod_simulator-1.0.0-py2.py3-none-any.whl (Package universel Wheel)
3. dist/FOMOD_Simulator_Multiplatform.zip (Archive autonome complète avec lanceurs Windows/macOS/Linux)
"""

import os
import sys
import shutil
import zipfile
import zipapp
import subprocess

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
DOWNLOADS_DIR = os.path.join(DIST_DIR, "downloads")
PUBLIC_DOWNLOADS_DIR = os.path.join(PROJECT_DIR, "public", "downloads")


def step_print(step: str, title: str):
    print(f"\n[{step}] {title}")
    print("-" * 60)


def build_zipapp():
    step_print("1/4", "Compilation du ZipApp exécutable (fomod_simulator.pyz)")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copie le script autonome en point d'entrée universel __main__.py
        standalone_path = os.path.join(PROJECT_DIR, "fomod_simulator_standalone.py")
        with open(standalone_path, "r", encoding="utf-8") as f:
            code = f.read()

        entry_point = os.path.join(tmpdir, "__main__.py")
        with open(entry_point, "w", encoding="utf-8") as f:
            f.write(code)

        out_pyz = os.path.join(DIST_DIR, "fomod_simulator.pyz")
        os.makedirs(DIST_DIR, exist_ok=True)
        if os.path.exists(out_pyz):
            os.remove(out_pyz)

        zipapp.create_archive(
            tmpdir,
            out_pyz,
            interpreter="/usr/bin/env python3",
            compressed=True,
        )
        os.chmod(out_pyz, 0o755)
        size_kb = os.path.getsize(out_pyz) / 1024
        print(f"✅ ZipApp généré avec succès : dist/fomod_simulator.pyz ({size_kb:.1f} Ko)")


def build_wheel():
    step_print("2/4", "Compilation du package Wheel universel (.whl)")
    subprocess.run(
        [sys.executable, "setup.py", "bdist_wheel", "--universal", "--dist-dir", "dist"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
    )
    print("✅ Package Wheel généré dans dist/")


def create_launchers(bundle_dir: str):
    # Windows Launcher
    win_bat = os.path.join(bundle_dir, "run_windows.bat")
    with open(win_bat, "w", encoding="utf-8") as f:
        f.write("""@echo off
title FOMOD Simulator - Skyrim Modding Tool
cd /d "%~dp0"
echo ========================================================
echo    Lancement du Simulateur FOMOD v1.0 (Windows)
echo ========================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo ERREUR : Python 3 n'a pas ete detecte sur votre systeme.
        echo Telechargez-le sur https://www.python.org/
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

echo Verification des dependances (PyQt6, py7zr)...
%PY_CMD% -m pip install -q --upgrade PyQt6 py7zr

echo Demarrage du Simulateur...
if exist fomod_simulator.pyz (
    %PY_CMD% fomod_simulator.pyz %*
) else (
    %PY_CMD% fomod_simulator_standalone.py %*
)
""")

    # macOS Launcher
    mac_cmd = os.path.join(bundle_dir, "run_macos.command")
    with open(mac_cmd, "w", encoding="utf-8") as f:
        f.write("""#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "========================================================"
echo "    Lancement du Simulateur FOMOD v1.0 (macOS)"
echo "========================================================"
if ! command -v python3 &> /dev/null; then
    echo "ERREUR : Python 3 n'a pas été détecté sur votre Mac."
    echo "Téléchargez-le sur https://www.python.org/ ou via : brew install python"
    read -n 1 -s -r -p "Appuyez sur une touche pour quitter..."
    exit 1
fi
python3 -m pip install -q --upgrade PyQt6 py7zr
if [ -f "fomod_simulator.pyz" ]; then
    python3 fomod_simulator.pyz "$@"
else
    python3 fomod_simulator_standalone.py "$@"
fi
""")
    os.chmod(mac_cmd, 0o755)

    # Linux Launcher
    linux_sh = os.path.join(bundle_dir, "run_linux.sh")
    with open(linux_sh, "w", encoding="utf-8") as f:
        f.write("""#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "========================================================"
echo "    Lancement du Simulateur FOMOD v1.0 (Linux)"
echo "========================================================"
if ! command -v python3 &> /dev/null; then
    echo "ERREUR : Python 3 n'a pas été détecté sur votre système."
    echo "Installez-le via : sudo apt install python3 python3-pip (Debian/Ubuntu) ou équivalent."
    exit 1
fi
python3 -m pip install -q --upgrade PyQt6 py7zr
if [ -f "fomod_simulator.pyz" ]; then
    python3 fomod_simulator.pyz "$@"
else
    python3 fomod_simulator_standalone.py "$@"
fi
""")
    os.chmod(linux_sh, 0o755)

    # Readme
    readme_path = os.path.join(bundle_dir, "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""================================================================================
           SIMULATEUR FOMOD v1.0 - ÉDITION MULTI-PLATEFORME
================================================================================
Cette archive est universelle et fonctionne sous Windows, macOS et Linux.

LANCEMENT RAPIDE :
------------------
- WINDOWS : Double-cliquez sur 'run_windows.bat'
- macOS   : Double-cliquez sur 'run_macos.command'
- LINUX   : Exécutez './run_linux.sh' ou 'python3 fomod_simulator.pyz'

LANCEMENT EN LIGNE DE COMMANDE (TOUT OS) :
------------------------------------------
1. Installer les prérequis :
   pip install -r requirements.txt

2. Lancer l'application compilée :
   python3 fomod_simulator.pyz
   (ou 'python fomod_simulator.pyz' sous Windows)

CONTENU DE L'ARCHIVE :
----------------------
- fomod_simulator.pyz           : Exécutable Python autonome compressé (ZipApp PEP 441)
- fomod_simulator_standalone.py : Script Python autonome tout-en-un
- run_windows.bat               : Lanceur automatisé pour Windows
- run_macos.command             : Lanceur automatisé pour macOS
- run_linux.sh                  : Lanceur automatisé pour Linux
- requirements.txt              : Liste des dépendances (PyQt6, py7zr)
- assets/                       : Icônes et logos de l'application
================================================================================
""")


def build_multiplatform_archive():
    step_print("3/4", "Création de l'archive ZIP multi-plateforme complète")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_name = "FOMOD_Simulator_Multiplatform"
        bundle_dir = os.path.join(tmpdir, bundle_name)
        os.makedirs(bundle_dir, exist_ok=True)

        # 1. Copie du ZipApp
        shutil.copy(os.path.join(DIST_DIR, "fomod_simulator.pyz"), bundle_dir)

        # 2. Copie du script autonome
        shutil.copy(os.path.join(PROJECT_DIR, "fomod_simulator_standalone.py"), bundle_dir)

        # 3. Copie requirements.txt
        shutil.copy(os.path.join(PROJECT_DIR, "python_app", "requirements.txt"), bundle_dir)

        # 4. Copie des assets
        assets_dest = os.path.join(bundle_dir, "assets")
        if os.path.exists(os.path.join(PROJECT_DIR, "assets")):
            shutil.copytree(os.path.join(PROJECT_DIR, "assets"), assets_dest)

        # 5. Création des lanceurs
        create_launchers(bundle_dir)

        # 6. Création du zip
        out_zip = os.path.join(DIST_DIR, f"{bundle_name}.zip")
        if os.path.exists(out_zip):
            os.remove(out_zip)

        shutil.make_archive(
            os.path.join(DIST_DIR, bundle_name),
            "zip",
            root_dir=tmpdir,
            base_dir=bundle_name,
        )

        # Synchronisation dans les dossiers downloads
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(PUBLIC_DOWNLOADS_DIR, exist_ok=True)
        shutil.copy(out_zip, DOWNLOADS_DIR)
        shutil.copy(out_zip, PUBLIC_DOWNLOADS_DIR)

        size_mb = os.path.getsize(out_zip) / (1024 * 1024)
        print(f"✅ Archive multi-plateforme créée : dist/{bundle_name}.zip ({size_mb:.2f} Mo)")


def clean_intermediates():
    step_print("4/4", "Nettoyage des fichiers intermédiaires de compilation")
    for d in ["build", "fomod_simulator.egg-info"]:
        p = os.path.join(PROJECT_DIR, d)
        if os.path.exists(p):
            shutil.rmtree(p)
            print(f"Dossier supprimé : {d}/")
    print("✅ Nettoyage terminé.")


def main():
    print("=" * 60)
    print("  COMPILATION DU SIMULATEUR FOMOD - MULTI-PLATEFORME")
    print("=" * 60)
    build_zipapp()
    build_wheel()
    build_multiplatform_archive()
    clean_intermediates()
    print("\n" + "=" * 60)
    print("🎉 COMPILATION MULTI-PLATEFORME TERMINÉE AVEC SUCCÈS !")
    print("Livrables générés :")
    print("  1. dist/fomod_simulator.pyz")
    print("  2. dist/fomod_simulator-1.0.0-py2.py3-none-any.whl")
    print("  3. dist/FOMOD_Simulator_Multiplatform.zip")
    print("=" * 60)


if __name__ == "__main__":
    main()
