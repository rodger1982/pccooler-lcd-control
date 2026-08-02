# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil

project_root = Path(SPECPATH).parent.parent
datas = [
    (str(project_root / "themes"), "themes"),
]

binaries = []
for executable in ("ffmpeg.exe", "ffprobe.exe"):
    location = shutil.which(executable)
    if location:
        binaries.append((location, "."))

hiddenimports = [
    "pccooler_lcd.unified",
    "pccooler_lcd.cli",
    "pccooler_lcd.qt.app",
    "pccooler_lcd.qt.main_window",
    "pccooler_lcd.qt.canvas",
]

a = Analysis(
    [str(project_root / "windows" / "windows_entry.py")],
    pathex=[str(project_root / "app")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["gi"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PCCOOLER-LCD-Control",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="PCCOOLER-LCD-Control",
)
