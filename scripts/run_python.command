#!/bin/bash
# -------------------------------------------------------------
# Lanceur macOS de la version Python (PyQt6) de fOMODSIM
# -------------------------------------------------------------

cd "$(dirname "$0")/.." || exit 1

echo "========================================================"
echo "    Démarrage de fOMODSIM v1.0 (PyQt6 macOS)"
echo "========================================================"

# 1. Vérification de Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERREUR : Python 3 n'a pas été détecté sur votre Mac."
    echo "Téléchargez-le sur https://www.python.org/downloads/ ou via Homebrew : brew install python"
    echo ""
    read -n 1 -s -r -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# 2. Environnement virtuel et dépendances
if [ ! -d ".venv" ]; then
    echo "[1/3] Création de l'environnement virtuel Python..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "[2/3] Vérification des dépendances PyQt6..."
pip install -q -r python_app/requirements.txt

echo "[3/3] Lancement de l'interface graphique native..."
echo "========================================================"
python3 -m python_app.main "$@"
