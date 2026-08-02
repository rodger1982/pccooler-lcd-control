from __future__ import annotations

import os
import sys
from pathlib import Path


APP_SLUG = "pccooler-lcd-control"


def config_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
        root = base / "PCCOOLER-LCD Control"
    else:
        root = Path(
            os.environ.get(
                "XDG_CONFIG_HOME",
                Path.home() / ".config",
            )
        ) / APP_SLUG
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_tree() -> dict[str, Path]:
    root = config_root()
    paths = {
        "root": root,
        "settings": root / "settings.json",
        "startup": root / "startup.json",
        "layouts": root / "layouts",
        "themes": root / "themes",
        "widgets": root / "widgets",
        "plugins": root / "plugins",
        "media": root / "media",
        "images": root / "media" / "images",
        "gifs": root / "media" / "gifs",
        "videos": root / "media" / "videos",
        "cache": root / "cache",
        "logs": root / "logs",
    }
    for key, path in paths.items():
        if key not in ("settings", "startup"):
            path.mkdir(parents=True, exist_ok=True)
    return paths
