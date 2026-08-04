# Changelog

## 3.0.0 Beta 4

- Added perceptual GIF frame-difference detection.
- Merges visually similar frames instead of uploading each one.
- Changed GIF defaults to 32 colors, zero PNG compression, one queued frame,
  and a 100 ms minimum frame delay.
- Added `--difference-threshold` and `--minimum-frame-duration`.
- Added tests for frame-difference scoring.

The display still receives full 320×240 images, so native high-frame-rate
animation remains limited by the CP3 transfer protocol.
