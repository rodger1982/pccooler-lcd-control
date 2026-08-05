from pathlib import Path

from pccooler_lcd.native_media import NativeMediaError


def test_native_media_error_is_runtime_error():
    assert issubclass(NativeMediaError, RuntimeError)
