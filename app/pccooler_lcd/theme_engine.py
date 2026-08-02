from __future__ import annotations

from pathlib import Path
import colorsys

from PIL import Image, ImageOps


def _load_sample(source) -> Image.Image:
    if isinstance(source, Image.Image):
        image = source.convert("RGB")
    else:
        path = Path(source).expanduser()
        image = Image.open(path)
        try:
            image.seek(0)
        except EOFError:
            pass
        image = image.convert("RGB")
    return ImageOps.fit(image, (96, 72), method=Image.Resampling.BILINEAR)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(value))):02X}" for value in rgb)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    values = []
    for channel in rgb:
        value = channel / 255.0
        values.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    light = max(_relative_luminance(a), _relative_luminance(b))
    dark = min(_relative_luminance(a), _relative_luminance(b))
    return (light + 0.05) / (dark + 0.05)


def _best_text(background: tuple[int, int, int]) -> tuple[int, int, int]:
    white = (250, 252, 255)
    black = (8, 12, 18)
    return white if contrast_ratio(background, white) >= contrast_ratio(background, black) else black


def _adjust_for_contrast(
    color: tuple[int, int, int],
    background: tuple[int, int, int],
    minimum: float = 4.5,
) -> tuple[int, int, int]:
    if contrast_ratio(color, background) >= minimum:
        return color

    h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in color))
    background_luminance = _relative_luminance(background)

    for step in range(1, 21):
        candidate_v = max(0.0, min(1.0, v + (step * 0.04 if background_luminance < 0.45 else -step * 0.04)))
        candidate_s = max(0.45, s)
        candidate = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(h, candidate_s, candidate_v))
        if contrast_ratio(candidate, background) >= minimum:
            return candidate

    return _best_text(background)


def generate_contrast_theme(source) -> dict[str, str | int]:
    image = _load_sample(source)
    sample = image.resize((48, 36))
    pixels = list(sample.getdata())

    average = tuple(sum(pixel[index] for pixel in pixels) // len(pixels) for index in range(3))
    brightness = _relative_luminance(average)

    quantized = sample.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = sorted(quantized.getcolors() or [], reverse=True)

    candidates: list[tuple[float, tuple[int, int, int]]] = []
    for count, palette_index in counts:
        rgb = tuple(palette[palette_index * 3:palette_index * 3 + 3])
        if len(rgb) != 3:
            continue
        h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
        score = (s * 2.2) + (0.5 - abs(v - 0.62)) + min(count / 500.0, 1.0)
        candidates.append((score, rgb))

    candidates.sort(reverse=True)
    accents: list[tuple[int, int, int]] = []
    for _, rgb in candidates:
        if all(sum(abs(rgb[index] - existing[index]) for index in range(3)) > 105 for existing in accents):
            accents.append(rgb)
        if len(accents) == 3:
            break

    defaults = [(0, 230, 190), (55, 165, 255), (255, 100, 160)]
    while len(accents) < 3:
        accents.append(defaults[len(accents)])

    if brightness < 0.5:
        panel = tuple(max(6, int(channel * 0.20)) for channel in average)
        text = (248, 250, 255)
        panel_opacity = 220
        overlay_alpha = 55
    else:
        panel = tuple(min(248, int(channel * 0.18 + 210)) for channel in average)
        text = (12, 18, 26)
        panel_opacity = 225
        overlay_alpha = 85

    accents = [_adjust_for_contrast(accent, panel, 3.0) for accent in accents]
    text = _adjust_for_contrast(text, panel, 7.0)

    return {
        "cpu": _hex(accents[0]),
        "memory": _hex(accents[1]),
        "gpu": _hex(accents[2]),
        "text": _hex(text),
        "panel": _hex(panel),
        "panel_opacity": panel_opacity,
        "overlay_alpha": overlay_alpha,
        "background_average": _hex(average),
    }
