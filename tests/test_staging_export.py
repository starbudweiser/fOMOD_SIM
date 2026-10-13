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
from python_app.fomod.staging import export_staging_to_directory, export_staging_to_zip

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


if __name__ == "__main__":
    unittest.main()
