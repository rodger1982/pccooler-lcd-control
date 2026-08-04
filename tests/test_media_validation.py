from pccooler_lcd.media import (
    is_color_value,
    resolve_media_path,
    validate_media_path,
)


def test_widget_color_is_not_media():
    assert is_color_value("#060608")
    assert resolve_media_path("#060608") is None
    assert validate_media_path("#060608") == (None, None)


def test_blank_background_is_valid():
    assert validate_media_path("") == (None, None)


def test_missing_media_returns_path_and_error(tmp_path):
    missing = tmp_path / "missing.gif"
    path, error = validate_media_path(missing)
    assert path == missing
    assert error == f"Media file not found: {missing}"


def test_existing_supported_extension_is_valid(tmp_path):
    image = tmp_path / "background.png"
    image.write_bytes(b"placeholder")
    path, error = validate_media_path(image)
    assert path == image
    assert error is None
