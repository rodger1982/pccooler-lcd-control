<p align="center">
  <img src="assets/branding/github-banner.png" alt="PCCOOLER-LCD Control banner">
</p>

# PCCOOLER-LCD Control

A modern cross-platform dashboard, theme studio, media player, and visual layout
designer for **PCCOOLER CP3 USB LCD displays**.

> This is an independent community project and is not affiliated with or endorsed by PCCOOLER.

## Highlights

- Linux and Windows support
- 320×240 visual screen designer
- CPU, GPU, RAM, disk, network, clock, date, uptime, and media widgets
- Multiple saved layouts and startup-layout selection
- Wallpaper-aware contrast themes
- PNG, JPEG, BMP, WebP, GIF, MP4, MOV, WebM, MKV, and AVI backgrounds
- Arch Linux package and Windows installer builds
- Unified Qt 6 interface

## Supported hardware

```text
USB VID:PID: 1d6b:0112
Manufacturer: CP3 Inc.
Product: CP3 USB Device
Display: 320×240
Transport: CDC ACM serial
```

Developed with the 2.4-inch LCD used by the PCCOOLER DC360 360 mm AIO.

## Arch Linux

```fish
git clone https://github.com/rodger1982/pccooler-lcd-control.git
cd pccooler-lcd-control
makepkg -Csi
pccooler-lcd-control
```

Enable startup:

```fish
systemctl --user enable --now pccooler-lcd-control.service
```

## Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build-windows.ps1
```

Outputs:

```text
dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe
dist\installer\PCCOOLER-LCD-Control-Setup.exe
```

## Examples

```fish
pccooler-lcd-control scan
pccooler-lcd-control send-image image.png
pccooler-lcd-control play-gif animation.gif
pccooler-lcd-control startup-dashboard
```

## Configuration

Linux: `~/.config/pccooler-lcd-control/`

Windows: `%APPDATA%\PCCOOLER-LCD Control\`

## Known media limitation

GIF and video playback currently transfers complete 320×240 frames. Playback
speed depends on compressed frame size and CP3 response time. Native video
playback remains an active reverse-engineering goal.

## Documentation

- [Build instructions](BUILDING.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)

## License

MIT License.
