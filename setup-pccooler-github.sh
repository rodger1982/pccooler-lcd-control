#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .git ]]; then
  echo "Run this script from the root of the pccooler-lcd-control Git repository." >&2
  exit 1
fi

mkdir -p .github/ISSUE_TEMPLATE

cat > .github/ISSUE_TEMPLATE/bug_report.yml <<'EOF'
name: Bug report
description: Report a reproducible problem with PCCOOLER-LCD Control
title: "[Bug]: "
labels: ["bug", "needs-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thank you for helping improve PCCOOLER-LCD Control.

  - type: dropdown
    id: platform
    attributes:
      label: Operating system
      options:
        - Arch Linux
        - Other Linux distribution
        - Windows 11
        - Windows 10
        - Other
    validations:
      required: true

  - type: input
    id: version
    attributes:
      label: Application version
      placeholder: "Example: 3.0.0-beta2"
    validations:
      required: true

  - type: input
    id: device
    attributes:
      label: LCD device
      placeholder: "Example: PCCOOLER DC360 CP3 1d6b:0112"
    validations:
      required: true

  - type: textarea
    id: problem
    attributes:
      label: What happened?
      description: Describe the problem and what you expected instead.
    validations:
      required: true

  - type: textarea
    id: reproduce
    attributes:
      label: Steps to reproduce
      placeholder: |
        1. Open...
        2. Select...
        3. Click...
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Logs or terminal output
      render: shell

  - type: textarea
    id: additional
    attributes:
      label: Additional context
EOF

cat > .github/ISSUE_TEMPLATE/feature_request.yml <<'EOF'
name: Feature request
description: Suggest an improvement or new capability
title: "[Feature]: "
labels: ["enhancement", "needs-triage"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem or use case
      description: What are you trying to accomplish?
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed solution
      description: Describe how you think the feature should work.
    validations:
      required: true

  - type: dropdown
    id: area
    attributes:
      label: Area
      options:
        - Screen Designer
        - Theme Studio
        - Widgets
        - GIF or video playback
        - Linux packaging
        - Windows packaging
        - Device communication
        - Other
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
EOF

cat > .github/ISSUE_TEMPLATE/config.yml <<'EOF'
blank_issues_enabled: false
contact_links:
  - name: Questions and ideas
    url: https://github.com/rodger1982/pccooler-lcd-control/discussions
    about: Ask questions or discuss ideas that are not confirmed bugs.
EOF

cat > .github/pull_request_template.md <<'EOF'
## Summary

Describe the change and why it is needed.

## Testing

- [ ] Tested on Linux
- [ ] Tested on Windows
- [ ] Existing layouts still load
- [ ] The application starts successfully
- [ ] Relevant command-line functions still work

## Screenshots or logs

Add screenshots, terminal output, or build logs when useful.

## Checklist

- [ ] I kept Linux and Windows compatibility in mind
- [ ] I updated documentation where needed
- [ ] I did not commit build output, virtual environments, or secrets
EOF

cat > CONTRIBUTING.md <<'EOF'
# Contributing

Thank you for contributing to PCCOOLER-LCD Control.

## Development workflow

1. Fork or clone the repository.
2. Create a focused branch:
   ```bash
   git switch -c fix/descriptive-name
   ```
3. Make and test the change.
4. Commit with a clear message.
5. Push the branch and open a pull request.

## Linux setup

On Arch Linux:

```bash
makepkg -Csi
```

Run from the installed package:

```bash
pccooler-lcd-control
```

## Windows setup

Use 64-bit Python 3.12 and PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\run-development.ps1
```

Build the portable application and installer:

```powershell
.\windows\build-windows.ps1
```

## Reporting bugs

Include:

- Operating system
- Application version
- LCD model and USB/COM details
- Exact steps to reproduce
- Terminal output or service logs
- Relevant layout file when possible

## Code style

Keep platform-specific code isolated. Shared rendering, layout, and theme code
should remain usable on both Linux and Windows.
EOF

cat > SECURITY.md <<'EOF'
# Security Policy

Please do not publish sensitive security reports as public issues.

For a potential security vulnerability, contact the repository owner privately
through GitHub. Include reproduction steps, affected versions, and the expected
impact.

Do not include passwords, access tokens, private layout content, or personal
system information in public reports.
EOF

cat > CODE_OF_CONDUCT.md <<'EOF'
# Code of Conduct

Be respectful, constructive, and patient.

Harassment, personal attacks, discrimination, and intentionally disruptive
behavior are not acceptable. Focus discussion on the project, the technical
problem, and possible solutions.

Project maintainers may edit or remove content and restrict participation when
necessary to keep the community safe and productive.
EOF

cat > ROADMAP.md <<'EOF'
# Roadmap

## 3.0 Beta stabilization

- [ ] Reliable Arch Linux package build
- [ ] Reliable Windows portable build
- [ ] Reliable Windows Setup installer
- [ ] Startup-layout persistence
- [ ] Device reconnect and port ownership handling
- [ ] GIF and MP4 playback performance
- [ ] Layout migration and compatibility tests

## Designer improvements

- [ ] Resize handles
- [ ] Snap-to-grid
- [ ] Alignment guides
- [ ] Undo and redo
- [ ] Layer ordering
- [ ] Layout thumbnails
- [ ] Drag media directly onto the canvas

## Theme Studio

- [ ] One-click contrast themes
- [ ] Palette preview
- [ ] Color accessibility warnings
- [ ] Theme import and export
- [ ] Font and icon controls

## Widget library

- [ ] Additional disk widgets
- [ ] Network upload/download widgets
- [ ] GPU memory
- [ ] Sensor history
- [ ] Circular gauges
- [ ] Custom text and image improvements
- [ ] Klipper integration

## Distribution

- [ ] GitHub Releases
- [ ] AUR package
- [ ] AppImage
- [ ] Windows signed installer
EOF

cat > RELEASE_CHECKLIST.md <<'EOF'
# Release Checklist

- [ ] Update the version in `pyproject.toml`
- [ ] Update `PKGBUILD`
- [ ] Update application `__version__`
- [ ] Confirm Linux application starts
- [ ] Confirm Windows application starts
- [ ] Test device scan and image transfer
- [ ] Test saved startup layout
- [ ] Test static image, GIF, and MP4 backgrounds
- [ ] Run GitHub Actions successfully
- [ ] Tag the release
- [ ] Verify GitHub release artifacts
EOF

if command -v gh >/dev/null 2>&1; then
  gh repo edit rodger1982/pccooler-lcd-control \
    --description "Cross-platform Qt control, media playback, and visual layout design for PCCOOLER CP3 LCD displays" \
    --enable-issues \
    --enable-discussions \
    --enable-projects

  gh repo edit rodger1982/pccooler-lcd-control \
    --add-topic pccooler \
    --add-topic lcd \
    --add-topic qt \
    --add-topic python \
    --add-topic linux \
    --add-topic windows \
    --add-topic hardware-monitoring
else
  echo "GitHub CLI was not found. Files were created, but repository settings were not changed."
fi

echo
echo "GitHub project files created."
echo "Review them, then run:"
echo "  git add ."
echo '  git commit -m "Add project documentation and GitHub templates"'
echo "  git push origin main"
