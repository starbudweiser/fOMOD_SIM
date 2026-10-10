/**
 * Traducteur de modding Skyrim & Interface utilisateur FOMOD
 * Fournit une traduction française immédiate pour les options, descriptions,
 * termes Skyrim (meshes, textures, physique, patches) et l'interface.
 */

const SKYRIM_GLOSSARY: Record<string, string> = {
  // Termes communs FOMOD
  'Install': 'Installer',
  'Installation': 'Installation',
  'Select': 'Sélectionner',
  'Choose': 'Choisir',
  'Default': 'Par défaut',
  'Recommended': 'Recommandé',
  'Optional': 'Optionnel',
  'Required': 'Requis',
  'None': 'Aucun',
  'Vanilla': 'Vanilla (Jeu de base)',
  'Textures': 'Textures',
  'Meshes': 'Modèles 3D (Meshes)',
  'Resolution': 'Résolution',
  'Performance': 'Performances',
  'Quality': 'Qualité',
  'High': 'Haute',
  'Medium': 'Moyenne',
  'Low': 'Basse',
  'Compatible': 'Compatible',
  'Incompatible': 'Incompatible',
  'Patch': 'Correctif (Patch)',
  'Patches': 'Correctifs (Patches)',
  'Replacement': 'Remplacement',
  'Replacer': 'Remplaceur',
  'Standalone': 'Autonome (Standalone)',
  'All in one': 'Tout-en-un (AIO)',
  'Physics': 'Physique (HDT-SMP / CBPC)',
  'Body type': 'Type de corps',
  'Body': 'Corps',
  'Armor': 'Armure',
  'Clothing': 'Vêtements',
  'Weapons': 'Armes',
  'Animations': 'Animations',
  'Sound': 'Son / Audio',
  'Lighting': 'Éclairage',
  'Weather': 'Météo',
  'Landscape': 'Paysages',
  'Architecture': 'Architecture',
  'Creatures': 'Créatures',
  'Characters': 'Personnages',
  'Followers': 'Compagnons',
  'Magic': 'Magie',
  'Gameplay': 'Jouabilité (Gameplay)',
  'Interface': 'Interface utilisateur (UI)',
  'Requires': 'Nécessite',
  'Requirements': 'Prérequis',
  'Enabled': 'Activé',
  'Disabled': 'Désactivé',
  'Dark': 'Sombre',
  'Light': 'Clair',
  'Standard': 'Standard',
  'Enhanced': 'Amélioré',
  'Fixes': 'Corrections',
  'Bug fixes': 'Corrections de bugs',
  'Color': 'Couleur',
  'Specular': 'Spéculaire / Reflets',
  'Normal map': 'Normal Map (Relief)',
  'Parallax': 'Parallaxe',
  'Complex Parallax': 'Parallaxe complexe',
  'Glow': 'Luminescence',
  'No glow': 'Sans luminescence',
  'Compatibility patch': 'Patch de compatibilité',
  'Underwear': 'Sous-vêtements',
  'Nude': 'Nu (Sans sous-vêtements)',
  'NeverNude': 'Toujours vêtu (NeverNude)',
  'Options': 'Options',
  'Core': 'Fichiers principaux (Core)',
  'Addon': 'Module complémentaire (Addon)',
  'Outfits': 'Tenues',
};

// Patterns de phrases courantes dans les installeurs de mods
const PHRASE_PATTERNS: [RegExp, string][] = [
  [/Choose which resolution you want/gi, 'Choisissez la résolution souhaitée'],
  [/Choose your preferred option/gi, 'Choisissez votre option préférée'],
  [/Installs the main files for the mod/gi, 'Installe les fichiers principaux du mod'],
  [/Installs the base textures and meshes/gi, 'Installe les textures et modèles de base'],
  [/Recommended for most users/gi, 'Recommandé pour la majorité des joueurs'],
  [/Requires (.*?) to be installed/gi, 'Nécessite que $1 soit installé'],
  [/Compatible with (.*?)/gi, 'Compatible avec $1'],
  [/Select only if you have (.*?)/gi, 'À sélectionner uniquement si vous possédez $1'],
  [/High quality textures with minimal performance impact/gi, 'Textures haute qualité avec un impact minimal sur les performances'],
  [/Best for modern GPUs/gi, 'Idéal pour les cartes graphiques récentes'],
  [/Lower resolution for better performance/gi, 'Résolution réduite pour de meilleures performances'],
  [/Adds physics support/gi, 'Ajoute la prise en charge de la physique (HDT-SMP / CBPC)'],
  [/Replaces the vanilla assets/gi, 'Remplace les éléments graphiques du jeu de base'],
  [/No ESP file required/gi, 'Aucun fichier ESP requis (Pure texture/mesh)'],
  [/Lightweight ESP flagged as ESL/gi, 'Plugin léger tagué ESL (ne compte pas dans la limite des 254 mods)'],
  [/Adds patch for (.*?)/gi, 'Ajoute le patch pour $1'],
  [/Do not select if you do not use (.*?)/gi, 'Ne sélectionnez pas cette option si vous n’utilisez pas $1'],
  [/Select exactly one option/gi, 'Sélectionnez exactement une option'],
  [/Select at least one option/gi, 'Sélectionnez au moins une option'],
  [/Select any number of options/gi, 'Sélectionnez les options de votre choix'],
  [/Select all options/gi, 'Toutes les options sont requises'],
  [/No description available/gi, 'Aucune description fournie'],
  [/Step (\d+) of (\d+)/gi, 'Étape $1 sur $2'],
];

const translationCache = new Map<string, string>();

export function translateText(text: string, enabled: boolean): string {
  if (!enabled || !text || !text.trim()) {
    return text;
  }

  const cached = translationCache.get(text);
  if (cached) return cached;

  let result = text;

  // Remplacement par patterns d'abord
  for (const [regex, repl] of PHRASE_PATTERNS) {
    result = result.replace(regex, repl);
  }

  // Remplacement par termes du glossaire
  for (const [en, fr] of Object.entries(SKYRIM_GLOSSARY)) {
    const regex = new RegExp(`\\b${en}\\b`, 'gi');
    result = result.replace(regex, fr);
  }

  translationCache.set(text, result);
  return result;
}
