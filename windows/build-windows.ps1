$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.11+ from python.org."
}

if (-not (Test-Path ".venv-win")) {
    py -3.12 -m venv .venv-win
}

& .\.venv-win\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-win\Scripts\python.exe -m pip install -r windows\requirements-windows.txt
& .\.venv-win\Scripts\python.exe -m pip install .

$ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
$extra = @()
if ($ffmpeg -and $ffprobe) {
    $extra += @("--add-binary", "$($ffmpeg.Source);.")
    $extra += @("--add-binary", "$($ffprobe.Source);.")
} else {
    Write-Warning "FFmpeg was not found. The EXE will work, but MP4 support requires ffmpeg.exe and ffprobe.exe in PATH or beside the EXE."
}

& .\.venv-win\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --name "PCCOOLER-LCD-Control" `
    --collect-all PySide6 `
    --collect-submodules pccooler_lcd `
    @extra `
    windows\windows_entry.py

Write-Host "Build complete: dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe"
