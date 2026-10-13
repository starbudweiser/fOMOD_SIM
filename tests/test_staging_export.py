"""Export du staging : les fichiers non chargés à l'indexation (textures, meshes) sont lus dans
l'archive à l'export, jamais écrits vides (bug du Lore Main Menu Compendium, 13/10/2026)."""
import os
import shutil
import tempfile
import unittest
import zipfile

from python_app.fomod.extractor import extract_archive
from python_app.fomod.parser import parse_module_config_xml
from python_app.fomod.session import InstallSession
from python_app.fomod.staging import export_staging_to_directory, export_staging_to_zip, staging_folder_name

CONFIG = """<?xml version="1.0" encoding="UTF-8"?>
<config><moduleName>Test</moduleName><installSteps order="Explicit">
<installStep name="Wallpapers"><optionalFileGroups order="Explicit">
<group name="Choix" type="SelectAny"><plugins order="Explicit">
<plugin name="Tous"><description>x</description>
<files><folder source="wallpapers" destination="mainmenuwallpapers"/></files>
<typeDescriptor><type name="Recommended"/></typeDescriptor></plugin>
</plugins></group></optionalFileGroups></installStep></installSteps></config>"""

# Plusieurs fichiers de même nom dans des dossiers différents, comme MainMenu.dds dans LMMC
TEXTURES = {f"wallpapers/{n}/data/textures/loremainmenu/MainMenu.dds": f"DDS {n} ".encode() * 500
            for n in ("Alduin", "Dragon War", "Bear Attack (2)")}


class TestStagingExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.archive = os.path.join(self.tmp, "mod.zip")
        with zipfile.ZipFile(self.archive, "w") as zf:
            zf.writestr("fomod/ModuleConfig.xml", CONFIG)
            for path, data in TEXTURES.items():
                zf.writestr(path, data)
        index, cfg, _ = extract_archive(self.archive)
        _, steps, req, cond = parse_module_config_xml(cfg)
        self.index = index
        self.result = InstallSession(steps, req, cond).build_staging(index)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_textures_are_deferred(self):
        # Prérequis du test : les .dds ne sont pas chargés à l'indexation
        self.assertTrue(all(i.data is None and i.member for i in self.result.items))

    def test_directory_export_has_content(self):
        out = os.path.join(self.tmp, "staging")
        self.assertEqual(export_staging_to_directory(self.result, out, self.index), [])
        for path, data in TEXTURES.items():
            dest = os.path.join(out, path.replace("wallpapers/", "mainmenuwallpapers/", 1))
            with open(dest, "rb") as fh:
                self.assertEqual(fh.read(), data)

    def test_zip_export_has_content(self):
        zpath = os.path.join(self.tmp, "out.zip")
        self.assertEqual(export_staging_to_zip(self.result, zpath, self.index), [])
        with zipfile.ZipFile(zpath) as zf:
            for path, data in TEXTURES.items():
                self.assertEqual(zf.read(path.replace("wallpapers/", "mainmenuwallpapers/", 1)), data)

    def test_unreadable_content_is_reported_not_written_empty(self):
        out = os.path.join(self.tmp, "staging")
        failures = export_staging_to_directory(self.result, out, None)  # pas d'accès à l'archive
        self.assertEqual(len(failures), len(TEXTURES))
        for item in self.result.items:
            self.assertFalse(os.path.exists(os.path.join(out, item.destination_path)))


class TestStagingFolderName(unittest.TestCase):
    def test_nexus_archive_suffix_removed_uppercase(self):
        self.assertEqual(
            staging_folder_name("/m/5 Main Menu Compendium - Randomizer (16-10)-150450-2-0-1747924526.zip", "LMMC"),
            "5 MAIN MENU COMPENDIUM - RANDOMIZER (16-10)",
        )
        self.assertEqual(staging_folder_name("/m/SLF Hair - Lite 1K-36510-2-0.7z"), "SLF HAIR - LITE 1K")

    def test_recent_nexus_and_collection_formats(self):
        cases = {
            "LMMC - Randomizer (16-9_10) (2K) 150450 2.1.1 2026-09-15T13-16Z izkcFpI8F.7z": "LMMC - RANDOMIZER (16-9_10) (2K)",
            "Accuracy - MCM menu 187578 MCM-01 2026-08-07T23-03Z CmfxYjTwZ.zip": "ACCURACY - MCM MENU",
            "DynDOLOD 3.00 68518 Alpha-208 2026-07-24T09-23Z OyYrPubRn (1).7z": "DYNDOLOD 3.00",
            "Easy_Console_Commands_1.0.25_Ks18n0cJO.zip": "EASY CONSOLE COMMANDS",
            "Lute-3391-.zip": "LUTE",
            "Lock.Picking.Redone.7z": "LOCK.PICKING.REDONE",
        }
        for archive, expected in cases.items():
            self.assertEqual(staging_folder_name("/m/" + archive), expected)

    def test_variants_of_same_mod_get_distinct_folders(self):
        a = staging_folder_name("/m/LMMC - Randomizer (16-9)-150450-2-0-1.zip", "Lore-Friendly Main Menu Compendium")
        b = staging_folder_name("/m/LMMC - Randomizer (21-9)-150450-2-0-1.zip", "Lore-Friendly Main Menu Compendium")
        self.assertNotEqual(a, b)

    def test_fallback_and_forbidden_characters(self):
        self.assertEqual(staging_folder_name(None, "Nom: du/mod"), "NOM- DU-MOD")
        self.assertEqual(staging_folder_name(None, ""), "MOD FOMOD")


if __name__ == "__main__":
    unittest.main()
