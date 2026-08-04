<p align="center">
  <img src="assets/branding/github-banner.png" alt="PCCOOLER-LCD Control banner">
</p>

# PCCOOLER-LCD Control 3.0.0 Beta 9

Beta 9 fixes the unified launcher so the transfer benchmark command can
run normally.

```fish
systemctl --user stop pccooler-lcd-control.service

pccooler-lcd-control benchmark-transfer \
  --frames 10 \
  --png-compression 9 \
  --chunk-delay 0.003 \
  --timeout 10 \
  --retries 5
```

The benchmark reports:

- average PNG payload size,
- average frame transfer time,
- measured maximum full-frame FPS,
- recommended stable animation FPS.

GIF and MP4 playback still transfers complete 320×240 frames. Native
or partial-frame protocol support would be required to exceed the
measured device limit.
