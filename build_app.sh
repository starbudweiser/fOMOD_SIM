#!/bin/bash
# -------------------------------------------------------------
# Compilation macOS de FOMOD Simulator (PyInstaller)
# Produit "FOMOD Simulator.app" (signée ad hoc, icône incluse)
# directement à la racine du projet.
# Tous les fichiers/dossiers temporaires sont supprimés en fin
# de script (succès ou échec).
# -------------------------------------------------------------

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="FOMOD Simulator.app"
SPEC="$ROOT/packaging/FOMOD_Simulator.spec"
TARGET="$ROOT/$APP_NAME"

cd "$ROOT"

# Dossier temporaire sur le même volume que le projet (déplacement atomique)
TMP_DIR="$(mktemp -d "$ROOT/.build_tmp.XXXXXX")"

cleanup() {
    rm -rf "$TMP_DIR" "$ROOT/build" "$ROOT/.pyinstaller_cache" "$ROOT"/*.egg-info
    find "$ROOT" \( -path "$ROOT/.venv" -o -path "$ROOT/web/node_modules" -o -path "$ROOT/.git" \) -prune -o \
        \( -name "__pycache__" -type d -o -name ".DS_Store" -type f \) -print0 2>/dev/null \
        | xargs -0 rm -rf 2>/dev/null || true
}
trap cleanup EXIT

echo "=========================================================="
echo "    Compilation native de FOMOD Simulator (.app)"
echo "=========================================================="

# 1. Prérequis
if ! command -v python3 &> /dev/null; then
    echo "Erreur : python3 est requis pour la compilation." >&2
    exit 1
fi
for f in "$SPEC" "$ROOT/assets/icon.icns" "$ROOT/assets/icon_1024.png" "$ROOT/python_app/main.py"; do
    if [ ! -f "$f" ]; then
        echo "Erreur : fichier requis introuvable : $f" >&2
        exit 1
    fi
done

# 2. Dépendances de build
python3 -m pip install --quiet --upgrade pyinstaller py7zr PyQt6

# 3. Compilation (tout est généré dans le dossier temporaire)
export PYINSTALLER_CONFIG_DIR="$TMP_DIR/config"
python3 -m PyInstaller --noconfirm --clean \
    --distpath "$TMP_DIR/dist" \
    --workpath "$TMP_DIR/work" \
    "$SPEC"

BUILT_APP="$TMP_DIR/dist/$APP_NAME"
if [ ! -d "$BUILT_APP" ]; then
    echo "Erreur : l'application n'a pas été générée." >&2
    exit 1
fi

# 4. Signature ad hoc + vérification
echo "Signature de l'application macOS (ad hoc)..."
xattr -cr "$BUILT_APP"
codesign --force --deep --sign - "$BUILT_APP"
codesign --verify --deep --strict --verbose=1 "$BUILT_APP"

# 5. Livraison à la racine du projet
rm -rf "$TARGET"
mv "$BUILT_APP" "$TARGET"

# 6. Nettoyage (également garanti par le trap EXIT)
echo "Nettoyage des fichiers temporaires..."
cleanup
trap - EXIT

echo "=========================================================="
echo "✅ Compilation et signature terminées avec succès !"
echo "Application : $TARGET"
echo "=========================================================="
