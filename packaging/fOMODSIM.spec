# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller — fOMODSIM (macOS .app)
# Utilisé par scripts/build_app.sh (chemins résolus depuis la racine du projet).
import os

block_cipher = None

# SPECPATH est injecté par PyInstaller (dossier contenant ce .spec : packaging/)
project_dir = os.path.abspath(os.path.join(SPECPATH, '..'))
assets_dir = os.path.join(project_dir, 'assets')
icon_path = os.path.join(assets_dir, 'icon.icns')

a = Analysis(
    [os.path.join(project_dir, 'python_app', 'main.py')],
    pathex=[project_dir, os.path.join(project_dir, 'python_app')],
    binaries=[],
    datas=[
        (icon_path, 'assets'),
        (os.path.join(assets_dir, 'icon.png'), 'assets'),
    ],
    hiddenimports=[
        'py7zr',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'python_app',
        'python_app.locales',
        'python_app.locales.fr',
        'python_app.locales.en',
        'python_app.locales.it',
        'python_app.locales.es',
        'python_app.fomod',
        'python_app.fomod.types',
        'python_app.fomod.parser',
        'python_app.fomod.extractor',
        'python_app.fomod.staging',
        'python_app.fomod.demo_mod',
        'python_app.gui',
        'python_app.gui.main_window',
        'python_app.gui.theme',
        'python_app.gui.workers',
        'python_app.gui.mod_info_dialog',
        'python_app.gui.modals',
        'python_app.gui.preview_generator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fOMODSIM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fOMODSIM',
)

# Configuration Bundle macOS (.app) avec Icône personnalisée
app = BUNDLE(
    coll,
    name='fOMODSIM.app',
    icon=icon_path,
    bundle_identifier='com.skyrimtools.fomodsimulator',
    info_plist={
        'CFBundleName': 'fOMODSIM',
        'CFBundleDisplayName': 'fOMODSIM',
        'CFBundleIdentifier': 'com.skyrimtools.fomodsimulator',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'CFBundleIconFile': 'icon.icns',
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': 'False',
        'NSHumanReadableCopyright': 'Copyright © 2026 Skyrim Tools. All rights reserved.',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Skyrim Mod Archive',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'CFBundleTypeExtensions': ['zip', '7z', 'rar'],
            }
        ],
    },
)
