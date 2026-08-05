# Changelog

## 3.0.0 Beta 14 — Native Media Startup

### Added
- Long-loop MP4 preparation with `-stream_loop -1`.
- `media-loop-prepare` command.
- `native-media-activate` command with dry-run protection.
- Persistent local state describing the most recent native-media upload.
- `native-media-status` and `native-media-clear-state`.

### Confirmed behavior
- Uploaded MP4 files persist on the CP3.
- The CP3 plays the uploaded MP4 after reboot.
- Native playback is smooth because the CP3 decodes the file locally.

### Remaining limitation
- The Windows command that enables looping and hardware-info overlays
  has not yet been recovered.
- Beta 14 temporarily works around the missing loop command by creating
  one long repeated MP4.
