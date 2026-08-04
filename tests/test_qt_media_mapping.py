from pathlib import Path


def test_main_window_contains_video_background_mapping():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "pccooler_lcd"
        / "qt"
        / "main_window.py"
    ).read_text()
    assert '"video": 3' in source
    assert "QStandardPaths.PicturesLocation" in source
