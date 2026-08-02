param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install 64-bit Python 3.12."
}

if (-not (Test-Path ".venv-win")) {
    py -3.12 -m venv .venv-win
}

$Python = Join-Path $ProjectRoot ".venv-win\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r windows\requirements-windows.txt
& $Python -m pip install .

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

& (Join-Path $ProjectRoot ".venv-win\Scripts\pyinstaller.exe") `
    --noconfirm `
    --clean `
    windows\pccooler-lcd-control.spec

$Exe = Join-Path $ProjectRoot "dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller did not create the application executable."
}

Write-Host ""
Write-Host "Portable application built:"
Write-Host "  $Exe"

if ($SkipInstaller) {
    exit 0
}

$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $CommonPaths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($Candidate in $CommonPaths) {
        if (Test-Path $Candidate) {
            $Iscc = Get-Item $Candidate
            break
        }
    }
}

if (-not $Iscc) {
    Write-Warning "Inno Setup was not found. Install it with:"
    Write-Warning "  winget install JRSoftware.InnoSetup"
    Write-Warning "The portable application was still built successfully."
    exit 0
}

& $Iscc.Source windows\installer.iss

Write-Host ""
Write-Host "Windows installer built:"
Write-Host "  dist\installer\PCCOOLER-LCD-Control-Setup.exe"
