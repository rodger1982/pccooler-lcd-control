from PIL import Image
from pccooler_lcd.animation import _difference_score

def test_identical_frames_have_zero_difference():
    frame = Image.new("RGB", (320, 240), (20, 30, 40))
    assert _difference_score(frame, frame.copy()) == 0.0

def test_opposite_frames_have_large_difference():
    black = Image.new("RGB", (320, 240), (0, 0, 0))
    white = Image.new("RGB", (320, 240), (255, 255, 255))
    assert _difference_score(black, white) > 0.95
