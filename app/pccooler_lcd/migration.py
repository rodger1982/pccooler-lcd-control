from __future__ import annotations

import shutil
from pathlib import Path

from .paths import ensure_tree


def migrate_legacy_config() -> list[str]:
    messages = []
    target = ensure_tree()
    legacy_root = Path.home() / ".config" / "pccooler-lcd-control"

    # Current path is already the canonical location on Linux. This function
    # also supports earlier ad-hoc layout folders.
    candidates = [
        Path.home() / ".config" / "pccooler-lcd" / "layouts",
        Path.home() / "Documents" / "pccooler-layouts",
    ]

    for source in candidates:
        if not source.is_dir():
            continue
        for item in source.glob("*.json"):
            destination = target["layouts"] / item.name
            if not destination.exists():
                shutil.copy2(item, destination)
                messages.append(f"Migrated {item.name}")
    return messages
