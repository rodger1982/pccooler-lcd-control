from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import glob
import os
import shutil
import subprocess
import time

import psutil
from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(slots=True)
class Stats:
    now: datetime
    cpu_percent: float
    cpu_temp: float | None
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    uptime_seconds: float
    gpu_name: str | None = None
    gpu_percent: float | None = None
    gpu_temp: float | None = None
    gpu_memory_percent: float | None = None
    disk_percent: float = 0.0
    net_mbps: float = 0.0


def _read_cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False)
    except (AttributeError, OSError):
        temps = {}

    preferred = ("k10temp", "coretemp", "zenpower", "cpu_thermal")
    for group in preferred:
        for reading in temps.get(group, []):
            if reading.current and 0 < reading.current < 130:
                return float(reading.current)

    for readings in temps.values():
        for reading in readings:
            label = (reading.label or "").lower()
            if ("package" in label or "cpu" in label or "tctl" in label) and 0 < reading.current < 130:
                return float(reading.current)

    for candidate in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            value = float(Path(candidate).read_text().strip()) / 1000.0
            if 0 < value < 130:
                return value
        except (OSError, ValueError):
            pass
    return None


def _read_nvidia() -> tuple[str | None, float | None, float | None, float | None]:
    if not shutil.which("nvidia-smi"):
        return None, None, None, None
    command = [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2, check=True)
        first = result.stdout.splitlines()[0]
        name, util, temp, used, total = [part.strip() for part in first.split(",", 4)]
        total_f = float(total)
        memory_percent = (float(used) / total_f * 100.0) if total_f else None
        return name, float(util), float(temp), memory_percent
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None, None, None, None



def _read_amd() -> tuple[str | None, float | None, float | None, float | None]:
    """Read AMDGPU data from sysfs without requiring extra utilities."""
    cards = sorted(Path("/sys/class/drm").glob("card[0-9]*"))
    for card in cards:
        device = card / "device"
        driver_link = device / "driver"
        try:
            driver_name = driver_link.resolve().name
        except OSError:
            continue
        if driver_name != "amdgpu":
            continue

        name = "AMD Radeon"
        product = device / "product_name"
        if product.exists():
            try:
                name = product.read_text().strip() or name
            except OSError:
                pass

        usage = None
        try:
            usage = float((device / "gpu_busy_percent").read_text().strip())
        except (OSError, ValueError):
            pass

        temperature = None
        for hwmon in (device / "hwmon").glob("hwmon*"):
            try:
                value = float((hwmon / "temp1_input").read_text().strip()) / 1000
                if 0 < value < 130:
                    temperature = value
                    break
            except (OSError, ValueError):
                pass

        memory_percent = None
        try:
            used = float((device / "mem_info_vram_used").read_text().strip())
            total = float((device / "mem_info_vram_total").read_text().strip())
            if total:
                memory_percent = used / total * 100
        except (OSError, ValueError):
            pass

        return name, usage, temperature, memory_percent

    return None, None, None, None

