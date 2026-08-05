<p align="center">
  <img src="assets/branding/github-banner.png" alt="PCCOOLER-LCD Control banner">
</p>

# PCCOOLER-LCD Control 3.0.0 Beta 14

Beta 14 adds a practical native-media startup workflow.

The CP3 has now been confirmed to store and decode uploaded MP4 files locally.
This provides smooth video playback without streaming PNG frames.

## Prepare a one-hour repeated MP4

```fish
pccooler-lcd-control media-loop-prepare \
  ~/Pictures/pccooler-images/4-3.mp4 \
  --output ~/Pictures/pccooler-images/4-3-cp3-loop.mp4 \
  --duration-minutes 60
```

## Prepare, upload, and activate

Dry run:

```fish
pccooler-lcd-control native-media-activate \
  ~/Pictures/pccooler-images/4-3.mp4 \
  --duration-minutes 60
```

Execute:

```fish
systemctl --user stop pccooler-lcd-control.service

pccooler-lcd-control native-media-activate \
  ~/Pictures/pccooler-images/4-3.mp4 \
  --duration-minutes 60 \
  --remote-name startup.mp4 \
  --execute \
  --verbose \
  --trace /tmp/native-media-upload.json
```

Power-cycle the CP3 if playback does not start immediately.

## Show the recorded state

```fish
pccooler-lcd-control native-media-status
```

## Important limitation

The official Windows application sends additional commands that restore
hardware-info overlays and true looping. Those commands are not yet recovered.

Beta 14 creates one long repeated MP4 as a temporary workaround. It does not
claim to reproduce the Windows overlay behavior yet.

## Device inspection and USB reset

Inspect the detected CP3 and its Linux USB path:

```fish
pccooler-lcd-control inspect-device
```

Reset an internally connected CP3 without unplugging it:

```fish
systemctl --user stop pccooler-lcd-control.service
pccooler-lcd-control reset-device --sudo
```

The reset command resolves the serial port to its parent USB device and verifies
that its VID/PID is `1d6b:0112` before changing the sysfs `authorized` state. It
refuses to reset an unrelated USB device and refuses to continue while the
serial port is owned by another process.

