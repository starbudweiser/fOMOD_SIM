"""Cas de conception FOMOD rencontrés dans des mods réels : visibilité des étapes, flags,
ordre, règles des groupes, types d'options, alwaysInstall, chemins et encodages."""
import unittest

from python_app.fomod.extractor import decode_xml_text
from python_app.fomod.parser import (
    find_folder_in_index,
    find_file_in_index,
    find_image_in_index,
    parse_module_config_xml,
)
from python_app.fomod.session import InstallSession
from python_app.fomod.types import ArchiveIndex, VirtualFileEntry


def make_index(*paths):
    files, dirs = {}, {}
    for p in paths:
        files[p.lower()] = VirtualFileEntry(path=p, size=10)
        parts = p.split("/")
        for i in range(1, len(parts)):
            sub = "/".join(parts[:i])
            dirs[sub.lower()] = sub
    return ArchiveIndex(files=files, dirs=dirs)


def plugin(name, files="", flags="", type_name="Optional", extra=""):
    flag_xml = f"<conditionFlags>{flags}</conditionFlags>" if flags else ""
    files_xml = f"<files>{files}</files>" if files else ""
    return (
        f'<plugin name="{name}"><description>{name}</description>{files_xml}{flag_xml}'
        f'<typeDescriptor><type name="{type_name}"/></typeDescriptor>{extra}</plugin>'
    )


def config(steps_xml, steps_order="Explicit", extra=""):
    return (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">'
        f'<moduleName>Test</moduleName>{extra}<installSteps order="{steps_order}">{steps_xml}</installSteps></config>'
    )


def step(name, groups_xml, visible=""):
    vis = f"<visible>{visible}</visible>" if visible else ""
    return f'<installStep name="{name}">{vis}<optionalFileGroups order="Explicit">{groups_xml}</optionalFileGroups></installStep>'


def group(name, gtype, plugins_xml, order="Explicit"):
    return f'<group name="{name}" type="{gtype}"><plugins order="{order}">{plugins_xml}</plugins></group>'


# Reproduction de « LMMC - Randomizer » : All in One / Modular + étape Modular conditionnelle
LMMC_LIKE = config(
    step("Résolution", group("Resolution", "SelectExactlyOne",
        plugin("16:9", '<folder source="16-9" destination=""/>') + plugin("16:10", '<folder source="16-10" destination=""/>')))
    + step("Installation", group("Installation Options", "SelectExactlyOne",
        plugin("All in One", '<folder source="wallpapers" destination="wallpapers"/>')
        + plugin("Modular", flags='<flag name="modular">On</flag>')))
    + step("Modular Selection", group("Modular Selection", "SelectAtLeastOne",
        plugin("Dragon", '<folder source="wallpapers/Dragon" destination="wallpapers/Dragon"/>')
        + plugin("Bear", '<folder source="wallpapers/Bear" destination="wallpapers/Bear"/>')),
        visible='<dependencies operator="And"><flagDependency flag="modular" value="On"/></dependencies>')
)
LMMC_INDEX = make_index(
    "16-9/meshes/logo.nif", "16-10/meshes/logo.nif",
    "wallpapers/Dragon/a.dds", "wallpapers/Bear/b.dds", "wallpapers/Wolf/c.dds",
    "fomod/ModuleConfig.xml",
)


