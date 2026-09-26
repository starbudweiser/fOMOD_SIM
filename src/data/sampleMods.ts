import { ArchiveIndex, VirtualFileEntry } from '../types/fomod';

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function createSvgPlaceholder(
  title: string,
  subtitle: string,
  bgColor: string = '#1e293b',
  accentColor: string = '#38bdf8'
): string {
  const safeTitle = escapeXml(title || 'Option du mod');
  const safeSubtitle = escapeXml(subtitle || 'Option de configuration du mod');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">
    <defs>
      <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${bgColor}" />
        <stop offset="100%" stop-color="#111111" />
      </linearGradient>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
      </pattern>
    </defs>
    <rect width="640" height="400" fill="url(#g)"/>
    <rect width="640" height="400" fill="url(#grid)"/>
    <circle cx="320" cy="160" r="70" fill="none" stroke="${accentColor}" stroke-width="3" opacity="0.6"/>
    <path d="M 280 160 L 320 120 L 360 160 L 320 200 Z" fill="${accentColor}" opacity="0.8"/>
    <text x="320" y="270" fill="#ffffff" font-family="'Segoe UI', Arial, sans-serif" font-size="22" font-weight="bold" text-anchor="middle">${safeTitle}</text>
    <text x="320" y="305" fill="#aaaaaa" font-family="'Segoe UI', Arial, sans-serif" font-size="14" text-anchor="middle">${safeSubtitle}</text>
    <rect x="20" y="20" width="120" height="28" rx="4" fill="rgba(0,0,0,0.6)"/>
    <text x="80" y="39" fill="${accentColor}" font-family="'Segoe UI', Arial, sans-serif" font-size="12" font-weight="bold" text-anchor="middle">FOMOD PREVIEW</text>
  </svg>`;
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

export interface SampleMod {
  id: string;
  name: string;
  author: string;
  version: string;
  filename: string;
  description: string;
  moduleConfigXml: string;
  infoXml: string;
  images: Record<string, string>;
}

export const SAMPLE_MOD_CBBE: SampleMod = {
  id: 'cbbe-se',
  name: "Caliente's Beautiful Bodies Enhancer - CBBE - SE",
  author: 'Caliente & Ousnius',
  version: '2.0.3',
  filename: 'Calientes_Beautiful_Bodies_Enhancer_v2.0.3.zip',
  description:
    'A complete female body replacer with high-polygon meshes and high-resolution textures. Includes BodySlide support and advanced physics integration.',
  infoXml: `<?xml version="1.0" encoding="utf-8"?>
<fomod>
  <Name>Caliente's Beautiful Bodies Enhancer - CBBE - SE</Name>
  <Author>Caliente and Ousnius</Author>
  <Version>2.0.3</Version>
  <Website>https://www.nexusmods.com/skyrimspecialedition/mods/198</Website>
  <Description>Caliente's Beautiful Bodies Enhancer (CBBE) is a complete female body mesh and texture overhaul for The Elder Scrolls V: Skyrim Special Edition.
Features realistic anatomy, smooth vertices, seamless neck joints, and comprehensive clothing and armor support. Compatible with HDT-SMP, CBPC, and BodySlide and Outfit Studio.</Description>
</fomod>`,
  images: {
    'fomod/images/curvy.png': createSvgPlaceholder('CBBE Curvy Body', 'Default voluptuous silhouette with smooth curves', '#1e293b', '#38bdf8'),
    'fomod/images/slim.png': createSvgPlaceholder('CBBE Slim Body', 'Athletic and slender proportions for female characters', '#1e293b', '#38bdf8'),
    'fomod/images/vanilla.png': createSvgPlaceholder('CBBE Vanilla Shape', 'Faithful to original Skyrim proportions', '#1e293b', '#38bdf8'),
    'fomod/images/tex4k.png': createSvgPlaceholder('4K Ultra Textures', 'Ultra HD skin pores, specular maps and normal detail', '#312e81', '#a855f7'),
    'fomod/images/tex2k.png': createSvgPlaceholder('2K High Textures', 'Balanced fidelity with excellent VRAM performance', '#312e81', '#a855f7'),
    'fomod/images/physics.png': createSvgPlaceholder('HDT-SMP / CBPC Physics', 'Real-time soft body physics simulation enabled', '#14532d', '#4ade80'),
    'fomod/images/static.png': createSvgPlaceholder('Static Body (No Physics)', 'Maximum FPS, zero performance impact', '#14532d', '#4ade80'),
    'fomod/images/underwear.png': createSvgPlaceholder('Underwear Version', 'Includes discrete lore-friendly underwear meshes', '#7c2d12', '#fb923c'),
    'fomod/images/nevernude.png': createSvgPlaceholder('NeverNude Safe Version', 'Includes permanent modesty cloth for safe streaming', '#7c2d12', '#fb923c'),
    'fomod/images/skyui_patch.png': createSvgPlaceholder('SkyUI SE Integration', 'Custom icons and inventory management tags', '#0f172a', '#fbbf24'),
    'fomod/images/racemenu_patch.png': createSvgPlaceholder('RaceMenu Overlays', 'High poly body morph sliders and tattoo overlays', '#0f172a', '#fbbf24'),
  },
  moduleConfigXml: `<?xml version="1.0" encoding="utf-8"?>
<moduleConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>Caliente's Beautiful Bodies Enhancer - CBBE - SE</moduleName>
  <requiredInstallFiles>
    <folder source="00 Core" destination="." priority="0"/>
  </requiredInstallFiles>
  <installSteps order="Explicit">
    <installStep name="Silhouette &amp; Version du corps">
      <optionalFileGroups order="Explicit">
        <group name="Type de corps principal" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="CBBE Curvy (Recommandé)">
              <description>The standard voluptuous body shape. Best for users looking for feminine curves and full compatibility with existing armor conversions. Recommended for most players.</description>
              <image path="fomod/images/curvy.png"/>
              <files>
                <folder source="01 Curvy/meshes" destination="meshes" priority="1"/>
              </files>
              <typeDescriptor>
                <type name="Recommended"/>
              </typeDescriptor>
            </plugin>
            <plugin name="CBBE Slim">
              <description>A more slender, athletic physique with reduced proportions. Maintains smooth topology and accurate rigging.</description>
              <image path="fomod/images/slim.png"/>
              <files>
                <folder source="01 Slim/meshes" destination="meshes" priority="1"/>
              </files>
              <typeDescriptor>
                <type name="Optional"/>
              </typeDescriptor>
            </plugin>
            <plugin name="CBBE Vanilla Shape">
              <description>Body proportions matched closely to original Bethesda Skyrim models while retaining the high vertex count and seamless seams of CBBE.</description>
              <image path="fomod/images/vanilla.png"/>
              <files>
                <folder source="01 Vanilla/meshes" destination="meshes" priority="1"/>
              </files>
              <typeDescriptor>
                <type name="Optional"/>
              </typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Résolution des Textures">
      <optionalFileGroups order="Explicit">
        <group name="Pack de textures de peau" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Textures 4K Ultra HD (Haute Qualité)">
              <description>Ultra-high definition diffuse, subsurface scattering, normal maps and specular maps (4096x4096). Recommended for GPUs with 6GB+ VRAM.</description>
              <image path="fomod/images/tex4k.png"/>
              <files>
                <folder source="02 Textures 4K/textures" destination="textures" priority="2"/>
              </files>
              <typeDescriptor>
                <type name="Recommended"/>
              </typeDescriptor>
            </plugin>
            <plugin name="Textures 2K Haute Performance">
              <description>High quality 2048x2048 textures. Sharp details with minimal performance impact and reduced memory footprint. Ideal for heavy mod setups.</description>
              <image path="fomod/images/tex2k.png"/>
              <files>
                <folder source="02 Textures 2K/textures" destination="textures" priority="2"/>
              </files>
              <typeDescriptor>
                <type name="Optional"/>
              </typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Moteur Physique &amp; Animation">
      <optionalFileGroups order="Explicit">
        <group name="Prise en charge de la physique" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Physique HDT-SMP / CBPC">
              <description>Enables dynamic physics weighting for breast, butt, and belly motion in real-time. Requires HDT-SMP or CBPC plugins in your Skyrim installation.</description>
              <image path="fomod/images/physics.png"/>
              <files>
                <folder source="03 Physics/meshes" destination="meshes" priority="3"/>
                <file source="03 Physics/CBBE_Physics.esp" destination="CBBE_Physics.esp" priority="3"/>
              </files>
              <dependencies operator="Or">
                <fileDependency file="CBPC.dll" state="Active"/>
                <fileDependency file="hdtSMP64.dll" state="Active"/>
              </dependencies>
            </plugin>
            <plugin name="Corps Statique (Sans Physique)">
              <description>Zero performance impact. Standard static skin weights with no physics calculation needed. Completely crash-proof and lightweight.</description>
              <image path="fomod/images/static.png"/>
              <files>
                <folder source="03 Static/meshes" destination="meshes" priority="3"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Options de Sous-vêtements &amp; Pudeur">
      <optionalFileGroups order="Explicit">
        <group name="Style de tenue par défaut" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Version Sous-vêtements (Underwear)">
              <description>Characters wear discrete lore-friendly underwear when unequipped. Safe for everyday play.</description>
              <image path="fomod/images/underwear.png"/>
              <files>
                <folder source="04 Underwear/meshes" destination="meshes" priority="4"/>
                <folder source="04 Underwear/textures" destination="textures" priority="4"/>
              </files>
            </plugin>
            <plugin name="Version NeverNude (Streaming Safe)">
              <description>Permanent cloth coverage applied directly to the body mesh. Fully Twitch/YouTube compliant.</description>
              <image path="fomod/images/nevernude.png"/>
              <files>
                <folder source="04 NeverNude/meshes" destination="meshes" priority="4"/>
                <folder source="04 NeverNude/textures" destination="textures" priority="4"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Patches de Compatibilité">
      <optionalFileGroups order="Explicit">
        <group name="Modules additionnels" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="Patch d'intégration SkyUI SE">
              <description>Adds inventory icons and category filters tailored for body items. Automatically preselected when SkyUI_SE.esp is detected in Data.</description>
              <image path="fomod/images/skyui_patch.png"/>
              <files>
                <file source="05 Patches/CBBE_SkyUI_Addon.esp" destination="CBBE_SkyUI_Addon.esp" priority="5"/>
              </files>
              <dependencies operator="And">
                <fileDependency file="SkyUI_SE.esp" state="Active"/>
              </dependencies>
            </plugin>
            <plugin name="Support des Sliders RaceMenu (skee64)">
              <description>Installs body morph sliders, overlay textures and bodypaint slots into RaceMenu character generation menu.</description>
              <image path="fomod/images/racemenu_patch.png"/>
              <files>
                <folder source="05 RaceMenu/SKSE" destination="SKSE" priority="5"/>
                <file source="05 RaceMenu/CBBE_RaceMenu_Morphs.esp" destination="CBBE_RaceMenu_Morphs.esp" priority="5"/>
              </files>
              <dependencies operator="And">
                <fileDependency file="skee64.dll" state="Active"/>
              </dependencies>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</moduleConfiguration>`,
};

export function buildSampleArchiveIndex(mod: SampleMod): ArchiveIndex {
  const files = new Map<string, VirtualFileEntry>();
  const dirs = new Map<string, string>();

  // Add info.xml
  const infoBlob = new Blob([mod.infoXml], { type: 'application/xml' });
  files.set('fomod/info.xml', { path: 'fomod/info.xml', isDir: false, size: infoBlob.size, blob: infoBlob });
  dirs.set('fomod', 'fomod');

  // Add ModuleConfig.xml
  const cfgBlob = new Blob([mod.moduleConfigXml], { type: 'application/xml' });
  files.set('fomod/moduleconfig.xml', { path: 'fomod/ModuleConfig.xml', isDir: false, size: cfgBlob.size, blob: cfgBlob });

  // Add images
  for (const [imgPath, dataUrl] of Object.entries(mod.images)) {
    const key = imgPath.toLowerCase();
    files.set(key, { path: imgPath, isDir: false, size: 24500, url: dataUrl });
    const dir = imgPath.substring(0, imgPath.lastIndexOf('/'));
    if (dir) dirs.set(dir.toLowerCase(), dir);
  }

  // Add simulated mod files and folders
  const dummyFiles = [
    '00 Core/meshes/actors/character/character assets/femalehead.nif',
    '00 Core/textures/actors/character/female/femalehead.dds',
    '01 Curvy/meshes/actors/character/character assets/femalebody_0.nif',
    '01 Curvy/meshes/actors/character/character assets/femalebody_1.nif',
    '01 Slim/meshes/actors/character/character assets/femalebody_0.nif',
    '01 Slim/meshes/actors/character/character assets/femalebody_1.nif',
    '01 Vanilla/meshes/actors/character/character assets/femalebody_0.nif',
    '01 Vanilla/meshes/actors/character/character assets/femalebody_1.nif',
    '02 Textures 4K/textures/actors/character/female/femalebody_4k.dds',
    '02 Textures 4K/textures/actors/character/female/femalebody_msn.dds',
    '02 Textures 2K/textures/actors/character/female/femalebody_2k.dds',
    '02 Textures 2K/textures/actors/character/female/femalebody_msn.dds',
    '03 Physics/meshes/actors/character/character assets/femalebody_physics.nif',
    '03 Physics/CBBE_Physics.esp',
    '03 Static/meshes/actors/character/character assets/femalebody_static.nif',
    '04 Underwear/meshes/actors/character/character assets/femaleunderwear.nif',
    '04 Underwear/textures/actors/character/female/underwear.dds',
    '04 NeverNude/meshes/actors/character/character assets/nevernude.nif',
    '04 NeverNude/textures/actors/character/female/nevernude.dds',
    '05 Patches/CBBE_SkyUI_Addon.esp',
    '05 RaceMenu/SKSE/Plugins/CharGen/Overlays.ini',
    '05 RaceMenu/CBBE_RaceMenu_Morphs.esp',
  ];

  for (const fpath of dummyFiles) {
    const key = fpath.toLowerCase();
    const isEsp = fpath.endsWith('.esp');
    const sz = isEsp ? 14200 : 854000;
    files.set(key, { path: fpath, isDir: false, size: sz });

    // Track parent folders
    const parts = fpath.split('/');
    let cur = '';
    for (let i = 0; i < parts.length - 1; i++) {
      cur = cur ? `${cur}/${parts[i]}` : parts[i];
      dirs.set(cur.toLowerCase(), cur);
    }
  }

  return { files, dirs };
}

export const SAMPLE_MOD_SMIM: SampleMod = {
  id: 'smim-se',
  name: 'Static Mesh Improvement Mod - SMIM',
  author: 'Brumbek',
  version: '2.08',
  filename: 'Static_Mesh_Improvement_Mod_v2.08.zip',
  description:
    'A massive project to greatly improve the appearance of countless static 3D models in Skyrim. Fixes seams, adds smooth 3D geometry to chains, ropes, fences, lanterns, barrels, and architectural assets.',
  infoXml: `<?xml version="1.0" encoding="utf-8"?>
<fomod>
  <Name>Static Mesh Improvement Mod - SMIM</Name>
  <Author>Brumbek</Author>
  <Version>2.08</Version>
  <Website>https://www.nexusmods.com/skyrimspecialedition/mods/659</Website>
  <Description>Static Mesh Improvement Mod (SMIM) is an essential mod dedicated to eliminating low-poly ugliness across thousands of objects in Skyrim. Everything from rope bridges and 3D chains to furniture and food meshes are remade with high fidelity geometry.</Description>
</fomod>`,
  images: {
    'fomod/images/smim_core.png': createSvgPlaceholder('SMIM Core Meshes', 'High-poly 3D barrels, furniture, clutter and ropes', '#1e293b', '#eab308'),
    'fomod/images/smim_chains.png': createSvgPlaceholder('3D Animated Chains', 'True 3D rounded chain links for dungeons and chandeliers', '#1e293b', '#eab308'),
    'fomod/images/smim_lanterns.png': createSvgPlaceholder('Refined Lanterns & Lights', 'Realistic glass reflection and metallic candleholders', '#312e81', '#f59e0b'),
    'fomod/images/smim_elfx.png': createSvgPlaceholder('ELFX Lighting Compatibility Patch', 'Ensures accurate light bulb placement with Enhanced Lights and FX', '#0f172a', '#38bdf8'),
  },
  moduleConfigXml: `<?xml version="1.0" encoding="utf-8"?>
<moduleConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>Static Mesh Improvement Mod - SMIM</moduleName>
  <requiredInstallFiles>
    <folder source="00 Core" destination="." priority="0"/>
  </requiredInstallFiles>
  <installSteps order="Explicit">
    <installStep name="Éléments Principaux SMIM">
      <optionalFileGroups order="Explicit">
        <group name="Pack d'éléments essentiels" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="SMIM Tout-en-un (Recommandé)">
              <description>Installs all core high polygon 3D mesh replacements including barrels, tables, chairs, ropes, signs, and farm clutter. Recommended for all users.</description>
              <image path="fomod/images/smim_core.png"/>
              <files>
                <folder source="01 All In One/meshes" destination="meshes" priority="1"/>
                <folder source="01 All In One/textures" destination="textures" priority="1"/>
                <file source="01 All In One/SMIM-SE-Merged.esp" destination="SMIM-SE-Merged.esp" priority="1"/>
              </files>
              <typeDescriptor>
                <type name="Recommended"/>
              </typeDescriptor>
            </plugin>
            <plugin name="SMIM Version Légère (Performance)">
              <description>Optimized meshes for lower-end machines. Keeps essential architectural fixes while skipping high-density clutter items.</description>
              <image path="fomod/images/smim_core.png"/>
              <files>
                <folder source="01 Lite/meshes" destination="meshes" priority="1"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Chaînes et Lanternes 3D">
      <optionalFileGroups order="Explicit">
        <group name="Chaines de donjons" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Chaînes 3D Haute Définition">
              <description>Replaces flat 2D chain textures with full 3D interlocking physical rings that react realistically to physics and wind.</description>
              <image path="fomod/images/smim_chains.png"/>
              <files>
                <folder source="02 Chains HD/meshes" destination="meshes" priority="2"/>
              </files>
            </plugin>
            <plugin name="Chaînes Standard">
              <description>Default Skyrim chains with minor seam fixes.</description>
              <image path="fomod/images/smim_chains.png"/>
              <files>
                <folder source="02 Chains Standard/meshes" destination="meshes" priority="2"/>
              </files>
            </plugin>
          </plugins>
        </group>
        <group name="Modèles de Lanternes" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Lanternes avec Verre Transparent">
              <description>High detail lanterns with semi-transparent tinted glass and modeled candle wicks.</description>
              <image path="fomod/images/smim_lanterns.png"/>
              <files>
                <folder source="02 Lanterns Glass/meshes" destination="meshes" priority="2"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>

    <installStep name="Correctifs &amp; Compatibilité">
      <optionalFileGroups order="Explicit">
        <group name="Patches d'Éclairage" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="Patch pour Enhanced Lights and FX (ELFX)">
              <description>Compatibility patch for ELFX. Automatically activated when EnhancedLightsandFX.esp is detected in your Data folder.</description>
              <image path="fomod/images/smim_elfx.png"/>
              <files>
                <file source="03 Patches/SMIM-ELFX-Patch.esp" destination="SMIM-ELFX-Patch.esp" priority="3"/>
              </files>
              <dependencies operator="And">
                <fileDependency file="EnhancedLightsandFX.esp" state="Active"/>
              </dependencies>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</moduleConfiguration>`,
};

