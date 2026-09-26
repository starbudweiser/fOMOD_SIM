import unittest
from python_app.fomod.types import (
    ArchiveIndex,
    VirtualFileEntry,
    GroupType,
)
from python_app.fomod.parser import (
    parse_module_config_xml,
    evaluate_dependencies,
    compute_option_type,
    is_option_recommended,
)
from python_app.fomod.staging import build_staging

# The ModuleConfig.xml provided by the user for Embers XD
EMBERS_XD_XML = """<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
	<moduleName>Embers XD</moduleName>
	<installSteps order="Explicit">
		<installStep name="Flames And Lights Customization">
			<optionalFileGroups order="Explicit">
				<group name="Flames Style" type="SelectExactlyOne">
					<plugins order="Explicit">
						<plugin name="Embers XD Flames">
							<conditionFlags>
								<flag name="EmbersXD">active</flag>
								<flag name="Torches">inactive</flag>
								<flag name="New">active</flag>
								<flag name="NoParallax">inactive</flag>
								<flag name="VanillaRocks">inactive</flag>
								<flag name="Cooking">inactive</flag>
								<flag name="EmbersHD">inactive</flag>
							</conditionFlags>
							<typeDescriptor>
								<type name="Recommended"/>
							</typeDescriptor>
						</plugin>
					</plugins>
				</group>
			</optionalFileGroups>
		</installStep>
		<installStep name="Plugin Selection">
			<optionalFileGroups>
				<group name="Select One" type="SelectExactlyOne">
					<plugins order="Explicit">
						<plugin name="Standard (Master + ESP)">
							<conditionFlags>
								<flag name="HD">active</flag>
								<flag name="Lux">inactive</flag>
							</conditionFlags>
							<files>
								<folder source="plugins/esm" destination=""/>
							</files>
							<typeDescriptor>
								<type name="Recommended"/>
							</typeDescriptor>
						</plugin>
					</plugins>
				</group>
			</optionalFileGroups>
		</installStep>
		<installStep name="Add-On Selection">
			<optionalFileGroups order="Explicit">
				<group name="Select One" type="SelectAny">
					<plugins order="Explicit">
						<plugin name="Install Fire Magick Add-On">
							<conditionFlags>
								<flag name="Magick">active</flag>
							</conditionFlags>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="NotUsable"/>
									<patterns>
										<pattern>
											<dependencies operator="And">
												<flagDependency flag="EmbersXD" value="active"/>
												<fileDependency file="Dawnguard.esm" state="Active"/>
											</dependencies>
											<type name="Optional"/>
										</pattern>
									</patterns>
								</dependencyType>
							</typeDescriptor>
						</plugin>
					</plugins>
				</group>
			</optionalFileGroups>
		</installStep>
		<installStep name="Further Customization">
			<optionalFileGroups>
				<group name="Select Required" type="SelectAny">
					<plugins>
						<plugin name="Reduced Actor Flames">
							<conditionFlags>
								<flag name="ReducedActorFlames">active</flag>
							</conditionFlags>
							<typeDescriptor>
								<type name="Optional"/>
							</typeDescriptor>
						</plugin>
					</plugins>
				</group>
			</optionalFileGroups>
		</installStep>
		<installStep name="Compatibility Patches">
			<optionalFileGroups>
				<group name="Select Required" type="SelectAny">
					<plugins>
						<plugin name="Hearthfire Crispy Dumplings">
							<conditionFlags>
								<flag name="CrispyDumplings">active</flag>
							</conditionFlags>
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
						<plugin name="Gourmet - Cooking Pots and Baking Ovens">
							<files>
								<folder source="patches/Gourmet" destination=""/>
							</files>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="Optional"/>
									<patterns>
										<pattern>
											<dependencies operator="And">
												<fileDependency file="GourmetTables.esp" state="Active"/>
											</dependencies>
											<type name="Recommended"/>
										</pattern>
									</patterns>
								</dependencyType>
							</typeDescriptor>
						</plugin>
						<plugin name="Windhelm Braziers BOS">
							<conditionFlags>
								<flag name="WindhelmBSO">active</flag>
							</conditionFlags>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="Optional"/>
									<patterns>
										<pattern>
											<dependencies operator="And">
												<fileDependency file="Windhelm_Braziers.esp" state="Active"/>
												<dependencies operator="Or">
													<fileDependency file="Lanterns Of Skyrim II.esm" state="Inactive"/>
													<fileDependency file="Lanterns Of Skyrim II.esm" state="Missing"/>
												</dependencies>
											</dependencies>
											<type name="Recommended"/>
										</pattern>
									</patterns>
								</dependencyType>
							</typeDescriptor>
						</plugin>
						<plugin name="Windhelm Braziers BOS + Lanterns of Skyrim II">
							<conditionFlags>
								<flag name="WindhelmBSO-LOS2">active</flag>
							</conditionFlags>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="Optional"/>
									<patterns>
										<pattern>
											<dependencies operator="And">
												<fileDependency file="Windhelm_Braziers.esp" state="Active"/>
												<fileDependency file="Lanterns Of Skyrim II.esm" state="Active"/>
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
	<conditionalFileInstalls>
        <patterns>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="New" value="active"/>
                </dependencies>
                <files>
                    <folder source="assets\\core\\meshes\\common" destination="" priority="1"/>
					<folder source="assets\\core\\meshes\\new" destination="" priority="1"/>
                </files>
            </pattern>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="Magick" value="active"/>
					<flagDependency flag="New" value="active"/>
                </dependencies>
                <files>
					<file source="plugins/magick/Embers XD - Fire Magick Add-On.esp" destination="Embers XD - Fire Magick Add-On.esp" priority="1"/>
				</files>
            </pattern>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="ReducedActorFlames" value="active"/>
                    <flagDependency flag="New" value="active"/>
				</dependencies>
                <files>
					<file source="patches/Reduced_Actor_Flames/Embers XD - Reduced Actor Flames.esp" destination="Embers XD - Reduced Actor Flames.esp" priority="1"/>
				</files>
            </pattern>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="CrispyDumplings" value="active"/>
					<flagDependency flag="New" value="active"/>
					<flagDependency flag="Cooking" value="inactive"/>
				</dependencies>
                <files>
                    <folder source="patches\\Hearthfire_Crispy_Dumplings\\new" destination="" priority="7"/>
                </files>
            </pattern>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="WindhelmBSO-LOS2" value="active"/>
				</dependencies>
                <files>
                    <folder source="patches\\Windhelm_Braziers_BSO-LOS2" destination="" priority="7"/>
                </files>
            </pattern>
		</patterns>
    </conditionalFileInstalls>
</config>
"""


