from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import json
import shutil
import subprocess
import time

from PIL import Image

from .transport import CP3Connection


@dataclass(slots=True)
class VideoInfo:
    width: int
    height: int
    duration: float
    fps: float


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            "FFmpeg is required for MP4 support. "
            "Install it with: sudo pacman -S ffmpeg"
        )
    return ffmpeg, ffprobe


def probe_video(path: str | Path) -> VideoInfo:
    _, ffprobe = require_ffmpeg()
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    rate = stream.get("r_frame_rate", "0/1")
    numerator, denominator = rate.split("/", 1)
    fps = float(numerator) / max(1.0, float(denominator))
    return VideoInfo(
        width=int(stream["width"]),
        height=int(stream["height"]),
        duration=float(data.get("format", {}).get("duration", 0.0) or 0.0),
        fps=fps,
    )


def ffmpeg_raw_command(
    path: str | Path,
    *,
    fps: float,
    fit: str,
    loop: bool,
) -> list[str]:
    ffmpeg, _ = require_ffmpeg()

    if fit == "contain":
        video_filter = (
            f"fps={fps},"
            "scale=320:240:force_original_aspect_ratio=decrease,"
            "pad=320:240:(ow-iw)/2:(oh-ih)/2:black"
        )
    else:
        video_filter = (
            f"fps={fps},"
            "scale=320:240:force_original_aspect_ratio=increase,"
            "crop=320:240"
        )

    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if loop:
        command += ["-stream_loop", "-1"]
    command += [
        "-i", str(path),
        "-an",
        "-vf", video_filter,
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "pipe:1",
    ]
    return command


def png_bytes(
    image: Image.Image,
    *,
    palette_colors: int = 96,
    compression: int = 1,
) -> bytes:
    candidates: list[bytes] = []

    rgb_buffer = BytesIO()
    image.save(
        rgb_buffer,
        format="PNG",
        compress_level=max(0, min(9, compression)),
        optimize=False,
    )
    candidates.append(rgb_buffer.getvalue())

    if palette_colors > 0:
        paletted = image.quantize(
            colors=max(16, min(256, palette_colors)),
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )
        paletted.info.pop("transparency", None)
        palette_buffer = BytesIO()
        paletted.save(
            palette_buffer,
            format="PNG",
            compress_level=max(0, min(9, compression)),
            optimize=False,
        )
        candidates.append(palette_buffer.getvalue())

    return min(candidates, key=len)


def raw_video_frames(
    path: str | Path,
    *,
    fps: float = 8.0,
    fit: str = "cover",
    loop: bool = True,
):
    frame_size = 320 * 240 * 3
    process = subprocess.Popen(
        ffmpeg_raw_command(path, fps=fps, fit=fit, loop=loop),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        while True:
            data = process.stdout.read(frame_size)
            if len(data) != frame_size:
                break
            yield Image.frombytes("RGB", (320, 240), data)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def play_video(
    path: str | Path,
    *,
    device: str,
    fps: float = 8.0,
    fit: str = "cover",
    palette_colors: int = 96,
    compression: int = 1,
    retries: int = 2,
    chunk_delay: float = 0.001,
    timeout: float = 4.0,
    verbose: bool = False,
) -> None:
    frame_interval = 1.0 / max(1.0, fps)
    with CP3Connection(
        device,
        timeout,
        chunk_delay,
        verbose,
    ) as connection:
        next_frame_time = time.monotonic()
        for image in raw_video_frames(
            path,
            fps=fps,
            fit=fit,
            loop=True,
        ):
            payload = png_bytes(
                image,
                palette_colors=palette_colors,
                compression=compression,
            )
            connection.send_png(
                payload,
                retries=retries,
            )
            next_frame_time += frame_interval
            delay = next_frame_time - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            elif delay < -frame_interval:
                next_frame_time = time.monotonic()
