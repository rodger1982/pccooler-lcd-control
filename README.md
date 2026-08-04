<p align="center">
  <img src="assets/branding/github-banner.png" alt="PCCOOLER-LCD Control banner">
</p>

# PCCOOLER-LCD Control 3.0.0 Beta 8

Beta 8 fixes dashboard lifecycle behavior and adds a transfer benchmark.

## Closing the GUI

Closing the editor no longer stops the startup service or a running dashboard.
Use the **Stop** button only when you intentionally want to stop a dashboard
started by that GUI window.

## Measure actual display speed

Stop the service first:

```fish
systemctl --user stop pccooler-lcd-control.service
```

Run:

```fish
pccooler-lcd-control benchmark-transfer \
  --frames 10 \
  --png-compression 9 \
  --chunk-delay 0.003 \
  --timeout 10 \
  --retries 5
```

The command reports the realistic maximum full-frame FPS and a recommended
stable animation FPS. Because GIF and MP4 playback currently sends complete
320×240 frames, it cannot exceed the measured device transfer/processing limit
without a different native or partial-frame protocol.
