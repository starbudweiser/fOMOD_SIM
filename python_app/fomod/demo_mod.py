import logging
from typing import Dict, Tuple
from .types import ArchiveIndex, VirtualFileEntry

logger = logging.getLogger(__name__)

SAMPLE_CBBE_INFO_XML = """<?xml version="1.0" encoding="utf-8"?>
<fomod>
  <Name>Caliente's Beautiful Bodies Enhancer - CBBE - SE</Name>
  <Author>Caliente and Ousnius</Author>
  <Version>2.0.3</Version>
  <Website>https://www.nexusmods.com/skyrimspecialedition/mods/198</Website>
  <Description>Caliente's Beautiful Bodies Enhancer (CBBE) is a complete female body mesh and texture overhaul for The Elder Scrolls V: Skyrim Special Edition.
Features realistic anatomy, smooth vertices, seamless neck joints, and comprehensive clothing and armor support. Compatible with HDT-SMP, CBPC, and BodySlide and Outfit Studio.</Description>
</fomod>"""

SAMPLE_CBBE_MODULE_CONFIG_XML = """<?xml version="1.0" encoding="utf-8"?>
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
            </plugin>
            <plugin name="Support des Sliders RaceMenu (skee64)">
              <description>Installs body morph sliders, overlay textures and bodypaint slots into RaceMenu character generation menu.</description>
              <image path="fomod/images/racemenu_patch.png"/>
              <files>
                <folder source="05 RaceMenu/SKSE" destination="SKSE" priority="5"/>
                <file source="05 RaceMenu/CBBE_RaceMenu_Morphs.esp" destination="CBBE_RaceMenu_Morphs.esp" priority="5"/>
              </files>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</moduleConfiguration>"""


def get_demo_mod() -> Tuple[ArchiveIndex, str, str]:
    """Retourne l'index d'archive virtuel du mod démo CBBE."""
    files: Dict[str, VirtualFileEntry] = {}
    dirs: Dict[str, str] = {}

    # info.xml
    info_bytes = SAMPLE_CBBE_INFO_XML.encode("utf-8")
    files["fomod/info.xml"] = VirtualFileEntry(path="fomod/info.xml", size=len(info_bytes), data=info_bytes)
    dirs["fomod"] = "fomod"

    # moduleconfig.xml
    cfg_bytes = SAMPLE_CBBE_MODULE_CONFIG_XML.encode("utf-8")
    files["fomod/moduleconfig.xml"] = VirtualFileEntry(path="fomod/ModuleConfig.xml", size=len(cfg_bytes), data=cfg_bytes)

    dummy_files = [
        "00 Core/meshes/actors/character/character assets/femalehead.nif",
        "00 Core/textures/actors/character/female/femalehead.dds",
        "01 Curvy/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Curvy/meshes/actors/character/character assets/femalebody_1.nif",
        "01 Slim/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Slim/meshes/actors/character/character assets/femalebody_1.nif",
        "01 Vanilla/meshes/actors/character/character assets/femalebody_0.nif",
        "01 Vanilla/meshes/actors/character/character assets/femalebody_1.nif",
        "02 Textures 4K/textures/actors/character/female/femalebody_4k.dds",
        "02 Textures 4K/textures/actors/character/female/femalebody_msn.dds",
        "02 Textures 2K/textures/actors/character/female/femalebody_2k.dds",
        "02 Textures 2K/textures/actors/character/female/femalebody_msn.dds",
        "03 Physics/meshes/actors/character/character assets/femalebody_physics.nif",
        "03 Physics/CBBE_Physics.esp",
        "03 Static/meshes/actors/character/character assets/femalebody_static.nif",
        "04 Underwear/meshes/actors/character/character assets/femaleunderwear.nif",
        "04 Underwear/textures/actors/character/female/underwear.dds",
        "04 NeverNude/meshes/actors/character/character assets/nevernude.nif",
        "04 NeverNude/textures/actors/character/female/nevernude.dds",
        "05 Patches/CBBE_SkyUI_Addon.esp",
        "05 RaceMenu/SKSE/Plugins/CharGen/Overlays.ini",
        "05 RaceMenu/CBBE_RaceMenu_Morphs.esp",
    ]

    for fpath in dummy_files:
        k = fpath.lower()
        sz = 14200 if fpath.endswith(".esp") else 854000
        files[k] = VirtualFileEntry(path=fpath, size=sz, data=b"DUMMY_DATA")

        parts = fpath.split("/")
        cur = ""
        for i in range(len(parts) - 1):
            cur = f"{cur}/{parts[i]}" if cur else parts[i]
            dirs[cur.lower()] = cur

    return ArchiveIndex(files=files, dirs=dirs), SAMPLE_CBBE_MODULE_CONFIG_XML, SAMPLE_CBBE_INFO_XML
