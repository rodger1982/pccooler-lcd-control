# Changelog

## 3.0.0 Beta 10

### Added
- Real `play-video` command for full-screen video testing.
- Separate media FPS and widget-refresh timing for animated layouts.

### Changed
- Full-screen video defaults to the measured stable rate of 1.6 FPS.
- Animated layouts cache telemetry and refresh widgets independently.
- Media backgrounds can advance between widget-stat updates.

### Known limitation
The CP3 still accepts only about 2.19 complete 320×240 frames per second.
Beta 10 removes software coupling between media and widgets, but cannot exceed
the measured device full-frame transfer limit.
