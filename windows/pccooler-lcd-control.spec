# Optional PyInstaller spec. The supported build path is windows/build-windows.ps1.
from pathlib import Path

project_root = Path.cwd()
entry = project_root / "windows" / "windows_entry.py"
app_path = project_root / "app"
themes = project_root / "themes"

if not entry.is_file():
    raise FileNotFoundError(f"Run PyInstaller from the repository root; missing {entry}")

a = Analysis(
    [str(entry)],
    pathex=[str(app_path)],
    binaries=[],
    datas=[(str(themes), "themes")],
    hiddenimports=[
        "pccooler_lcd.unified",
        "pccooler_lcd.cli",
        "pccooler_lcd.qt.app",
        "pccooler_lcd.qt.main_window",
        "pccooler_lcd.qt.canvas",
    ],
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
    icon=str(project_root / "assets" / "icons" / "pccooler-lcd-control.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="PCCOOLER-LCD-Control",
)
