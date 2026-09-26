#!/bin/bash
# -------------------------------------------------------------
# Script de compilation autonome pour macOS (PyInstaller)
# Génère une application native figée (.app) sans dépendance Python
# -------------------------------------------------------------

set -e

cd "$(dirname "$0")" || exit 1

echo "=========================================================="
echo "    Compilation native de FOMOD Simulator (.app)"
echo "=========================================================="

# 1. Vérification des prérequis
if ! command -v python3 &> /dev/null; then
    echo "Erreur: python3 est requis pour la compilation."
    exit 1
fi

# 2. Installation de PyInstaller et dépendances
python3 -m pip install --quiet --upgrade pyinstaller py7zr PyQt6

# 3. Compilation via PyInstaller Spec avec cache local
export PYINSTALLER_CONFIG_DIR="$(pwd)/.pyinstaller_cache"
pyinstaller --noconfirm FOMOD_Simulator.spec

# 4. Signature de code ad-hoc pour macOS
echo "Signature de l'application macOS (ad-hoc)..."
xattr -cr "dist/FOMOD Simulator.app"
codesign --force --deep --sign - "dist/FOMOD Simulator.app"
codesign --verify --deep --strict --verbose=1 "dist/FOMOD Simulator.app"

# 5. Nettoyage des fichiers intermédiaires
echo "Nettoyage des fichiers intermédiaires..."
rm -rf build .pyinstaller_cache dist/FOMOD_Simulator

echo "=========================================================="
echo "✅ Compilation et signature terminées avec succès !"
echo "L'application compilée est disponible dans : dist/FOMOD Simulator.app"
echo "Vous pouvez la déplacer directement dans /Applications ou sur votre Bureau."
echo "=========================================================="