def collect_stats() -> Stats:
    memory = psutil.virtual_memory()
    gpu_name, gpu_percent, gpu_temp, gpu_memory = _read_nvidia()
    if not gpu_name:
        gpu_name, gpu_percent, gpu_temp, gpu_memory = _read_amd()
    try:
        disk_percent = float(psutil.disk_usage('/').percent)
    except OSError:
        disk_percent = 0.0
    counters = psutil.net_io_counters()
    previous = getattr(collect_stats, '_net_previous', None)
    previous_time = getattr(collect_stats, '_net_time', None)
    current_time = time.monotonic()
    net_mbps = 0.0
    if previous is not None and previous_time is not None:
        elapsed = max(0.001, current_time - previous_time)
        byte_delta = (counters.bytes_sent + counters.bytes_recv) - previous
        net_mbps = max(0.0, byte_delta * 8 / elapsed / 1_000_000)
    collect_stats._net_previous = counters.bytes_sent + counters.bytes_recv
    collect_stats._net_time = current_time
    return Stats(
        now=datetime.now(),
        cpu_percent=psutil.cpu_percent(interval=None),
        cpu_temp=_read_cpu_temp(),
        memory_percent=float(memory.percent),
        memory_used_gb=memory.used / (1024 ** 3),
        memory_total_gb=memory.total / (1024 ** 3),
        uptime_seconds=max(0.0, time.time() - psutil.boot_time()),
        gpu_name=gpu_name,
        gpu_percent=gpu_percent,
        gpu_temp=gpu_temp,
        gpu_memory_percent=gpu_memory,
        disk_percent=disk_percent,
        net_mbps=net_mbps,
    )


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _bar(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], value: float, accent: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = xy
    value = max(0.0, min(100.0, value))
    draw.rounded_rectangle(xy, radius=4, fill=(25, 32, 43), outline=(55, 65, 80))
    fill_x = x1 + int((x2 - x1) * value / 100.0)
    if fill_x > x1:
        draw.rounded_rectangle((x1, y1, fill_x, y2), radius=4, fill=accent)


def _temp(value: float | None) -> str:
    return "--°C" if value is None else f"{value:.0f}°C"


def _load_background(background, fallback: tuple[int, int, int]) -> Image.Image:
    if isinstance(background, Image.Image):
        return ImageOps.fit(
            background.convert("RGB"),
            (320, 240),
            method=Image.Resampling.LANCZOS,
        )
    if background:
        path = Path(background).expanduser()
        if path.is_file():
            try:
                image = Image.open(path).convert("RGB")
                return ImageOps.fit(
                    image,
                    (320, 240),
                    method=Image.Resampling.LANCZOS,
                )
            except OSError:
                pass
    return Image.new("RGB", (320, 240), fallback)


def colors_from_background(background) -> dict[str, str]:
    """Choose readable accent colors from a static image or GIF frame."""
    image = _load_background(background, (7, 11, 20))
    sample = image.resize((48, 36)).convert("RGB")
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = quantized.getcolors() or []
    candidates = []
    for count, index in sorted(counts, reverse=True):
        rgb = tuple(palette[index * 3:index * 3 + 3])
        if len(rgb) != 3:
            continue
        brightness = sum(rgb) / 3
        saturation = max(rgb) - min(rgb)
        candidates.append((saturation * 2 + brightness, rgb))

    colorful = [rgb for _, rgb in sorted(candidates, reverse=True)]
    while len(colorful) < 3:
        colorful.append((0, 230, 190))

    def hex_color(rgb):
        return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in rgb)

    average = tuple(
        int(sum(pixel[i] for pixel in sample.getdata()) / (48 * 36))
        for i in range(3)
    )
    luminance = sum(average) / 3
    text = (245, 248, 252) if luminance < 150 else (15, 20, 28)
    panel = tuple(max(0, int(c * 0.28)) for c in average)

    return {
        "cpu": hex_color(colorful[0]),
        "memory": hex_color(colorful[1]),
        "gpu": hex_color(colorful[2]),
        "text": hex_color(text),
        "panel": hex_color(panel),
    }


