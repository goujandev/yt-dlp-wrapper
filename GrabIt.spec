# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for GrabIt.

Produces a single windowed GrabIt.exe in dist/, with ffmpeg.exe bundled inside
when vendor/ffmpeg.exe exists (build.py fetches it for you).

    pyinstaller GrabIt.spec --noconfirm
"""

import os

# SPECPATH is injected by PyInstaller and is the directory holding this spec;
# it is reliable regardless of the working directory the build was started from.
spec_dir = os.path.abspath(SPECPATH)  # noqa: F821

binaries = []
datas = []

# Required: the bundled ffmpeg is GPL, so its notice must ship with the exe.
notices = os.path.join(spec_dir, "THIRD-PARTY-NOTICES.txt")
if os.path.isfile(notices):
    datas.append((notices, "."))
    print(f"Bundling licence notices: {notices}")
else:
    raise SystemExit(
        f"THIRD-PARTY-NOTICES.txt is missing from {spec_dir}. "
        "It must ship with the GPL ffmpeg binary; refusing to build without it."
    )

# App icon: the .ico is stamped into the exe, the .png is loaded at runtime for
# the window and taskbar. build.py generates both from logo.png.
icon_ico = os.path.join(spec_dir, "assets", "GrabIt.ico")
icon_png = os.path.join(spec_dir, "assets", "icon.png")
exe_icon = icon_ico if os.path.isfile(icon_ico) else None
if os.path.isfile(icon_png):
    datas.append((icon_png, "assets"))
if exe_icon is None:
    print("WARNING: assets/GrabIt.ico not found - the exe will use the default icon.")

ffmpeg_exe = os.path.join(spec_dir, "vendor", "ffmpeg.exe")
if os.path.isfile(ffmpeg_exe):
    # Land it at the root of the extraction dir, where ffmpeg_tools looks first.
    binaries.append((ffmpeg_exe, "."))
else:
    print("WARNING: vendor/ffmpeg.exe not found - building without bundled ffmpeg.")

a = Analysis(
    ["run_grabit.py"],
    pathex=[spec_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # yt-dlp resolves extractors lazily; PyInstaller cannot see them.
        "yt_dlp.extractor.lazy_extractors",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim the parts of Qt GrabIt never touches.
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuick3D",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtMultimedia",
        "PyQt6.Qt3DCore",
        "PyQt6.QtCharts",
        "PyQt6.QtDataVisualization",
        "tkinter",
        "test",
        "unittest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GrabIt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app - no console flashes
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)
