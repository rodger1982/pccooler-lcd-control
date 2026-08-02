# PCCOOLER-LCD Control 2.0.0 Alpha 17

This release replaces the GTK Theme Studio with a Qt 6 designer built with
PySide6.

## New Qt interface

Launch:

```fish
pccooler-lcd-control
```

The legacy command now opens the same Qt interface:

```fish
pccooler-lcd-studio
```

The Qt designer includes:

- Modern dark interface
- Dockable Widget Library
- Proper graphics-scene design canvas
- Drag-to-position widgets
- Rubber-band selection
- Ctrl+mouse-wheel zoom
- Dockable Properties panel
- Per-widget border and graph toggles
- Native Qt color picker
- Dockable Theme Studio
- Wallpaper and GIF selection
- High-contrast palette generation
- Global border and graph controls
- Live rendered preview
- Send preview directly to the LCD
- Start and stop custom layout dashboards
- Save and open JSON layouts

## Installation

```fish
makepkg -Csi
```

Arch dependency:

```text
pyside6
```

The CLI, transport, layout renderer, GIF pipeline, and JSON layout format remain
compatible with previous 2.0 alpha releases.


## Alpha 9 packaging fix

The Qt package directory was present in the source tree but omitted from the
Python wheel because setuptools was configured to include only the top-level
`pccooler_lcd` package. Alpha 9 uses recursive package discovery and includes
`pccooler_lcd.qt` plus future subpackages automatically.


## Alpha 10 compact widget fix

Disk and network widgets now use compact layout rules:

- Small boxes show the value only.
- Taller boxes reserve a separate label row.
- Text automatically shrinks and wraps within the available space.
- Labels no longer overlap disk or network values.


## Alpha 11 display modes and GIF backgrounds

CPU and GPU widgets now have independent controls for:

- Show percentage
- Show temperature
- Show graph/bar

Memory widgets have:

- Show percentage
- Show used/total GB
- Show graph/bar

The Qt preview now decodes and animates GIF backgrounds instead of displaying
only a static frame. Starting a custom layout uses a faster 0.18-second refresh
interval and enables GIF timing automatically.


## Alpha 12 labels and GIF service performance

- Fixes duplicate labels on disk and network widgets.
- Adds a per-widget **Show label** toggle in the Qt Properties panel.
- Animated layout backgrounds can now use `--optimized-gif`.
- Optimized mode pre-renders and caches every composed layout frame.
- A dedicated sender thread and adaptive frame skipping keep GIF playback from
  falling progressively behind.
- Starting an animated layout from Qt enables optimized GIF mode automatically.


## Alpha 13 multi-layout library

The Qt application now includes a dockable **Layouts** library.

Layouts are stored under:

```text
~/.config/pccooler-lcd-control/layouts/
```

You can:

- Save multiple named layouts
- Double-click a layout to load it
- Duplicate the current layout
- Rename saved layouts
- Delete layouts
- Save As to any custom path
- Keep the currently active layout selected while editing


## Alpha 14 startup fix

The Alpha 13 layout-library insertion accidentally dedented several methods
outside the Qt `MainWindow` class. Alpha 14 restores the layout-library,
selection, property, preview, dashboard, and save callbacks to `MainWindow`.


## Alpha 15 startup layout persistence

The Layouts panel now includes **Set Startup**.

The selected layout is saved in:

```text
~/.config/pccooler-lcd-control/startup.json
```

On login, the systemd user service now runs:

```fish
pccooler-lcd startup-dashboard
```

This loads the selected layout, including GIF background settings, instead of
starting the default dashboard. The active startup layout is marked with a star
in the Layouts panel.


## Alpha 16 MP4 and video support

The CP3 display does not decode MP4 directly. PCCOOLER-LCD Control now uses
FFmpeg to decode video on the PC, resize it to 320×240, and stream the frames
through the existing CP3 image protocol.

### Full-screen MP4

```fish
pccooler-lcd play-video video.mp4 --fps 8
```

### MP4 as a layout background

Choose an MP4 in the Qt wallpaper picker and set the type to **MP4 / Video**.
Starting or selecting it as the startup layout uses the video-background
pipeline automatically.

```fish
pccooler-lcd video-layout-dashboard layout.json --fps 6
```

The default is 6 FPS for composed dashboards and 8 FPS for full-screen video.
The actual rate depends on PNG size and the CP3 controller's upload speed.


## Alpha 17 Windows support

PCCOOLER-LCD Control now supports Windows USB serial/COM-port discovery. The same CP3 transport and Qt designer are used on Linux and Windows.

### Build the Windows app

On a Windows 10/11 x64 computer with Python 3.12 installed:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build-windows.ps1
```

The standalone application is created at:

```text
dist\PCCOOLER-LCD-Control\PCCOOLER-LCD-Control.exe
```

The app automatically finds the CP3 USB Serial Device by VID/PID, such as `COM4`. No CP3 application is required. Close CP3 first so only one program owns the COM port.

MP4 support uses FFmpeg. Place `ffmpeg.exe` and `ffprobe.exe` beside the app or install FFmpeg in PATH before building.