def render_dashboard(
    stats: Stats,
    theme: str = "cyber",
    title: str = "PCCOOLER LINUX",
    background=None,
    panel_alpha: int = 205,
    overlay_alpha: int = 55,
    cpu_color: str | None = None,
    memory_color: str | None = None,
    gpu_color: str | None = None,
    text_color: str | None = None,
    panel_color: str | None = None,
) -> Image.Image:
    palettes = {
        "cyber": ((7, 11, 20), (13, 21, 34), (0, 230, 190), (30, 170, 255), (235, 242, 250)),
        "amber": ((18, 12, 5), (35, 23, 8), (255, 165, 30), (255, 205, 80), (255, 245, 220)),
        "ice": ((7, 17, 25), (12, 35, 48), (90, 220, 255), (145, 180, 255), (235, 250, 255)),
        "nasa": ((4, 8, 18), (10, 22, 38), (100, 205, 255), (255, 160, 70), (240, 248, 255)),
    }
    bg, panel, accent, accent2, text = palettes.get(theme, palettes["cyber"])

    def parse_hex(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        if not value:
            return fallback
        value = value.strip().lstrip("#")
        if len(value) != 6:
            return fallback
        try:
            return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return fallback

    cpu_accent = parse_hex(cpu_color, accent)
    memory_accent = parse_hex(memory_color, accent2)
    gpu_accent = parse_hex(gpu_color, accent)
    text = parse_hex(text_color, text)
    panel = parse_hex(panel_color, panel)

    base = _load_background(background, bg).convert("RGBA")
    shade = Image.new("RGBA", (320, 240), (*bg, max(0, min(255, overlay_alpha))))
    base = Image.alpha_composite(base, shade)

    overlay = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    small = _font(11)
    label = _font(12, True)
    value = _font(20, True)
    clock = _font(29, True)

    draw.rounded_rectangle((7, 5, 313, 58), radius=10, fill=(*panel, panel_alpha), outline=(*accent, 120))
    draw.text((14, 10), title, font=label, fill=accent)
    draw.text((304, 10), stats.now.strftime("%a %b %d").upper(), font=small, fill=text, anchor="ra")
    draw.text((14, 28), stats.now.strftime("%H:%M:%S"), font=clock, fill=text)

    draw.rounded_rectangle((8, 66, 156, 140), radius=11, fill=(*panel, panel_alpha), outline=(70, 90, 110, 170))
    draw.text((18, 76), "CPU", font=label, fill=cpu_accent)
    draw.text((18, 95), f"{stats.cpu_percent:4.0f}%", font=value, fill=text)
    draw.text((145, 98), _temp(stats.cpu_temp), font=label, fill=accent2, anchor="ra")
    _bar(draw, (18, 122, 145, 132), stats.cpu_percent, cpu_accent)

    draw.rounded_rectangle((164, 66, 312, 140), radius=11, fill=(*panel, panel_alpha), outline=(70, 90, 110, 170))
    draw.text((174, 76), "MEMORY", font=label, fill=memory_accent)
    draw.text((174, 95), f"{stats.memory_percent:4.0f}%", font=value, fill=text)
    draw.text((301, 100), f"{stats.memory_used_gb:.1f}/{stats.memory_total_gb:.0f} GB", font=small, fill=accent2, anchor="ra")
    _bar(draw, (174, 122, 301, 132), stats.memory_percent, memory_accent)

    draw.rounded_rectangle((8, 148, 312, 220), radius=11, fill=(*panel, panel_alpha), outline=(70, 90, 110, 170))
    if stats.gpu_name:
        draw.text((18, 158), "GPU", font=label, fill=gpu_accent)
        draw.text((59, 159), stats.gpu_name[:28], font=small, fill=text)
        draw.text((18, 178), f"{stats.gpu_percent or 0:.0f}%", font=value, fill=text)
        draw.text((94, 182), _temp(stats.gpu_temp), font=label, fill=accent2)
        draw.text((300, 182), f"VRAM {stats.gpu_memory_percent or 0:.0f}%", font=label, fill=accent2, anchor="ra")
        _bar(draw, (18, 205, 301, 214), stats.gpu_percent or 0, gpu_accent)
    else:
        uptime = int(stats.uptime_seconds)
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        draw.text((18, 158), "SYSTEM", font=label, fill=accent)
        draw.text((18, 182), "UPTIME", font=small, fill=accent2)
        draw.text((76, 177), f"{days}d {hours:02d}h {minutes:02d}m", font=value, fill=text)
        draw.text((18, 205), "GPU telemetry appears automatically when available", font=small, fill=(175, 190, 205))

    draw.text((10, 230), f"DISK {stats.disk_percent:.0f}%", font=small, fill=accent)
    draw.text((310, 230), f"NET {stats.net_mbps:.1f} Mb/s", font=small, fill=accent, anchor="ra")

    return Image.alpha_composite(base, overlay).convert("RGB")
