from __future__ import annotations

from pathlib import Path
from serial.tools import list_ports

from .platform import default_device

VID = 0x1D6B
PID = 0x0112


def scan_devices():
    return [
        port for port in list_ports.comports()
        if port.vid == VID and port.pid == PID
    ]


def resolve_device(preferred: str | None = None) -> str:
    selected = preferred if preferred not in (None, "", "auto") else default_device()
    if selected:
        path = Path(selected)
        if path.exists():
            return str(path.resolve())
        # COM4 and similar Windows device names are not filesystem paths.
        if selected.upper().startswith("COM"):
            return selected

    devices = scan_devices()
    if devices:
        return devices[0].device
    raise FileNotFoundError(
        "PCCOOLER CP3 device 1d6b:0112 not found. "
        "On Windows, confirm it appears as a USB Serial Device (COM port)."
    )