class TestStepVisibility(unittest.TestCase):
    def setUp(self):
        _, self.steps, req, cond = parse_module_config_xml(LMMC_LIKE)
        self.session = InstallSession(self.steps, req, cond, set())

    def _opt(self, step_idx, name):
        g = self.steps[step_idx].groups[0]
        return next(o for o in g.options if o.name == name), g

    def test_visibility_parsed(self):
        self.assertIsNone(self.steps[0].visibility)
        self.assertIsNotNone(self.steps[2].visibility)

    def test_all_in_one_hides_modular_step_and_installs_everything(self):
        self.assertEqual(self.session.visible_step_indices(), [0, 1])
        res = self.session.build_staging(LMMC_INDEX)
        dests = {i.destination_path for i in res.items}
        self.assertIn("wallpapers/Wolf/c.dds", dests)
        self.assertEqual(res.missing_count, 0)
        # Les options de l'étape masquée ne sont pas installées
        self.assertNotIn("Dragon", [o.name for o in self.session.selected_options()])

    def test_modular_shows_step_and_installs_only_checked(self):
        opt, g = self._opt(1, "Modular")
        self.assertTrue(self.session.toggle(opt, g))
        self.assertEqual(self.session.active_flags, {"modular": "On"})
        self.assertEqual(self.session.visible_step_indices(), [0, 1, 2])
        dests = {i.destination_path for i in self.session.build_staging(LMMC_INDEX).items}
        self.assertNotIn("wallpapers/Wolf/c.dds", dests)
        self.assertIn("wallpapers/Dragon/a.dds", dests)

    def test_back_to_all_in_one_hides_step_again(self):
        mod, g = self._opt(1, "Modular")
        aio, _ = self._opt(1, "All in One")
        self.session.toggle(mod, g)
        self.session.toggle(aio, g)
        self.assertEqual(self.session.visible_step_indices(), [0, 1])
        self.assertEqual(self.session.active_flags, {})


class TestFlagsAndConditions(unittest.TestCase):
    def test_flag_value_is_tag_text(self):
        xml = config(
            step("Corps", group("Body", "SelectExactlyOne",
                plugin("CBBE", flags='<flag name="body">CBBE</flag>') + plugin("UNP", flags='<flag name="body">UNP</flag>')))
            + step("Textures UNP", group("T", "SelectExactlyOne", plugin("UNP tex", '<file source="unp.dds"/>')),
                   visible='<flagDependency flag="body" value="UNP"/>')
        )
        _, steps, req, cond = parse_module_config_xml(xml)
        self.assertEqual(steps[0].groups[0].options[1].flags, {"body": "UNP"})
        s = InstallSession(steps, req, cond, set())
        self.assertEqual(s.visible_step_indices(), [0])  # CBBE par défaut
        s.toggle(steps[0].groups[0].options[1], steps[0].groups[0])
        self.assertEqual(s.visible_step_indices(), [0, 1])

    def test_visible_with_or_and_file_dependency(self):
        xml = config(
            step("A", group("G", "SelectAny", plugin("x", '<file source="x.esp"/>')))
            + step("Patch USSEP", group("P", "SelectAny", plugin("p", '<file source="p.esp"/>')),
                   visible='<dependencies operator="Or"><fileDependency file="Unofficial Skyrim Special Edition Patch.esp" state="Active"/>'
                           '<flagDependency flag="force" value="yes"/></dependencies>')
        )
        _, steps, req, cond = parse_module_config_xml(xml)
        self.assertEqual(InstallSession(steps, req, cond, set()).visible_step_indices(), [0])
        with_ussep = InstallSession(steps, req, cond, {"unofficial skyrim special edition patch.esp"})
        self.assertEqual(with_ussep.visible_step_indices(), [0, 1])

    def test_game_version_dependency_assumed_true(self):
        xml = config(step("A", group("G", "SelectAny", plugin("x")),
                          visible='<dependencies operator="And"><gameDependency version="1.5.97"/></dependencies>'))
        _, steps, req, cond = parse_module_config_xml(xml)
        self.assertEqual(InstallSession(steps, req, cond, set()).visible_step_indices(), [0])

    def test_conditional_installs_use_flags(self):
        xml = config(
            step("Body", group("B", "SelectExactlyOne",
                plugin("CBBE", flags='<flag name="b">cbbe</flag>') + plugin("3BA", flags='<flag name="b">3ba</flag>'))),
            extra="",
        ).replace(
            "</installSteps>",
            '</installSteps><conditionalFileInstalls><patterns><pattern><dependencies><flagDependency flag="b" value="3ba"/>'
            '</dependencies><files><folder source="3ba" destination=""/></files></pattern></patterns></conditionalFileInstalls>',
        )
        _, steps, req, cond = parse_module_config_xml(xml)
        idx = make_index("3ba/meshes/body.nif")
        s = InstallSession(steps, req, cond, set())
        self.assertEqual(s.build_staging(idx).copied_count, 0)
        s.toggle(steps[0].groups[0].options[1], steps[0].groups[0])
        self.assertEqual([i.destination_path for i in s.build_staging(idx).items], ["meshes/body.nif"])


