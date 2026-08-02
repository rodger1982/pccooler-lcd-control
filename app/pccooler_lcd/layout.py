from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .dashboard import Stats, collect_stats
from .media import first_frame, MediaError


@dataclass(slots=True)
class Widget:
    kind: str
    x: int
    y: int
    width: int
    height: int
    label: str = ""
    foreground: str = "#FFFFFF"
    accent: str = "#00E6BE"
    background: str = "#0D1522"
    opacity: int = 210
    font_size: int = 16
    show_label: bool = True
    show_border: bool = True
    show_graph: bool = True
    show_percentage: bool = True
    show_temperature: bool = True
    show_memory_gb: bool = True


@dataclass(slots=True)
class Layout:
    name: str = "My Layout"
    background: str = ""
    background_type: str = "auto"
    background_fit: str = "cover"
    background_color: str = "#07101A"
    overlay_alpha: int = 35
    widgets: list[Widget] = field(default_factory=list)


WIDGET_DEFAULTS: dict[str, Widget] = {
    "clock": Widget("clock", 10, 8, 145, 52, "TIME", font_size=28),
    "date": Widget("date", 166, 8, 144, 52, "DATE", font_size=15),
    "cpu": Widget("cpu", 10, 70, 145, 72, "CPU"),
    "memory": Widget("memory", 165, 70, 145, 72, "MEMORY", accent="#33AAFF"),
    "gpu": Widget("gpu", 10, 150, 300, 62, "GPU", accent="#FF55AA"),
    "disk": Widget("disk", 10, 218, 90, 18, "DISK", font_size=11),
    "network": Widget("network", 112, 218, 198, 18, "NETWORK", font_size=11),
    "uptime": Widget("uptime", 10, 150, 300, 62, "UPTIME"),
    "text": Widget("text", 10, 100, 160, 40, "CUSTOM TEXT"),
    "image": Widget("image", 190, 90, 100, 100, "IMAGE"),
}


def clone_default(kind: str) -> Widget:
    source = WIDGET_DEFAULTS[kind]
    return Widget(**asdict(source))


def default_layout() -> Layout:
    return Layout(
        name="System Dashboard",
        widgets=[
            clone_default("clock"),
            clone_default("date"),
            clone_default("cpu"),
            clone_default("memory"),
            clone_default("gpu"),
            clone_default("disk"),
            clone_default("network"),
        ],
    )


def save_layout(layout: Layout, path: str | Path) -> None:
    data = asdict(layout)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_layout(path: str | Path) -> Layout:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    widgets = [Widget(**item) for item in data.get("widgets", [])]
    return Layout(
        name=data.get("name", "Imported Layout"),
        background=data.get("background", ""),
        background_type=data.get("background_type", "auto"),
        background_fit=data.get("background_fit", "cover"),
        background_color=data.get("background_color", "#07101A"),
        overlay_alpha=int(data.get("overlay_alpha", 35)),
        widgets=widgets,
    )


def _rgb(value: str, fallback=(255, 255, 255)):
    value = (value or "").lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, max(8, size))
    return ImageFont.load_default()


