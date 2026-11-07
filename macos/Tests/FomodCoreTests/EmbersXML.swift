// XML de test (Embers XD), repris de tests/test_embers_xd.py

let embersXdXML = #"""
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
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
                    <folder source="assets\core\meshes\common" destination="" priority="1"/>
					<folder source="assets\core\meshes\new" destination="" priority="1"/>
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
                    <folder source="patches\Hearthfire_Crispy_Dumplings\new" destination="" priority="7"/>
                </files>
            </pattern>
			<pattern>
                <dependencies operator="And">
                    <flagDependency flag="WindhelmBSO-LOS2" value="active"/>
				</dependencies>
                <files>
                    <folder source="patches\Windhelm_Braziers_BSO-LOS2" destination="" priority="7"/>
                </files>
            </pattern>
		</patterns>
    </conditionalFileInstalls>
</config>
"""#
