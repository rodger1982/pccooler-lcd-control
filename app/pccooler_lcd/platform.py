from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "PCCOOLER-LCD Control"


def config_dir() -> Path:
    """Return the per-user configuration directory on Linux and Windows."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "PCCOOLER-LCD Control"
        return Path.home() / "AppData" / "Roaming" / "PCCOOLER-LCD Control"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "pccooler-lcd-control"


def default_device() -> str | None:
    # Windows COM ports are discovered by VID/PID. Linux prefers the udev link.
    return None if sys.platform == "win32" else "/dev/pccooler-lcd"


def is_windows() -> bool:
    return sys.platform == "win32"
