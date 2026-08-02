from pathlib import Path
from pccooler_lcd.media import detect_media_type

def test_media_types():
    assert detect_media_type("a.png") == "image"
    assert detect_media_type("a.gif") == "gif"
    assert detect_media_type("a.mp4") == "video"
