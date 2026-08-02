$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv-win")) { py -3.12 -m venv .venv-win }
& .\.venv-win\Scripts\python.exe -m pip install -e .
& .\.venv-win\Scripts\pccooler-lcd-control.exe
