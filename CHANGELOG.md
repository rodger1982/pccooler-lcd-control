# Changelog

## 3.0.0 Beta 5

### Fixed
- Widget panel colors are never treated as media filenames.
- Missing media no longer opens repeating modal dialogs.
- Failed media paths are remembered instead of retried every 100 ms.
- Layouts remain editable using their fallback background color.
- Static images, GIFs, and videos share the same validation path.
- Image-widget media errors no longer crash rendering.

### Changed
- Missing-media warnings are shown once in the status bar.
- Theme-analysis failures are non-blocking.
