#!/bin/bash
# -------------------------------------------------------------
# Lanceur autonome macOS pour le Simulateur FOMOD v1.0
# -------------------------------------------------------------

# Se positionner dans le dossier du script
cd "$(dirname "$0")" || exit 1

echo "========================================================"
echo "    Démarrage du Simulateur FOMOD v1.0 (macOS)"
echo "========================================================"

# 1. Vérification de Node.js
if ! command -v node &> /dev/null; then
    echo "ERREUR : Node.js n'a pas été détecté sur votre Mac."
    echo "Installez-le rapidement via https://nodejs.org ou avec Homebrew : brew install node"
    echo ""
    read -n 1 -s -r -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# 2. Vérification de la présence du build de production dist/
if [ ! -d "dist" ]; then
    echo "[1/2] Dossier dist/ introuvable. Compilation initiale..."
    npm run build
fi

# 3. Ouverture automatique du navigateur par défaut sur macOS
(sleep 1 && open "http://localhost:3000") &

# 4. Lancement du serveur local autonome (support WASM & offline)
echo "[2/2] Serveur actif sur http://localhost:3000"
echo "Fermez cette fenêtre Terminal pour stopper l'application."
echo "========================================================"
node serve.cjs
