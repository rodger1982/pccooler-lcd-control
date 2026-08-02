param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install 64-bit Python 3.12."
}

$VenvDir = Join-Path $ProjectRoot ".venv-win"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$PyInstaller = Join-Path $VenvDir "Scripts\pyinstaller.exe"

if (-not (Test-Path $Python)) {
    py -3.12 -m venv $VenvDir
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ProjectRoot "windows\requirements-windows.txt")
& $Python -m pip install $ProjectRoot

Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build"), (Join-Path $ProjectRoot "dist") -ErrorAction SilentlyContinue

$EntryScript = Join-Path $ProjectRoot "windows\windows_entry.py"
$AppPath = Join-Path $ProjectRoot "app"
$ThemesPath = Join-Path $ProjectRoot "themes"
$AddData = "$ThemesPath;themes"

if (-not (Test-Path $EntryScript)) {
    throw "Windows entry script was not found: $EntryScript"
}

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "PCCOOLER-LCD-Control",
    "--paths", $AppPath,
    "--add-data", $AddData,
    "--collect-all", "PySide6",
    "--collect-submodules", "pccooler_lcd",
    $EntryScript
)

$Ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
$Ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
if ($Ffmpeg) {
    $PyInstallerArgs = @("--add-binary", "$($Ffmpeg.Source);.") + $PyInstallerArgs
}
if ($Ffprobe) {
    $PyInstallerArgs = @("--add-binary", "$($Ffprobe.Source);.") + $PyInstallerArgs
}

& $PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Exe = Join-Path $ProjectRoot "dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller did not create the expected executable: $Exe"
}

$PortableZip = Join-Path $ProjectRoot "dist\PCCOOLER-LCD-Control-Windows-x64.zip"
Compress-Archive -Path (Join-Path $ProjectRoot "dist\PCCOOLER-LCD-Control\*") -DestinationPath $PortableZip -Force

Write-Host "Portable application built:"
Write-Host "  $Exe"
Write-Host "Portable archive built:"
Write-Host "  $PortableZip"

if ($SkipInstaller) {
    exit 0
}

$IsccCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$Iscc = $IsccCandidates | Select-Object -First 1
if (-not $Iscc) {
    Write-Warning "Inno Setup was not found. Install it with: winget install JRSoftware.InnoSetup"
    Write-Warning "The portable Windows build was created successfully."
    exit 0
}

& $Iscc (Join-Path $ProjectRoot "windows\installer.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$Installer = Join-Path $ProjectRoot "dist\installer\PCCOOLER-LCD-Control-Setup.exe"
if (-not (Test-Path $Installer)) {
    throw "The installer was not created: $Installer"
}

Write-Host "Windows installer built:"
Write-Host "  $Installer"
