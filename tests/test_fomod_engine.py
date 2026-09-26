import os
import unittest
import tempfile
import zipfile
from python_app.fomod.types import (
    FomodStep,
    FomodGroup,
    FomodOption,
    FomodFileItem,
    FomodFolderItem,
    GroupType,
    ArchiveIndex,
    VirtualFileEntry,
    FomodDependencies,
    FileDependency,
    FlagDependency,
    ConditionalInstallPattern,
    TypeDescriptor,
    TypeDescriptorPattern,
)
from python_app.fomod.parser import (
    parse_module_config_xml,
    parse_info_xml,
    norm,
    evaluate_dependencies,
    compute_option_type,
    is_option_recommended,
    find_file_in_index,
    find_folder_in_index,
)
from python_app.fomod.extractor import extract_archive, reanchor_index
from python_app.fomod.staging import (
    build_staging,
    export_staging_to_zip,
    export_staging_to_directory,
    resolve_file_destination,
)
from python_app.fomod.demo_mod import get_demo_mod, SAMPLE_CBBE_MODULE_CONFIG_XML, SAMPLE_CBBE_INFO_XML


class TestFomodParser(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm(r"foo\bar\baz"), "foo/bar/baz")
        self.assertEqual(norm("./meshes/actor.nif"), "meshes/actor.nif")
        self.assertEqual(norm("/textures/skin.dds/"), "textures/skin.dds")

    def test_resolve_file_destination(self):
        # Case 1: destination is already filename
        self.assertEqual(
            resolve_file_destination("CBBE_Physics.esp", "03 Physics/CBBE_Physics.esp"),
            "CBBE_Physics.esp",
        )
        # Case 2: destination is a directory
        self.assertEqual(
            resolve_file_destination("meshes", "01 Curvy/femalebody.nif"),
            "meshes/femalebody.nif",
        )
        # Case 3: destination is '.'
        self.assertEqual(
            resolve_file_destination(".", "Plugin.esp"),
            "Plugin.esp",
        )

    def test_parse_info_xml(self):
        meta = parse_info_xml(SAMPLE_CBBE_INFO_XML)
        self.assertIn("Caliente", meta.name)
        self.assertEqual(meta.author, "Caliente and Ousnius")
        self.assertEqual(meta.version, "2.0.3")
        self.assertTrue(len(meta.description) > 20)

    def test_parse_module_config(self):
        mod_name, steps, req_files, cond_installs = parse_module_config_xml(SAMPLE_CBBE_MODULE_CONFIG_XML)
        self.assertIn("Caliente", mod_name)
        self.assertEqual(len(req_files), 1)
        self.assertEqual(req_files[0].source, "00 Core")
        self.assertEqual(len(steps), 5)
        self.assertEqual(len(cond_installs), 0)

        # Check step 1
        step1 = steps[0]
        self.assertIn("Silhouette", step1.name)
        self.assertEqual(len(step1.groups), 1)
        grp = step1.groups[0]
        self.assertEqual(grp.type, GroupType.SelectExactlyOne)
        self.assertEqual(len(grp.options), 3)
        self.assertEqual(grp.options[0].name, "CBBE Curvy (Recommandé)")
        self.assertTrue(grp.options[0].is_default)

    def test_dependencies_evaluation(self):
        # And condition with file
        deps_and = FomodDependencies(
            operator="And",
            file_dependencies=[FileDependency("SkyUI_SE.esp", "Active")],
        )
        self.assertTrue(evaluate_dependencies(deps_and, {"skyui_se.esp"}, {}))
        self.assertFalse(evaluate_dependencies(deps_and, {"other.esp"}, {}))

        # Missing state condition
        deps_missing = FomodDependencies(
            operator="And",
            file_dependencies=[FileDependency("Lanterns Of Skyrim II.esm", "Missing")],
        )
        self.assertTrue(evaluate_dependencies(deps_missing, set(), {}))
        self.assertFalse(evaluate_dependencies(deps_missing, {"lanterns of skyrim ii.esm"}, {}))

        # Flag condition with active and inactive
        deps_flag_active = FomodDependencies(
            operator="And",
            flag_dependencies=[FlagDependency("BodyType", "Curvy")],
        )
        self.assertTrue(evaluate_dependencies(deps_flag_active, set(), {"BodyType": "Curvy"}))
        self.assertFalse(evaluate_dependencies(deps_flag_active, set(), {"BodyType": "Slim"}))

        deps_flag_inactive = FomodDependencies(
            operator="And",
            flag_dependencies=[FlagDependency("NoParallax", "inactive")],
        )
        # Unset flag is considered inactive
        self.assertTrue(evaluate_dependencies(deps_flag_inactive, set(), {}))
        # Explicit inactive is inactive
        self.assertTrue(evaluate_dependencies(deps_flag_inactive, set(), {"NoParallax": "inactive"}))
        # Active flag fails inactive requirement
        self.assertFalse(evaluate_dependencies(deps_flag_inactive, set(), {"NoParallax": "active"}))

    def test_type_descriptor_and_recommendation(self):
        xml = """<config>
            <moduleName>Patch Mod</moduleName>
            <installSteps>
                <installStep name="Patches">
                    <optionalFileGroups>
                        <group name="Select" type="SelectAny">
                            <plugins>
                                <plugin name="Dumplings Patch">
                                    <typeDescriptor>
                                        <dependencyType>
                                            <defaultType name="Optional"/>
                                            <patterns>
                                                <pattern>
                                                    <dependencies operator="And">
                                                        <fileDependency file="DumplingsbyKadraeus.esp" state="Active"/>
                                                    </dependencies>
                                                    <type name="Recommended"/>
                                                </pattern>
                                            </patterns>
                                        </dependencyType>
                                    </typeDescriptor>
                                </plugin>
                            </plugins>
                        </group>
                    </optionalFileGroups>
                </installStep>
            </installSteps>
        </config>"""
        _, steps, _, _ = parse_module_config_xml(xml)
        opt = steps[0].groups[0].options[0]

        # Without dumpling mod in data
        self.assertFalse(is_option_recommended(opt, set(), {}))
        self.assertEqual(compute_option_type(opt, set(), {}), "Optional")

        # With dumpling mod in data
        self.assertTrue(is_option_recommended(opt, {"dumplingsbykadraeus.esp"}, {}))
        self.assertEqual(compute_option_type(opt, {"dumplingsbykadraeus.esp"}, {}), "Recommended")

    def test_conditional_file_installs(self):
        xml = """<config>
            <moduleName>Exotic Mod</moduleName>
            <installSteps>
                <installStep name="Step 1">
                    <optionalFileGroups>
                        <group name="Choice" type="SelectExactlyOne">
                            <plugins>
                                <plugin name="Option A">
                                    <conditionFlags>
                                        <flag name="StyleA">active</flag>
                                    </conditionFlags>
                                    <files>
                                        <file source="base.esp" destination="base.esp"/>
                                    </files>
                                </plugin>
                            </plugins>
                        </group>
                    </optionalFileGroups>
                </installStep>
            </installSteps>
            <conditionalFileInstalls>
                <patterns>
                    <pattern>
                        <dependencies operator="And">
                            <flagDependency flag="StyleA" value="active"/>
                        </dependencies>
                        <files>
                            <file source="extra_plugin.esp" destination="extra_plugin.esp" priority="5"/>
                            <folder source="extra_folder" destination="" priority="2"/>
                        </files>
                    </pattern>
                </patterns>
            </conditionalFileInstalls>
        </config>"""
        mod_name, steps, req_files, cond_installs = parse_module_config_xml(xml)
        self.assertEqual(len(cond_installs), 1)
        self.assertEqual(len(cond_installs[0].files), 1)
        self.assertEqual(cond_installs[0].files[0].source, "extra_plugin.esp")

        index = ArchiveIndex(
            files={
                "base.esp": VirtualFileEntry(path="base.esp", data=b"base"),
                "extra_plugin.esp": VirtualFileEntry(path="extra_plugin.esp", data=b"extra"),
                "extra_folder/mesh.nif": VirtualFileEntry(path="extra_folder/mesh.nif", data=b"nif"),
            },
            dirs={"extra_folder": "extra_folder"},
        )

        selected_opts = [steps[0].groups[0].options[0]]
        active_flags = {"StyleA": "active"}

        result = build_staging(
            selected_options=selected_opts,
            required_files=req_files,
            archive_index=index,
            conditional_installs=cond_installs,
            active_flags=active_flags,
            installed_basenames=set(),
        )

        dest_paths = [item.destination_path.lower() for item in result.items]
        self.assertIn("base.esp", dest_paths)
        self.assertIn("extra_plugin.esp", dest_paths)
        self.assertIn("mesh.nif", dest_paths)
        self.assertEqual(result.copied_count, 3)

    def test_reanchor_index(self):
        # Test wrapper directory auto-removal (Mitsuriou's Follower Bodies Overhaul7z/fomod/ModuleConfig.xml)
        files = {
            "root_wrapper/fomod/moduleconfig.xml": VirtualFileEntry(path="root_wrapper/fomod/ModuleConfig.xml"),
            "root_wrapper/00 core/mesh.nif": VirtualFileEntry(path="root_wrapper/00 Core/mesh.nif", size=100),
        }
        dirs = {"root_wrapper/00 core": "root_wrapper/00 Core"}

        new_files, new_dirs = reanchor_index(files, dirs)
        self.assertIn("fomod/moduleconfig.xml", new_files)
        self.assertIn("00 core/mesh.nif", new_files)
        self.assertEqual(new_files["00 core/mesh.nif"].path, "00 Core/mesh.nif")

    def test_staging_build(self):
        index, cfg_xml, info_xml = get_demo_mod()
        mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)

        selected_opts = [
            steps[0].groups[0].options[0],  # CBBE Curvy
            steps[1].groups[0].options[1],  # 2K Textures
        ]

        result = build_staging(selected_opts, req_files, index, cond_installs)
        self.assertTrue(result.copied_count > 0)
        self.assertEqual(result.missing_count, 0)

        dest_paths = [item.destination_path.lower() for item in result.items]
        # Should include core files
        self.assertTrue(any("femalehead.nif" in p for p in dest_paths))
        # Should include curvy body
        self.assertTrue(any("femalebody_0.nif" in p for p in dest_paths))
        # Should include 2k textures
        self.assertTrue(any("femalebody_2k.dds" in p for p in dest_paths))

    def test_export_to_zip(self):
        index, cfg_xml, info_xml = get_demo_mod()
        mod_name, steps, req_files, cond_installs = parse_module_config_xml(cfg_xml)
        selected_opts = [steps[0].groups[0].options[0]]

        result = build_staging(selected_opts, req_files, index, cond_installs)

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            export_staging_to_zip(result, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            with zipfile.ZipFile(tmp_path, "r") as zf:
                names = zf.namelist()
                self.assertTrue(len(names) > 0)
                self.assertTrue(any("femalehead.nif" in n for n in names))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
