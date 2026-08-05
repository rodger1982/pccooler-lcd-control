# Development Workflow

## Source of truth

The Git repository is the only editable source tree. Historical beta folders
and generated build output must not be edited directly.

## Branches

- `main`: stable, reviewed work
- `feature/*`: one focused subsystem or fix
- `release/*`: release preparation only when needed

## Before testing the LCD

Stop the user service so the serial port is not held:

```fish
systemctl --user stop pccooler-lcd-control.service
```

Check ownership:

```fish
sudo fuser -v /dev/ttyACM0
```

## Generated directories

The following are ignored and safe to regenerate:

```text
build/
dist/
pkg/
src/
```

## Protocol experiments

Keep confirmed protocol facts in `docs/protocol/`. Put raw traces under a local
ignored folder or attach them to an issue; do not mix guesses with confirmed
commands.
