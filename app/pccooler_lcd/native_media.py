from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import subprocess
import tempfile


class NativeMediaError(RuntimeError):
    pass


@dataclass(slots=True)
class PreparedMedia:
    source: Path
    output: Path
    width: int
    height: int
    fps: float
    codec: str
    size: int


def _require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise NativeMediaError(
            f"{name} was not found in PATH. Install FFmpeg first."
        )
    return path


def probe_media(path: str | Path) -> dict:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise NativeMediaError(f"Media file not found: {source}")

    ffprobe = _require_program("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,pix_fmt,duration",
        "-show_entries",
        "format=duration,size,format_name",
        "-of",
        "json",
        str(source),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise NativeMediaError(
            result.stderr.strip() or "ffprobe failed"
        )
    return json.loads(result.stdout)


def _fps_value(value: str | None, fallback: float = 30.0) -> float:
    if not value:
        return fallback
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value:
                return float(numerator) / denominator_value
        except ValueError:
            return fallback
    try:
        return float(value)
    except ValueError:
        return fallback


def prepare_media(
    source_path: str | Path,
    output_path: str | Path,
    *,
    width: int = 320,
    height: int = 240,
    fps: float = 30.0,
    fit: str = "cover",
    crf: int = 23,
    preset: str = "medium",
    codec: str = "libx264",
) -> PreparedMedia:
    source = Path(source_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()

    if not source.is_file():
        raise NativeMediaError(f"Media file not found: {source}")
    if width <= 0 or height <= 0:
        raise NativeMediaError("Width and height must be positive")
    if width % 2 or height % 2:
        raise NativeMediaError(
            "CP3 media dimensions must both be even numbers"
        )
    if fit not in {"cover", "contain"}:
        raise NativeMediaError("fit must be cover or contain")

    ffmpeg = _require_program("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    if fit == "cover":
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-an",
        "-vf",
        video_filter,
        "-r",
        f"{fps:g}",
        "-c:v",
        codec,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-bf",
        "0",
        "-movflags",
        "+faststart",
        str(output),
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise NativeMediaError(
            result.stderr.strip() or "FFmpeg conversion failed"
        )

    info = probe_media(output)
    stream = (info.get("streams") or [{}])[0]
    return PreparedMedia(
        source=source,
        output=output,
        width=int(stream.get("width") or width),
        height=int(stream.get("height") or height),
        fps=_fps_value(stream.get("r_frame_rate"), fps),
        codec=str(stream.get("codec_name") or codec),
        size=output.stat().st_size,
    )


def temporary_prepared_path(source: str | Path) -> Path:
    source_path = Path(source)
    safe_stem = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in source_path.stem
    )
    return Path(tempfile.gettempdir()) / f"{safe_stem}-cp3.mp4"


def prepare_looped_media(
    source_path: str | Path,
    output_path: str | Path,
    *,
    duration_minutes: float = 60.0,
    width: int = 320,
    height: int = 240,
    fps: float = 30.0,
    fit: str = "cover",
    crf: int = 23,
    preset: str = "medium",
    codec: str = "libx264",
) -> PreparedMedia:
    """
    Repeat a source video into one long MP4.

    The CP3 is confirmed to play an uploaded MP4 locally, but the native
    loop-control command has not yet been recovered. A long repeated MP4 is a
    practical temporary substitute.
    """
    if duration_minutes <= 0:
        raise NativeMediaError("duration_minutes must be greater than zero")

    source = Path(source_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()

    if not source.is_file():
        raise NativeMediaError(f"Media file not found: {source}")
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise NativeMediaError(
            "Width and height must be positive even numbers"
        )
    if fit not in {"cover", "contain"}:
        raise NativeMediaError("fit must be cover or contain")

    ffmpeg = _require_program("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    if fit == "cover":
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )

    command = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(source),
        "-t",
        f"{duration_minutes * 60:g}",
        "-an",
        "-vf",
        video_filter,
        "-r",
        f"{fps:g}",
        "-c:v",
        codec,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-bf",
        "0",
        "-movflags",
        "+faststart",
        str(output),
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise NativeMediaError(
            result.stderr.strip() or "FFmpeg loop conversion failed"
        )

    info = probe_media(output)
    stream = (info.get("streams") or [{}])[0]
    return PreparedMedia(
        source=source,
        output=output,
        width=int(stream.get("width") or width),
        height=int(stream.get("height") or height),
        fps=_fps_value(stream.get("r_frame_rate"), fps),
        codec=str(stream.get("codec_name") or codec),
        size=output.stat().st_size,
    )
