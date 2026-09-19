# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Full Thrust Fleet Manager.

Build (from the project root, with requirements-dev.txt installed):
    pyinstaller fleetmanager.spec

Onedir build at dist/FullThrustFleetManager/: faster cold start than onefile, which re-extracts
everything on every launch. The desktop build must work fully offline, so everything the app
reads at runtime is bundled here, including the rulebook PDFs.
"""

from pathlib import Path

block_cipher = None

# Folders are added whole and data/ is globbed, never hand-listed: Frostgrave's hand-kept lists
# drifted from its browser bundle and shipped broken twice. User data lives in
# paths.user_data_dir() and is never bundled.
datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("translations", "translations"),
    ("rulebooks", "rulebooks"),
    ("pyproject.toml", "."),
] + [
    (str(p), str(p.parent)) for p in sorted(Path("data").rglob("*.json"))
]

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["waitress", "pystray", "pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FullThrustFleetManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    upx=False,
    upx_exclude=[],
    name="FullThrustFleetManager",
)
