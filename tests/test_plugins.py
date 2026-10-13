"""Détection des plugins : masters des .esp, scan du dossier Data, pré-sélection des patchs."""
import os
import struct
import tempfile
import unittest

from python_app.fomod.parser import parse_module_config_xml
from python_app.fomod.plugins import annotate_option_masters, parse_plugin_masters, scan_data_dir
from python_app.fomod.session import InstallSession
from python_app.fomod.types import ArchiveIndex, VirtualFileEntry
from tests.test_fomod_session import config, group, plugin, step


def make_plugin(*masters: str) -> bytes:
    """En-tête TES4 minimal : HEDR puis un MAST + DATA par master."""
    subs = b"HEDR" + struct.pack("<H", 12) + b"\0" * 12
    for m in masters:
        name = m.encode("cp1252") + b"\0"
        subs += b"MAST" + struct.pack("<H", len(name)) + name + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<I", len(subs)) + b"\0" * 16 + subs


def index_with(plugins: dict) -> ArchiveIndex:
    files, dirs = {}, {}
    for path, data in plugins.items():
        files[path.lower()] = VirtualFileEntry(path=path, size=len(data), data=data)
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs["/".join(parts[:i]).lower()] = "/".join(parts[:i])
    return ArchiveIndex(files=files, dirs=dirs)


class TestPluginMasters(unittest.TestCase):
    def test_parse_masters(self):
        self.assertEqual(parse_plugin_masters(make_plugin("Skyrim.esm", "SkyUI_SE.esp")), ["skyrim.esm", "skyui_se.esp"])

    def test_not_a_plugin(self):
        self.assertEqual(parse_plugin_masters(b"PK\x03\x04" + b"\0" * 40), [])


# Mod avec un plugin principal et deux patchs en choix unique : USSEP ou non, plus un patch SkyUI
PATCH_MOD = config(
    step("Version", group("Version", "SelectExactlyOne",
        plugin("Standard", '<file source="Standard/Mod.esp"/>', type_name="Recommended")
        + plugin("USSEP", '<file source="USSEP/Mod.esp"/>')))
    + step("Patchs", group("Patchs", "SelectAny",
        plugin("SkyUI", '<file source="Patches/Mod - UI.esp"/>')))
)
PATCH_INDEX = index_with({
    "Standard/Mod.esp": make_plugin("Skyrim.esm"),
    "USSEP/Mod.esp": make_plugin("Skyrim.esm", "Unofficial Skyrim Special Edition Patch.esp"),
    "Patches/Mod - UI.esp": make_plugin("Skyrim.esm", "Mod.esp", "SkyUI_SE.esp"),
})


class TestPatchPreselection(unittest.TestCase):
    def setUp(self):
        _, self.steps, _, _ = parse_module_config_xml(PATCH_MOD)
        annotate_option_masters(PATCH_INDEX, self.steps)
        self.standard, self.ussep = self.steps[0].groups[0].options
        self.ui = self.steps[1].groups[0].options[0]

    def test_masters_exclude_vanilla_and_mod_plugins(self):
        self.assertEqual(self.standard.required_masters, set())
        self.assertEqual(self.ussep.required_masters, {"unofficial skyrim special edition patch.esp"})
        self.assertEqual(self.ui.required_masters, {"skyui_se.esp"})

    def test_without_data_author_defaults(self):
        sess = InstallSession(self.steps)
        self.assertEqual(sess.selected, {self.standard.id})

    def test_detected_masters_win(self):
        sess = InstallSession(self.steps, installed_basenames={
            "skyrim.esm", "unofficial skyrim special edition patch.esp", "skyui_se.esp"})
        self.assertEqual(sess.selected, {self.ussep.id, self.ui.id})

    def test_missing_master_not_checked(self):
        sess = InstallSession(self.steps, installed_basenames={"skyrim.esm", "unofficial skyrim special edition patch.esp"})
        self.assertNotIn(self.ui.id, sess.selected)


class TestDataScan(unittest.TestCase):
    def test_scan_keeps_plugins_and_skips_asset_folders(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in ("Skyrim.esm", "SKSE/Plugins/po3.dll", "Mod.bsa", "readme.txt",
                        "textures/fake.esp", "Meshes/x.nif"):
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "wb").close()
            self.assertEqual(scan_data_dir(d), {"skyrim.esm", "po3.dll", "mod.bsa"})


if __name__ == "__main__":
    unittest.main()