class TestGroupRulesAndTypes(unittest.TestCase):
    def _session(self, gtype, plugins_xml):
        _, steps, req, cond = parse_module_config_xml(config(step("S", group("G", gtype, plugins_xml))))
        return steps[0].groups[0], InstallSession(steps, req, cond, set())

    def test_exactly_one_selects_first_and_cannot_be_emptied(self):
        g, s = self._session("SelectExactlyOne", plugin("a") + plugin("b"))
        self.assertEqual(s.selected, {g.options[0].id})
        self.assertFalse(s.toggle(g.options[0], g))
        self.assertEqual(s.selected, {g.options[0].id})

    def test_exactly_one_prefers_recommended(self):
        g, s = self._session("SelectExactlyOne", plugin("a") + plugin("b", type_name="Recommended"))
        self.assertEqual(s.selected, {g.options[1].id})

    def test_at_most_one_can_be_emptied(self):
        g, s = self._session("SelectAtMostOne", plugin("a") + plugin("b"))
        self.assertEqual(s.selected, set())
        s.toggle(g.options[0], g)
        s.toggle(g.options[0], g)
        self.assertEqual(s.selected, set())

    def test_at_least_one_keeps_one(self):
        g, s = self._session("SelectAtLeastOne", plugin("a") + plugin("b"))
        self.assertEqual(s.selected, {g.options[0].id})
        self.assertFalse(s.toggle(g.options[0], g))
        s.toggle(g.options[1], g)
        self.assertTrue(s.toggle(g.options[0], g))
        self.assertEqual(s.selected, {g.options[1].id})

    def test_select_all_is_locked(self):
        g, s = self._session("SelectAll", plugin("a") + plugin("b"))
        self.assertEqual(s.selected, {o.id for o in g.options})
        self.assertFalse(s.toggle(g.options[0], g))

    def test_required_and_not_usable(self):
        g, s = self._session("SelectAny", plugin("req", type_name="Required") + plugin("no", type_name="NotUsable"))
        self.assertEqual(s.selected, {g.options[0].id})
        self.assertFalse(s.toggle(g.options[0], g))
        self.assertFalse(s.toggle(g.options[1], g))

    def test_dependency_type_pattern(self):
        td = (
            '<typeDescriptor><dependencyType><defaultType name="Optional"/><patterns><pattern>'
            '<dependencies operator="And"><fileDependency file="SkyUI_SE.esp" state="Active"/></dependencies>'
            '<type name="Recommended"/></pattern></patterns></dependencyType></typeDescriptor>'
        )
        xml = config(step("S", group("G", "SelectAny",
            '<plugin name="skyui patch"><description/>' + td + "</plugin>")))
        _, steps, req, cond = parse_module_config_xml(xml)
        self.assertEqual(InstallSession(steps, req, cond, set()).selected, set())
        self.assertEqual(len(InstallSession(steps, req, cond, {"skyui_se.esp"}).selected), 1)


