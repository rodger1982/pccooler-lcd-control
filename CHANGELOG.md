# Changelog

## 3.0.0 Beta 11

### Added
- Experimental native-media preparation using FFmpeg.
- `media-info` FFprobe inspection command.
- `media-prepare` with the recovered Windows options:
  `yuv420p`, no B-frames, fast-start MP4, even dimensions.
- Guarded `media-upload` command using the confirmed CP3 block-transfer
  envelope. It is dry-run by default and requires `--execute`.
- Generic `protocol-request` command with JSON request/reply trace files.
- Generic non-PNG file transfer support in `CP3Connection`.
- CP3 request-frame inspection and checksum reporting.
- Protocol findings and reverse-engineering bundle under `docs/protocol`.

### Important limitation
The exact media-list and media-select command bodies remain unconfirmed.
A successful experimental file transfer does not yet guarantee that the
display firmware will expose or play the uploaded file.
