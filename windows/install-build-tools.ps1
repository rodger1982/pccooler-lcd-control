$ErrorActionPreference = "Stop"

function Install-WingetPackage {
    param([string]$Id)
    $Installed = winget list --id $Id --exact 2>$null
    if ($LASTEXITCODE -ne 0) {
        winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
    }
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget is required. Install or update Microsoft App Installer."
}

Install-WingetPackage "Python.Python.3.12"
Install-WingetPackage "Gyan.FFmpeg"
Install-WingetPackage "JRSoftware.InnoSetup"

Write-Host ""
Write-Host "Prerequisites installed. Close this PowerShell window,"
Write-Host "open a new PowerShell window, and run:"
Write-Host "  .\windows\build-windows.ps1"