class TestEmbersXD(unittest.TestCase):
    def test_embers_xd_interpretation_and_staging(self):
        mod_name, steps, req_files, cond_installs = parse_module_config_xml(EMBERS_XD_XML)
        self.assertEqual(mod_name, "Embers XD")
        self.assertEqual(len(steps), 5)
        self.assertEqual(len(cond_installs), 5)

        # Simuler un dossier Data contenant GourmetTables.esp et DumplingsbyKadraeus.esp
        installed = {"gourmettables.esp", "dumplingsbykadraeus.esp", "windhelm_braziers.esp", "lanterns of skyrim ii.esm"}
        active_flags = {"New": "active", "EmbersXD": "active", "HD": "active", "Magick": "active", "ReducedActorFlames": "active"}

        patch_step = steps[4]
        patch_opts = patch_step.groups[0].options

        # Vérifier Crispy Dumplings
        self.assertTrue(is_option_recommended(patch_opts[0], installed, active_flags))

        # Vérifier Gourmet
        self.assertTrue(is_option_recommended(patch_opts[1], installed, active_flags))

        # Vérifier Windhelm BOS (doit être False car LOS2 est Active)
        self.assertFalse(is_option_recommended(patch_opts[2], installed, active_flags))

        # Vérifier Windhelm BOS + LOS2 (doit être True car les deux sont Active)
        self.assertTrue(is_option_recommended(patch_opts[3], installed, active_flags))

        # Sélectionner les options
        selected_options = [
            steps[0].groups[0].options[0],  # Flames
            steps[1].groups[0].options[0],  # Plugin Standard (Embers XD.esp)
            steps[2].groups[0].options[0],  # Magick Add-on
            steps[3].groups[0].options[0],  # Reduced Actor Flames
            patch_opts[0],                 # Crispy Dumplings
            patch_opts[1],                 # Gourmet
            patch_opts[3],                 # Windhelm BOS + LOS2
        ]

        for opt in selected_options:
            for k, v in opt.flags.items():
                active_flags[k] = v

        # Créer index virtuel avec tous les fichiers
        index = ArchiveIndex(
            files={
                "plugins/esm/embers xd.esp": VirtualFileEntry(path="plugins/esm/Embers XD.esp", data=b"esp"),
                "plugins/esm/embers xd.esm": VirtualFileEntry(path="plugins/esm/Embers XD.esm", data=b"esm"),
                "plugins/magick/embers xd - fire magick add-on.esp": VirtualFileEntry(path="plugins/magick/Embers XD - Fire Magick Add-On.esp", data=b"magick"),
                "patches/reduced_actor_flames/embers xd - reduced actor flames.esp": VirtualFileEntry(path="patches/Reduced_Actor_Flames/Embers XD - Reduced Actor Flames.esp", data=b"flames"),
                "patches/gourmet/embers xd - patch - gourmet tables.esp": VirtualFileEntry(path="patches/Gourmet/Embers XD - Patch - Gourmet Tables.esp", data=b"gourmet"),
                "patches/windhelm_braziers_bso-los2/embers xd - patch - windhelm braziers bos - losii_swap.ini": VirtualFileEntry(path="patches/Windhelm_Braziers_BSO-LOS2/Embers XD - Patch - Windhelm Braziers BOS - LOSII_SWAP.ini", data=b"ini"),
                "patches/windhelm_braziers_bso-los2/embers xd - patch - windhelm braziers bos.esp": VirtualFileEntry(path="patches/Windhelm_Braziers_BSO-LOS2/Embers XD - Patch - Windhelm Braziers BOS.esp", data=b"bos"),
                "assets/core/meshes/common/mesh.nif": VirtualFileEntry(path="assets/core/meshes/common/mesh.nif", data=b"mesh"),
            },
            dirs={
                "plugins/esm": "plugins/esm",
                "patches/gourmet": "patches/Gourmet",
                "patches/windhelm_braziers_bso-los2": "patches/Windhelm_Braziers_BSO-LOS2",
                "assets/core/meshes/common": "assets/core/meshes/common",
            }
        )

        staging_res = build_staging(
            selected_options=selected_options,
            required_files=[],
            archive_index=index,
            conditional_installs=cond_installs,
            active_flags=active_flags,
            installed_basenames=installed,
        )

        # Vérifier que MULTIPLES ESP sont copiés
        dest_esps = [item.destination_path for item in staging_res.items if item.destination_path.lower().endswith(".esp")]
        print("ESPs copiés dans le Staging:", dest_esps)
        self.assertGreater(len(dest_esps), 1)
        self.assertIn("Embers XD.esp", dest_esps)
        self.assertIn("Embers XD - Fire Magick Add-On.esp", dest_esps)
        self.assertIn("Embers XD - Reduced Actor Flames.esp", dest_esps)
        self.assertIn("Embers XD - Patch - Gourmet Tables.esp", dest_esps)
        self.assertIn("Embers XD - Patch - Windhelm Braziers BOS.esp", dest_esps)


if __name__ == "__main__":
    unittest.main()
