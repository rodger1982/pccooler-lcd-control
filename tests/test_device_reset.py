from pathlib import Path

import pytest

from pccooler_lcd import device


def test_find_usb_sysfs_device_validates_cp3(monkeypatch, tmp_path):
    usb = tmp_path / '3-2'
    interface = usb / '3-2:1.0' / 'tty' / 'ttyACM0'
    interface.mkdir(parents=True)
    (usb / 'idVendor').write_text('1d6b\n')
    (usb / 'idProduct').write_text('0112\n')

    tty_root = tmp_path / 'class' / 'tty'
    tty_dir = tty_root / 'ttyACM0'
    tty_dir.mkdir(parents=True)
    (tty_dir / 'device').symlink_to(interface, target_is_directory=True)
    monkeypatch.setattr(device, 'SYS_TTY', tty_root)

    assert device.find_usb_sysfs_device('/dev/ttyACM0') == usb.resolve()


def test_find_usb_sysfs_device_refuses_other_usb(monkeypatch, tmp_path):
    usb = tmp_path / '3-2'
    interface = usb / '3-2:1.0' / 'tty' / 'ttyACM0'
    interface.mkdir(parents=True)
    (usb / 'idVendor').write_text('1234\n')
    (usb / 'idProduct').write_text('5678\n')

    tty_root = tmp_path / 'class' / 'tty'
    tty_dir = tty_root / 'ttyACM0'
    tty_dir.mkdir(parents=True)
    (tty_dir / 'device').symlink_to(interface, target_is_directory=True)
    monkeypatch.setattr(device, 'SYS_TTY', tty_root)

    with pytest.raises(device.DeviceResetError, match='Refusing to reset'):
        device.find_usb_sysfs_device('/dev/ttyACM0')


def test_reset_requires_free_port(monkeypatch, tmp_path):
    usb = tmp_path / '3-2'
    usb.mkdir()
    (usb / 'authorized').write_text('1')
    monkeypatch.setattr(device, 'resolve_device', lambda preferred=None: '/dev/ttyACM0')
    monkeypatch.setattr(device, 'find_usb_sysfs_device', lambda serial: usb)
    monkeypatch.setattr(device, '_port_users', lambda serial: ['python 1234'])

    with pytest.raises(device.DeviceResetError, match='still in use'):
        device.reset_device()
