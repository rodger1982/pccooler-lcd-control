#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v makepkg >/dev/null 2>&1; then
    echo "This installer targets Arch Linux and requires makepkg." >&2
    exit 1
fi

makepkg -Csi

systemctl --user disable --now pccooler-lcd.service 2>/dev/null || true
systemctl --user daemon-reload

echo
echo "Installed PCCOOLER-LCD Control."
echo "Launch with: pccooler-lcd-control"
echo
echo "To start the selected layout automatically:"
echo "  systemctl --user enable --now pccooler-lcd-control.service"