class TestOrderAndFiles(unittest.TestCase):
    def test_order_attributes(self):
        xml = config(
            step("Zeta", group("G", "SelectAny", plugin("b") + plugin("a"), order="Ascending"))
            + step("Alpha", group("G", "SelectAny", plugin("c"))),
            steps_order="Ascending",
        )
        _, steps, _, _ = parse_module_config_xml(xml)
        self.assertEqual([s.name for s in steps], ["Alpha", "Zeta"])
        self.assertEqual([o.name for o in steps[1].groups[0].options], ["a", "b"])

    def test_explicit_order_kept(self):
        xml = config(step("Z", group("G", "SelectAny", "")) + step("A", group("G", "SelectAny", "")))
        _, steps, _, _ = parse_module_config_xml(xml)
        self.assertEqual([s.name for s in steps], ["Z", "A"])

    def test_missing_destination_defaults_to_source(self):
        xml = config(step("S", group("G", "SelectAll", plugin("a", '<file source="Docs\\readme.txt"/><folder source="meshes"/>'))))
        _, steps, _, _ = parse_module_config_xml(xml)
        opt = steps[0].groups[0].options[0]
        self.assertEqual(opt.files[0].destination, "Docs/readme.txt")
        self.assertEqual(opt.folders[0].destination, "meshes")

    def test_always_install_and_install_if_usable(self):
        xml = config(step("S", group("G", "SelectAny",
            plugin("doc", '<file source="always.txt" alwaysInstall="true"/>')
            + plugin("usable", '<file source="usable.txt" installIfUsable="true"/>')
            + plugin("blocked", '<file source="blocked.txt" installIfUsable="true"/>', type_name="NotUsable"))))
        _, steps, req, cond = parse_module_config_xml(xml)
        s = InstallSession(steps, req, cond, set())
        self.assertEqual(s.selected, set())
        dests = {i.destination_path for i in s.build_staging(make_index("always.txt", "usable.txt", "blocked.txt")).items}
        self.assertEqual(dests, {"always.txt", "usable.txt"})

    def test_folder_does_not_grab_homonyms(self):
        xml = config(step("S", group("G", "SelectAll", plugin("core", '<folder source="00 Core/textures" destination="textures"/>'))))
        _, steps, req, cond = parse_module_config_xml(xml)
        idx = make_index("00 Core/textures/a.dds", "01 Option/textures/b.dds")
        dests = {i.destination_path for i in InstallSession(steps, req, cond, set()).build_staging(idx).items}
        self.assertEqual(dests, {"textures/a.dds"})

    def test_empty_folder_source_is_mod_root(self):
        xml = config(step("S", group("G", "SelectAll", plugin("all", '<folder source="" destination=""/>'))))
        _, steps, req, cond = parse_module_config_xml(xml)
        idx = make_index("plugin.esp", "meshes/a.nif", "fomod/ModuleConfig.xml")
        dests = {i.destination_path for i in InstallSession(steps, req, cond, set()).build_staging(idx).items}
        self.assertEqual(dests, {"plugin.esp", "meshes/a.nif"})


class TestLookupAndEncoding(unittest.TestCase):
    def test_lookup_respects_segment_boundaries(self):
        idx = make_index("mymod.esp", "Data/mod.esp")
        self.assertEqual(find_file_in_index(idx, "mod.esp").path, "Data/mod.esp")
        self.assertIsNone(find_folder_in_index(make_index("xtextures/a.dds"), "textures"))

    def test_image_extension_fallback(self):
        idx = make_index("Images/shot 1.jpg")
        self.assertEqual(find_image_in_index(idx, "Images\\shot 1.png").path, "Images/shot 1.jpg")

    def test_utf16_without_bom_and_bare_ampersand(self):
        xml = config(step("Tops & Bottoms", group("G", "SelectAny", plugin("a"))))
        for raw in (xml.encode("utf-16"), xml.encode("utf-16-le")):
            _, steps, _, _ = parse_module_config_xml(decode_xml_text(raw))
            self.assertEqual(steps[0].name, "Tops & Bottoms")


if __name__ == "__main__":
    unittest.main()
