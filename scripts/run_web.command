#!/bin/bash
# -------------------------------------------------------------
# Lanceur macOS de la version web (React/Vite) du Simulateur FOMOD
# -------------------------------------------------------------

cd "$(dirname "$0")/../web" || exit 1

echo "========================================================"
echo "    Démarrage du Simulateur FOMOD v1.0 (Web, macOS)"
echo "========================================================"

# 1. Vérification de Node.js
if ! command -v node &> /dev/null; then
    echo "ERREUR : Node.js n'a pas été détecté sur votre Mac."
    echo "Installez-le via https://nodejs.org ou Homebrew : brew install node"
    echo ""
    read -n 1 -s -r -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# 2. Dépendances et build de production
if [ ! -d "node_modules" ]; then
    echo "[1/3] Installation des dépendances..."
    npm install
fi
if [ ! -d "dist" ]; then
    echo "[2/3] Compilation initiale..."
    npm run build
fi

# 3. Ouverture du navigateur et serveur local (support WASM & offline)
(sleep 1 && open "http://localhost:3000") &

echo "[3/3] Serveur actif sur http://localhost:3000"
echo "Fermez cette fenêtre Terminal pour stopper l'application."
echo "========================================================"
node serve.cjs
