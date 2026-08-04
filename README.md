# PCCOOLER-LCD Control 3.0.0 Beta 10

Beta 10 adds full-screen video playback and separates media timing from widget
refresh timing.

## Full-screen video test

```fish
systemctl --user stop pccooler-lcd-control.service

pccooler-lcd-control play-video ~/Pictures/pccooler-images/video.mp4 \
  --fps 1.6 \
  --palette-colors 32 \
  --png-compression 9 \
  --chunk-delay 0.003 \
  --retries 5 \
  --timeout 10
```

## Animated layout

```fish
pccooler-lcd-control media-layout-dashboard layout.json \
  --media-fps 1.6 \
  --widget-refresh 1.0
```

Media frames and telemetry are now timed independently. The video background
can advance without recollecting CPU/GPU/RAM statistics for every frame.
