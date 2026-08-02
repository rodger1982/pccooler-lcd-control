$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv-win")) {
    py -3.12 -m venv .venv-win
}

$Python = Join-Path $ProjectRoot ".venv-win\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r windows\requirements-windows.txt
& $Python -m pip install -e .
& $Python -m pccooler_lcd.unified
