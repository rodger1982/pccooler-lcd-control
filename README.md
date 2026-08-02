# PCCOOLER-LCD Control 3.0.0 Beta 1

Cross-platform control, media playback, and visual layout design for PCCOOLER
CP3 LCD displays.

The same repository supports:

- Arch Linux packages
- Linux systemd user startup
- Windows portable application builds
- Windows Setup installers
- Windows COM-port discovery
- Linux `/dev/ttyACM*` discovery
- Image, GIF, and MP4 backgrounds
- Layout and widget libraries
- Qt screen designer
- Startup-layout persistence

## Linux installation

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

Enable the startup-layout service:

```fish
systemctl --user enable --now pccooler-lcd-control.service
```

## Windows installer build

In PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\install-build-tools.ps1
```

Open a new PowerShell window, then:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build-windows.ps1
```

The finished installer is:

```text
dist\PCCOOLER-LCD-Control-Setup.exe
```

End users install that file normally and do not need to install Python.

## GitHub automated builds

The `.github/workflows` directory includes Windows and Arch Linux build
workflows. See [BUILDING.md](BUILDING.md) for full instructions.

## Existing users

The compatibility command remains:

```text
pccooler-lcd
```

The primary command and desktop application are:

```text
pccooler-lcd-control
```
