# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Linux build of Full Thrust Fleet Manager.

Build (on Linux, with requirements-dev.txt installed):
    pyinstaller fleetmanager-linux.spec

Produces a single onefile binary at dist/FullThrustFleetManager, rather than the Windows build's
onedir: one downloadable file that only needs `chmod +x` is the easiest thing to hand a
non-technical Linux user, where a folder that has to be kept together is one more way to break it.
The slower cold start that onefile costs is worth that.

The tray icon (tray.py) is excluded. app.py's main() only reaches it on win32 anyway, and pystray
would drag in GTK/AppIndicator/X11 backends this build cannot assume are installed. Auto-shutdown
when the browser tab closes (idle_watchdog.py) is cross-platform and covers the same need.
"""

from pathlib import Path

block_cipher = None

# Folders whole, data/ globbed: see fleetmanager.spec for why these are never hand-listed.
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
    hiddenimports=["waitress"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tray", "pystray"],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FullThrustFleetManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
