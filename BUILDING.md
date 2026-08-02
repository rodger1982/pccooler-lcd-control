# Cross-platform builds

PCCOOLER-LCD Control uses one Python/Qt codebase for Linux and Windows.

## Linux / Arch Linux

Install locally:

```fish
./linux/install-arch.sh
```

or:

```fish
makepkg -Csi
```

Launch:

```fish
pccooler-lcd-control
```

Enable startup:

```fish
systemctl --user enable --now pccooler-lcd-control.service
```

## Windows development

Open PowerShell in the project directory.

Install build prerequisites:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\install-build-tools.ps1
```

Close PowerShell and open a new PowerShell window so PATH changes are loaded.

Run from source:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\run-development.ps1
```

## Windows installer

Build the portable application and installer:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build-windows.ps1
```

Outputs:

```text
dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe
dist\installer\PCCOOLER-LCD-Control-Setup.exe
```

The installer bundles Python, Qt, Pillow, pyserial, psutil, the application,
themes, and FFmpeg when FFmpeg is available in PATH.

## GitHub Actions

The repository contains workflows for:

- Windows portable application and installer
- Arch Linux package
- Tagged GitHub releases

Push the files to GitHub, open the **Actions** tab, and run the build workflows.
