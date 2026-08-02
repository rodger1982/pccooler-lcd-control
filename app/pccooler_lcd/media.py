from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageOps, ImageSequence

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
GIF_EXTENSIONS = {".gif"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"}


class MediaError(RuntimeError):
    pass


def detect_media_type(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in GIF_EXTENSIONS:
        return "gif"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    raise MediaError(f"Unsupported media format: {suffix or 'no extension'}")


def _fit(image: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    image = image.convert("RGB")
    if fit == "contain":
        canvas = Image.new("RGB", size, (0, 0, 0))
        fitted = ImageOps.contain(image, size, Image.Resampling.BILINEAR)
        canvas.paste(fitted, ((size[0]-fitted.width)//2, (size[1]-fitted.height)//2))
        return canvas
    return ImageOps.fit(image, size, method=Image.Resampling.BILINEAR)


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise MediaError("FFmpeg is required for video media. Install ffmpeg and restart the application.")
    return executable


def first_frame(path: str | Path, *, size=(320, 240), fit="cover") -> Image.Image:
    path = Path(path).expanduser()
    media_type = detect_media_type(path)
    if media_type in {"image", "gif"}:
        with Image.open(path) as source:
            source.seek(0)
            return _fit(source.copy(), size, fit)
    command = [
        _ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, timeout=20)
    expected = size[0] * size[1] * 3
    if result.returncode != 0:
        raise MediaError(result.stderr.decode(errors="replace").strip() or "FFmpeg could not decode video")
    # ffmpeg output is source sized, so request exact dimensions in a second command.
    vf = (f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=" +
          ("decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black" % size if fit == "contain" else "increase,crop=%d:%d" % size))
    command = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    result = subprocess.run(command, capture_output=True, timeout=20)
    if result.returncode != 0 or len(result.stdout) != expected:
        raise MediaError(result.stderr.decode(errors="replace").strip() or "FFmpeg returned an invalid frame")
    return Image.frombytes("RGB", size, result.stdout)


@dataclass(slots=True)
class MediaFrame:
    image: Image.Image
    duration: float
    index: int


class MediaSource:
    def __init__(self, path: str | Path, *, size=(320, 240), fit="cover", fps=8.0, cache=True):
        self.path = Path(path).expanduser()
        if not self.path.is_file():
            raise MediaError(f"Media file not found: {self.path}")
        self.kind = detect_media_type(self.path)
        self.size = size
        self.fit = fit
        self.fps = max(1.0, float(fps))
        self.cache = cache
        self.frames: list[MediaFrame] = []
        self.index = 0
        self.elapsed = 0.0
        self.process: subprocess.Popen | None = None
        self._load()

    @property
    def animated(self) -> bool:
        return self.kind in {"gif", "video"}

    def _load(self) -> None:
        if self.kind == "image":
            self.frames = [MediaFrame(first_frame(self.path, size=self.size, fit=self.fit), 3600.0, 0)]
        elif self.kind == "gif" and self.cache:
            with Image.open(self.path) as gif:
                self.frames = [
                    MediaFrame(_fit(frame.copy(), self.size, self.fit), max(0.02, frame.info.get("duration", gif.info.get("duration", 100))/1000.0), i)
                    for i, frame in enumerate(ImageSequence.Iterator(gif))
                ]
        elif self.kind == "video":
            self._open_video()

    def _open_video(self) -> None:
        if self.process:
            self.close()
        if self.fit == "contain":
            vf=f"fps={self.fps},scale={self.size[0]}:{self.size[1]}:force_original_aspect_ratio=decrease,pad={self.size[0]}:{self.size[1]}:(ow-iw)/2:(oh-ih)/2:black"
        else:
            vf=f"fps={self.fps},scale={self.size[0]}:{self.size[1]}:force_original_aspect_ratio=increase,crop={self.size[0]}:{self.size[1]}"
        self.process = subprocess.Popen([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", str(self.path), "-an", "-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def next_frame(self, elapsed: float | None = None) -> Image.Image:
        if self.kind == "image":
            return self.frames[0].image.copy()
        if self.kind == "gif":
            if elapsed is None:
                self.index = (self.index + 1) % len(self.frames)
            else:
                self.elapsed += max(0.0, elapsed)
                while self.elapsed >= self.frames[self.index].duration:
                    self.elapsed -= self.frames[self.index].duration
                    self.index = (self.index + 1) % len(self.frames)
            return self.frames[self.index].image.copy()
        assert self.process and self.process.stdout
        frame_size=self.size[0]*self.size[1]*3
        data=self.process.stdout.read(frame_size)
        if len(data) != frame_size:
            self._open_video(); assert self.process and self.process.stdout
            data=self.process.stdout.read(frame_size)
        if len(data) != frame_size:
            raise MediaError("Video decoder stopped before returning a full frame")
        return Image.frombytes("RGB", self.size, data)

    def close(self) -> None:
        if self.process:
            self.process.terminate()
            try: self.process.wait(timeout=1)
            except subprocess.TimeoutExpired: self.process.kill()
            self.process=None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