def _background(layout: Layout, background_frame: Image.Image | None = None) -> Image.Image:
    if background_frame is not None:
        method = ImageOps.contain if layout.background_fit == "contain" else ImageOps.fit
        if layout.background_fit == "contain":
            canvas = Image.new("RGB", (320, 240), _rgb(layout.background_color, (7, 16, 26)))
            fitted = method(background_frame.convert("RGB"), (320, 240), Image.Resampling.BILINEAR)
            canvas.paste(fitted, ((320 - fitted.width) // 2, (240 - fitted.height) // 2))
            return canvas
        return method(background_frame.convert("RGB"), (320, 240), method=Image.Resampling.BILINEAR)
    if layout.background and Path(layout.background).expanduser().is_file():
        try:
            return first_frame(layout.background, size=(320, 240), fit=layout.background_fit)
        except (OSError, MediaError):
            pass
    return Image.new("RGB", (320, 240), _rgb(layout.background_color, (7, 16, 26)))


def _bar(draw, box, value, accent):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x+w, y+h), radius=max(2, h//2), fill=(30, 38, 50, 230))
    fill = int(w * max(0, min(100, value)) / 100)
    if fill:
        draw.rounded_rectangle((x, y, x+fill, y+h), radius=max(2, h//2), fill=(*accent, 255))


def _panel(draw, widget: Widget):
    bg = _rgb(widget.background, (13, 21, 34))
    kwargs = {
        "radius": 9,
        "fill": (*bg, max(0, min(255, widget.opacity))),
    }
    if widget.show_border:
        kwargs["outline"] = (*_rgb(widget.accent, (0, 230, 190)), 150)
        kwargs["width"] = 1
    draw.rounded_rectangle(
        (widget.x, widget.y, widget.x + widget.width, widget.y + widget.height),
        **kwargs,
    )



def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = (text or "").replace("\n", " \n ").split()
    lines: list[str] = []
    current = ""

    for word in words:
        if word == "\n":
            if current:
                lines.append(current)
                current = ""
            if len(lines) >= max_lines:
                break
            continue

        candidate = word if not current else f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                current = ""
                break

        # Break very long single words.
        part = ""
        for char in word:
            test = part + char
            if _text_width(draw, test, font) <= max_width:
                part = test
            else:
                if part:
                    lines.append(part)
                    if len(lines) >= max_lines:
                        part = ""
                        break
                part = char
        current = part

        if len(lines) >= max_lines:
            current = ""
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    return lines[:max_lines]


def _fit_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    preferred_size: int,
    bold: bool = True,
) -> tuple[object, list[str], int]:
    for size in range(max(8, preferred_size), 7, -1):
        font = _font(size, bold)
        line_height = max(9, int(size * 1.15))
        max_lines = max(1, max_height // line_height)
        lines = _wrap_text(draw, text, font, max_width, max_lines)

        if not lines:
            return font, [""], line_height

        widest = max(_text_width(draw, line, font) for line in lines)
        total_height = len(lines) * line_height
        if widest <= max_width and total_height <= max_height:
            return font, lines, line_height

    font = _font(8, bold)
    return font, _wrap_text(draw, text, font, max_width, max(1, max_height // 9)), 9


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    max_width: int,
    max_height: int,
    preferred_size: int,
    fill,
    bold: bool = True,
) -> None:
    font, lines, line_height = _fit_wrapped_text(
        draw,
        text,
        max_width,
        max_height,
        preferred_size,
        bold,
    )
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _compact_text_block(
    draw: ImageDraw.ImageDraw,
    widget: Widget,
    label_text: str,
    value_text: str,
    foreground,
    accent,
) -> None:
    padding = 5
    usable_width = max(8, widget.width - padding * 2)
    usable_height = max(8, widget.height - padding * 2)

    # Tiny widgets: value only.
    if usable_height < 22 or widget.width < 72:
        _draw_wrapped(
            draw,
            (widget.x + padding, widget.y + padding),
            value_text,
            usable_width,
            usable_height,
            max(8, min(widget.font_size, usable_height - 2)),
            foreground,
            True,
        )
        return

    label_height = min(12, max(9, usable_height // 3))
    value_y = widget.y + padding + label_height + 1
    value_height = max(8, usable_height - label_height - 1)

    if widget.show_label:
        _draw_wrapped(
            draw,
            (widget.x + padding, widget.y + padding),
            label_text,
            usable_width,
            label_height,
            max(8, min(widget.font_size - 5, 10)),
            accent,
            True,
        )

    _draw_wrapped(
        draw,
        (widget.x + padding, value_y),
        value_text,
        usable_width,
        value_height,
        max(8, min(widget.font_size, value_height)),
        foreground,
        True,
    )

def render_layout(layout: Layout, stats: Stats | None = None, background_frame: Image.Image | None = None) -> Image.Image:
    stats = stats or collect_stats()
    base = _background(layout, background_frame).convert("RGBA")
    if layout.overlay_alpha:
        base = Image.alpha_composite(
            base,
            Image.new("RGBA", (320, 240), (0, 0, 0, max(0, min(255, layout.overlay_alpha)))),
        )
    overlay = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for widget in layout.widgets:
        _panel(draw, widget)
        fg = _rgb(widget.foreground)
        accent = _rgb(widget.accent, (0, 230, 190))
        label_font = _font(max(9, widget.font_size - 5), True)
        value_font = _font(widget.font_size, True)
        x = widget.x + 8
        y = widget.y + 6

        if widget.show_label and widget.kind not in ("clock", "date", "disk", "network"):
            _draw_wrapped(
                draw,
                (x, y),
                widget.label or widget.kind.upper(),
                max(10, widget.width - 16),
                max(10, min(24, widget.height // 3)),
                max(9, widget.font_size - 5),
                accent,
                True,
            )
            y += max(13, min(24, widget.height // 3))

        if widget.kind == "clock":
            _draw_wrapped(draw, (widget.x + 8, widget.y + 8), stats.now.strftime("%H:%M:%S"), widget.width - 16, widget.height - 16, widget.font_size, fg, True)
        elif widget.kind == "date":
            _draw_wrapped(draw, (widget.x + 8, widget.y + 8), stats.now.strftime("%a %b %d").upper(), widget.width - 16, max(12, widget.height - 28), widget.font_size, fg, True)
            draw.text((widget.x + 8, widget.y + 28), stats.now.strftime("%Y"), font=label_font, fill=accent)
        elif widget.kind == "cpu":
            parts = []
            if widget.show_percentage:
                parts.append(f"{stats.cpu_percent:.0f}%")
            if widget.show_temperature and stats.cpu_temp is not None:
                parts.append(f"{stats.cpu_temp:.0f}°C")
            value_text = "   ".join(parts) or "CPU"
            _draw_wrapped(
                draw,
                (x, y),
                value_text,
                max(10, widget.width - 16),
                max(10, widget.height - (y - widget.y) - (14 if widget.show_graph else 6)),
                widget.font_size,
                fg,
                True,
            )
            if widget.show_graph and widget.show_percentage:
                _bar(draw, (widget.x+8, widget.y+widget.height-15, widget.width-16, 8), stats.cpu_percent, accent)
        elif widget.kind == "memory":
            parts = []
            if widget.show_percentage:
                parts.append(f"{stats.memory_percent:.0f}%")
            if widget.show_memory_gb:
                parts.append(
                    f"{stats.memory_used_gb:.1f}/{stats.memory_total_gb:.0f} GB"
                )
            value_text = "   ".join(parts) or "MEMORY"
            _draw_wrapped(
                draw,
                (x, y),
                value_text,
                max(10, widget.width - 16),
                max(10, widget.height - (y - widget.y) - (14 if widget.show_graph else 6)),
                widget.font_size,
                fg,
                True,
            )
            if widget.show_graph and widget.show_percentage:
                _bar(draw, (widget.x+8, widget.y+widget.height-15, widget.width-16, 8), stats.memory_percent, accent)
        elif widget.kind == "gpu":
            if stats.gpu_percent is None and stats.gpu_temp is None:
                value_text = "GPU DATA N/A"
            else:
                parts = []
                if widget.show_percentage and stats.gpu_percent is not None:
                    parts.append(f"{stats.gpu_percent:.0f}%")
                if widget.show_temperature and stats.gpu_temp is not None:
                    parts.append(f"{stats.gpu_temp:.0f}°C")
                value_text = "   ".join(parts) or "GPU"
            _draw_wrapped(
                draw,
                (x, y),
                value_text,
                max(10, widget.width - 16),
                max(10, widget.height - (y - widget.y) - (14 if widget.show_graph else 6)),
                widget.font_size,
                fg,
                True,
            )
            if (
                widget.show_graph
                and widget.show_percentage
                and stats.gpu_percent is not None
            ):
                _bar(draw, (widget.x+8, widget.y+widget.height-14, widget.width-16, 7), stats.gpu_percent, accent)
        elif widget.kind == "disk":
            _compact_text_block(
                draw,
                widget,
                widget.label or "DISK",
                f"{stats.disk_percent:.0f}%",
                fg,
                accent,
            )
        elif widget.kind == "network":
            _compact_text_block(
                draw,
                widget,
                widget.label or "NETWORK",
                f"{stats.net_mbps:.1f} Mb/s",
                fg,
                accent,
            )
        elif widget.kind == "uptime":
            total = int(stats.uptime_seconds)
            days, rem = divmod(total, 86400)
            hours, rem = divmod(rem, 3600)
            minutes = rem // 60
            draw.text((x, y), f"{days}d {hours:02d}h {minutes:02d}m", font=value_font, fill=fg)
        elif widget.kind == "text":
            _draw_wrapped(draw, (x, y), widget.label or "CUSTOM TEXT", widget.width - 16, widget.height - 16, widget.font_size, fg, True)
        elif widget.kind == "image":
            candidate = Path(widget.label).expanduser()
            if candidate.is_file():
                try:
                    image = first_frame(candidate, size=(widget.width-8, widget.height-8), fit="cover").convert("RGBA")
                    overlay.alpha_composite(image, (widget.x+4, widget.y+4))
                except OSError:
                    draw.text((x, y), "IMAGE ERROR", font=label_font, fill=accent)
            else:
                _draw_wrapped(draw, (x, y), "SET IMAGE PATH", widget.width - 16, widget.height - 16, max(9, widget.font_size - 5), accent, True)

    return Image.alpha_composite(base, overlay).convert("RGB")
