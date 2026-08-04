# PCCOOLER-LCD Control 3.0.0 Beta 4

Beta 4 focuses on smoother, more consistent GIF playback.

## New GIF defaults

```fish
pccooler-lcd-control play-gif animation.gif
```

The defaults now use:

```text
32 palette colors
1-frame queue
0 PNG compression
100 ms minimum delay
1.5% visual-difference threshold
```

More aggressive frame merging:

```fish
pccooler-lcd-control play-gif animation.gif   --difference-threshold 0.03   --minimum-frame-duration 0.08
```

More color quality:

```fish
pccooler-lcd-control play-gif animation.gif --palette-colors 64
```

## Upload to GitHub

Copy this release into the existing repository while preserving `.git`, then:

```fish
git add .
git commit -m "Improve GIF playback performance"
git push origin main
```

## Arch Linux

```fish
makepkg -Csi
```

## Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windowsuild-windows.ps1
```
