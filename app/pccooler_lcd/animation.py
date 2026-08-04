from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import queue
import threading
import time

from PIL import Image, ImageOps, ImageSequence

from .transport import CP3Connection, TransferError


@dataclass(slots=True)
class EncodedFrame:
    payload: bytes
    duration: float
    digest: str
    source_index: int


@dataclass(slots=True)
class AnimationStats:
    source_frames: int = 0
    encoded_frames: int = 0
    duplicate_frames_removed: int = 0
    frames_sent: int = 0
    frames_skipped: int = 0
    transfer_errors: int = 0


def fit_frame(frame: Image.Image, fit: str = "cover") -> Image.Image:
    if fit == "contain":
        canvas = Image.new("RGB", (320, 240), (0, 0, 0))
        fitted = ImageOps.contain(
            frame.convert("RGB"),
            (320, 240),
            Image.Resampling.BILINEAR,
        )
        canvas.paste(
            fitted,
            ((320 - fitted.width) // 2, (240 - fitted.height) // 2),
        )
        return canvas
    return ImageOps.fit(
        frame.convert("RGB"),
        (320, 240),
        method=Image.Resampling.BILINEAR,
    )


def _encode_png_candidates(
    frame: Image.Image,
    palette_colors: int,
    compression: int,
) -> bytes:
    candidates: list[bytes] = []

    rgb = BytesIO()
    frame.save(
        rgb,
        format="PNG",
        compress_level=max(0, min(9, compression)),
        optimize=False,
    )
    candidates.append(rgb.getvalue())

    if palette_colors > 0:
        colors = max(16, min(256, palette_colors))
        palette_image = frame.convert("RGB").quantize(
            colors=colors,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )

        # Animated GIF frames can carry transparency metadata from the source.
        # Once converted to RGB and quantized, that metadata is stale and can
        # make Pillow reject the paletted PNG with:
        # "transparency for P must be an integer or bytes".
        palette_image.info.pop("transparency", None)

        paletted = BytesIO()
        palette_image.save(
            paletted,
            format="PNG",
            compress_level=max(0, min(9, compression)),
            optimize=False,
        )
        candidates.append(paletted.getvalue())

    return min(candidates, key=len)



def _difference_score(
    current: Image.Image,
    previous: Image.Image,
    sample_size: tuple[int, int] = (40, 30),
) -> float:
    """Return normalized average RGB difference between two frames."""
    current_bytes = current.resize(
        sample_size,
        Image.Resampling.BILINEAR,
    ).convert("RGB").tobytes()
    previous_bytes = previous.resize(
        sample_size,
        Image.Resampling.BILINEAR,
    ).convert("RGB").tobytes()
    total = sum(abs(a - b) for a, b in zip(current_bytes, previous_bytes))
    return total / (len(current_bytes) * 255.0)


def prepare_gif(
    path: str | Path,
    *,
    fit: str = "cover",
    minimum_delay: float = 0.06,
    palette_colors: int = 128,
    compression: int = 2,
    max_frames: int = 0,
    difference_threshold: float = 0.015,
    minimum_frame_duration: float = 0.0,
) -> tuple[list[EncodedFrame], AnimationStats]:
    gif = Image.open(Path(path))
    count = getattr(gif, "n_frames", 1)
    if count < 2:
        raise ValueError("The selected file is not an animated GIF")

    stats = AnimationStats(source_frames=count)
    prepared: list[EncodedFrame] = []
    previous_digest: str | None = None
    previous_fitted: Image.Image | None = None

    for index, source in enumerate(ImageSequence.Iterator(gif)):
        if max_frames and index >= max_frames:
            break

        fitted = fit_frame(source.copy(), fit)
        duration = max(
            minimum_delay,
            source.info.get(
                "duration",
                gif.info.get("duration", 100),
            ) / 1000.0,
        )

        if (
            previous_fitted is not None
            and difference_threshold > 0
            and _difference_score(fitted, previous_fitted)
            < difference_threshold
        ):
            if prepared:
                prepared[-1].duration += duration
            stats.duplicate_frames_removed += 1
            continue

        if minimum_frame_duration > 0 and duration < minimum_frame_duration:
            if prepared:
                prepared[-1].duration += duration
            stats.frames_skipped += 1
            previous_fitted = fitted
            continue

        payload = _encode_png_candidates(
            fitted,
            palette_colors=palette_colors,
            compression=compression,
        )
        digest = hashlib.sha1(payload).hexdigest()

        if digest == previous_digest and prepared:
            prepared[-1].duration += duration
            stats.duplicate_frames_removed += 1
            previous_fitted = fitted
            continue

        prepared.append(
            EncodedFrame(
                payload=payload,
                duration=duration,
                digest=digest,
                source_index=index,
            )
        )
        previous_digest = digest
        previous_fitted = fitted

    stats.encoded_frames = len(prepared)
    return prepared, stats


class SmoothAnimationPlayer:
    """
    Timed GIF player with producer/sender separation.

    The scheduler advances using the GIF clock rather than sleeping after every
    transfer. If the LCD upload falls behind, stale frames are skipped instead
    of making the animation progressively slower.
    """

    def __init__(
        self,
        connection: CP3Connection,
        frames: list[EncodedFrame],
        *,
        loops: int = 0,
        retries: int = 2,
        queue_depth: int = 2,
        allow_frame_skip: bool = True,
    ) -> None:
        if not frames:
            raise ValueError("Animation contains no frames")
        self.connection = connection
        self.frames = frames
        self.loops = loops
        self.retries = retries
        self.allow_frame_skip = allow_frame_skip
        self.queue: queue.Queue[EncodedFrame | None] = queue.Queue(
            maxsize=max(1, queue_depth)
        )
        self.stop_event = threading.Event()
        self.stats = AnimationStats(
            source_frames=len(frames),
            encoded_frames=len(frames),
        )
        self.sender_error: Exception | None = None

    def _sender(self) -> None:
        try:
            while not self.stop_event.is_set():
                frame = self.queue.get()
                if frame is None:
                    return
                try:
                    self.connection.send_png(
                        frame.payload,
                        retries=self.retries,
                    )
                    self.stats.frames_sent += 1
                except Exception as error:
                    self.stats.transfer_errors += 1
                    self.sender_error = error
                    self.stop_event.set()
                    return
                finally:
                    self.queue.task_done()
        finally:
            self.stop_event.set()

    def play(self) -> AnimationStats:
        sender = threading.Thread(
            target=self._sender,
            name="cp3-animation-sender",
            daemon=True,
        )
        sender.start()

        animation_clock = time.monotonic()
        loop_index = 0

        try:
            while (
                not self.stop_event.is_set()
                and (self.loops == 0 or loop_index < self.loops)
            ):
                frame_index = 0
                while frame_index < len(self.frames):
                    if self.stop_event.is_set():
                        break

                    frame = self.frames[frame_index]
                    now = time.monotonic()

                    if self.allow_frame_skip and now > animation_clock + frame.duration:
                        skipped = 0
                        while (
                            frame_index + 1 < len(self.frames)
                            and now > animation_clock + frame.duration
                        ):
                            animation_clock += frame.duration
                            frame_index += 1
                            frame = self.frames[frame_index]
                            skipped += 1
                        self.stats.frames_skipped += skipped

                    wait = animation_clock - time.monotonic()
                    if wait > 0:
                        time.sleep(wait)

                    while not self.stop_event.is_set():
                        try:
                            self.queue.put(frame, timeout=0.05)
                            break
                        except queue.Full:
                            if self.allow_frame_skip:
                                self.stats.frames_skipped += 1
                                break

                    animation_clock += frame.duration
                    frame_index += 1

                loop_index += 1
        except KeyboardInterrupt:
            self.stop_event.set()
        finally:
            self.stop_event.set()
            try:
                self.queue.put_nowait(None)
            except queue.Full:
                pass
            sender.join(timeout=3)

        if self.sender_error:
            raise TransferError(str(self.sender_error))
        return self.stats
