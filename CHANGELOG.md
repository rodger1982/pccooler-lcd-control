# Changelog

## 3.0.0 Beta 8

### Fixed
- Closing the Qt editor no longer stops the dashboard or startup service.
- The Stop button only stops a dashboard process launched by the current GUI.

### Added
- `benchmark-transfer` command to measure actual CP3 full-frame throughput.
- Reports average frame size, transfer time, maximum FPS, and recommended
  stable animation FPS.

### Known limitation
GIF and MP4 playback still transfers complete 320×240 frames. Beta 8 measures
the real device limit but does not add native video decoding.
