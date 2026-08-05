# PCCOOLER Project Workspace

The folder **`pccooler-project`** is now the Git repository root.

The installed application, Python package, CLI command, and systemd unit keep their existing names for compatibility:

- Application: `PCCOOLER-LCD Control`
- CLI: `pccooler-lcd-control`
- Python package: `pccooler_lcd`
- User service: `pccooler-lcd-control.service`

Historical files are stored under `archive/` and are intentionally excluded from Git.

This workspace has been reorganized so the active Git repository is separate
from releases, build products, patches, and historical snapshots.

## Active development

`pccooler-lcd-control/`

This is the only Git repository and should be the normal working directory.
It preserves the `feature/device-reset` branch and its uncommitted changes.

Typical workflow:

```fish
cd pccooler-lcd-control
git status
pytest
makepkg -Csi
```

## Folder layout

- `pccooler-lcd-control/` — active source and Git history
- `archive/releases/zips/` — packaged historical beta releases
- `archive/releases/source-snapshots/` — extracted historical beta source trees
- `archive/artifacts/arch-packages/` — built Arch Linux packages
- `archive/artifacts/build-output/` — generated `build`, `dist`, `pkg`, and `src` trees
- `archive/patches/` — standalone patch archives
- `archive/legacy/` — duplicate or obsolete project copies retained for safety

## Recommended Git workflow

Use feature branches for one subsystem at a time:

```fish
git switch main
git pull
git switch -c feature/name
```

Before committing:

```fish
git status
git diff
pytest
```

Then:

```fish
git add app tests README.md
git commit -m "Describe focused change"
git push -u origin HEAD
```

## Release workflow

Do not copy extracted releases beside the repository. Build releases into
`dist/`, tag them in Git, and move final archives to `archive/releases/zips/`.
