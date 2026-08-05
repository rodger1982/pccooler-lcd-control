from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import serial
from serial.tools import list_ports

from .platform import default_device

VID = 0x1D6B
PID = 0x0112
SYS_TTY = Path('/sys/class/tty')


class DeviceResetError(RuntimeError):
    pass


@dataclass(slots=True)
class CP3DeviceInfo:
    serial_device: str
    vid: int | None
    pid: int | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    description: str | None
    usb_sysfs_path: str | None
    usb_bus_path: str | None
    authorized_path: str | None
    connected: bool
    port_in_use: bool | None
    port_users: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def scan_devices():
    return [
        port for port in list_ports.comports()
        if port.vid == VID and port.pid == PID
    ]


def resolve_device(preferred: str | None = None) -> str:
    selected = preferred if preferred not in (None, '', 'auto') else default_device()
    if selected:
        path = Path(selected)
        if path.exists():
            return str(path.resolve())
        # COM4 and similar Windows device names are not filesystem paths.
        if selected.upper().startswith('COM'):
            return selected

    devices = scan_devices()
    if devices:
        return devices[0].device
    raise FileNotFoundError(
        'PCCOOLER CP3 device 1d6b:0112 not found. '
        'On Windows, confirm it appears as a USB Serial Device (COM port).'
    )


def _read_hex(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding='ascii').strip(), 16)
    except (OSError, ValueError):
        return None


def _read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding='utf-8', errors='replace').strip()
        return value or None
    except OSError:
        return None


def _tty_name(serial_device: str) -> str:
    name = Path(serial_device).name
    if not name.startswith('tty'):
        raise DeviceResetError(
            f'Unable to map {serial_device!r} to a Linux tty sysfs entry'
        )
    return name


def find_usb_sysfs_device(serial_device: str) -> Path:
    if sys.platform != 'linux':
        raise DeviceResetError('USB sysfs discovery is only available on Linux')

    tty_link = SYS_TTY / _tty_name(serial_device) / 'device'
    if not tty_link.exists():
        raise DeviceResetError(f'No sysfs entry found for {serial_device}')

    current = tty_link.resolve()
    for candidate in (current, *current.parents):
        vid = _read_hex(candidate / 'idVendor')
        pid = _read_hex(candidate / 'idProduct')
        if vid is not None and pid is not None:
            if (vid, pid) != (VID, PID):
                raise DeviceResetError(
                    f'Refusing to reset USB {vid:04x}:{pid:04x}; '
                    f'expected CP3 {VID:04x}:{PID:04x}'
                )
            return candidate

    raise DeviceResetError(
        f'Could not locate the parent USB device for {serial_device}'
    )


def _port_users(serial_device: str) -> list[str]:
    fuser = shutil.which('fuser')
    if not fuser:
        return []
    result = subprocess.run(
        [fuser, '-v', serial_device],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    output = '\n'.join(part for part in (result.stdout, result.stderr) if part)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines


def _can_open_exclusively(serial_device: str) -> bool | None:
    try:
        port = serial.Serial(
            port=serial_device,
            baudrate=115200,
            timeout=0.1,
            write_timeout=0.5,
            exclusive=True,
        )
    except (serial.SerialException, OSError):
        return False
    else:
        port.close()
        return True


def inspect_device(preferred: str | None = None) -> CP3DeviceInfo:
    serial_device = resolve_device(preferred)
    matched = next(
        (port for port in scan_devices() if port.device == serial_device),
        None,
    )

    usb_path: Path | None = None
    if sys.platform == 'linux':
        try:
            usb_path = find_usb_sysfs_device(serial_device)
        except DeviceResetError:
            usb_path = None

    users = _port_users(serial_device) if sys.platform == 'linux' else []
    exclusive = _can_open_exclusively(serial_device)

    return CP3DeviceInfo(
        serial_device=serial_device,
        vid=matched.vid if matched else VID,
        pid=matched.pid if matched else PID,
        manufacturer=matched.manufacturer if matched else None,
        product=matched.product if matched else None,
        serial_number=matched.serial_number if matched else None,
        description=matched.description if matched else None,
        usb_sysfs_path=str(usb_path) if usb_path else None,
        usb_bus_path=usb_path.name if usb_path else None,
        authorized_path=str(usb_path / 'authorized') if usb_path else None,
        connected=Path(serial_device).exists() if not serial_device.upper().startswith('COM') else True,
        port_in_use=(not exclusive) if exclusive is not None else None,
        port_users=users,
    )


def _write_authorized(path: Path, value: str, use_sudo: bool) -> None:
    if os.access(path, os.W_OK):
        path.write_text(value, encoding='ascii')
        return

    if not use_sudo:
        raise DeviceResetError(
            f'Permission denied writing {path}. Re-run with --sudo or run '
            f'the command as root.'
        )

    sudo = shutil.which('sudo')
    tee = shutil.which('tee')
    if not sudo or not tee:
        raise DeviceResetError('The --sudo option requires sudo and tee')

    result = subprocess.run(
        [sudo, tee, str(path)],
        input=f'{value}\n',
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise DeviceResetError(
            result.stderr.strip() or f'Failed to write {value} to {path}'
        )


def wait_for_device(
    preferred: str | None,
    timeout: float = 15.0,
    poll_interval: float = 0.25,
) -> str:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            device = resolve_device(preferred)
            if device.upper().startswith('COM') or Path(device).exists():
                return device
        except (FileNotFoundError, DeviceResetError) as error:
            last_error = error
        time.sleep(poll_interval)
    raise DeviceResetError(
        f'CP3 did not reconnect within {timeout:.1f} seconds'
        + (f': {last_error}' if last_error else '')
    )


def reset_device(
    preferred: str | None = None,
    *,
    use_sudo: bool = False,
    disconnect_delay: float = 1.0,
    reconnect_timeout: float = 15.0,
) -> CP3DeviceInfo:
    if sys.platform != 'linux':
        raise DeviceResetError(
            'reset-device currently supports Linux sysfs only'
        )

    serial_device = resolve_device(preferred)
    usb_device = find_usb_sysfs_device(serial_device)
    authorized = usb_device / 'authorized'
    if not authorized.is_file():
        raise DeviceResetError(f'USB authorization control not found: {authorized}')

    users = _port_users(serial_device)
    if users:
        raise DeviceResetError(
            'The serial port is still in use. Stop the dashboard/service first.\n'
            + '\n'.join(users)
        )

    _write_authorized(authorized, '0', use_sudo)
    time.sleep(max(0.1, disconnect_delay))
    _write_authorized(authorized, '1', use_sudo)

    reconnected = wait_for_device(
        None if preferred in (None, '', 'auto') else preferred,
        timeout=reconnect_timeout,
    )
    # Allow usbser/cdc_acm and udev links to settle.
    time.sleep(0.5)
    return inspect_device(reconnected)
