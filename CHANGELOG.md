# Changelog

## 3.0.0 Beta 13 — Protocol Lab

### Added
- Protocol recorder for TX, RX, and file-data events.
- Human-readable CP3 packet decoder.
- Protocol trace viewer with compact summary mode.
- Guarded packet replay for non-file request packets.
- Rate-limited protocol probing from a candidate-method file.
- Confirmed/unknown protocol command catalog.
- JSON session traces for `protocol-request`.
- Protocol test fixtures and candidate read-only method list.

### Safety
- Replay ignores file-transfer packets.
- Probing is dry-run unless `--execute` is provided.
- Probing stops after a configurable number of consecutive failures.
- No destructive media-delete or reset guesses are included.
