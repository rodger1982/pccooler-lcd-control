from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path
import tempfile
import time

from PIL import Image, ImageOps, ImageSequence

from . import __version__
from .dashboard import collect_stats, render_dashboard, colors_from_background
from .device import (
    DeviceResetError,
    inspect_device,
    reset_device,
    resolve_device,
    scan_devices,
)
from .protocol_cp3 import (
    parse_png_dimensions,
    request_preview,
    describe_frame,
    decode_packet_text,
)
from .transport import CP3Connection, TransferError
from .layout import load_layout, render_layout
from .animation import prepare_gif, SmoothAnimationPlayer, EncodedFrame
from .video import play_video, raw_video_frames, png_bytes as video_png_bytes
from .media import MediaSource, detect_media_type
from .platform import config_dir, default_device
from .protocol_lab import (
    ProtocolRecorder,
    protocol_catalog,
    load_trace,
)
from .native_media import (
    NativeMediaError,
    prepare_media,
    probe_media,
    temporary_prepared_path,
    prepare_looped_media,
)


def scan_cmd(args):
    devices = scan_devices()
    if not devices:
        print("No PCCOOLER CP3 device found")
        return 1
    for port in devices:
        print(
            f"{port.device} {port.vid:04x}:{port.pid:04x} "
            f"{port.manufacturer or '-'} {port.product or port.description}"
        )
    return 0


def diagnose_cmd(args):
    print(f"Version: {__version__}")
    print(f"Device: {resolve_device(args.device)}")
    print(f"Detected CP3 devices: {len(scan_devices())}")
    print("Display geometry: 320x240")
    print("Transport: persistent CDC ACM serial")
    print("GIF mode: pre-rendered cached PNG frames")
    return 0



def inspect_device_cmd(args):
    try:
        info = inspect_device(args.device)
    except (DeviceResetError, FileNotFoundError) as error:
        raise SystemExit(str(error))

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
        return 0

    print('PCCOOLER CP3 device')
    print(f'  Serial device: {info.serial_device}')
    print(
        '  USB ID: '
        f'{info.vid:04x}:{info.pid:04x}'
        if info.vid is not None and info.pid is not None
        else '  USB ID: unknown'
    )
    print(f'  Manufacturer: {info.manufacturer or "unknown"}')
    print(f'  Product: {info.product or info.description or "unknown"}')
    print(f'  Serial number: {info.serial_number or "unknown"}')
    print(f'  USB bus path: {info.usb_bus_path or "unavailable"}')
    print(f'  USB sysfs path: {info.usb_sysfs_path or "unavailable"}')
    print(f'  Connected: {"yes" if info.connected else "no"}')
    if info.port_in_use is None:
        print('  Port in use: unknown')
    else:
        print(f'  Port in use: {"yes" if info.port_in_use else "no"}')
    if info.port_users:
        print('  Port users:')
        for line in info.port_users:
            print(f'    {line}')
    return 0


def reset_device_cmd(args):
    print('Locating PCCOOLER CP3...')
    try:
        before = inspect_device(args.device)
        print(f'  Serial device: {before.serial_device}')
        print(f'  USB bus path: {before.usb_bus_path or "unknown"}')
        print('Resetting USB device...')
        after = reset_device(
            args.device,
            use_sudo=args.sudo,
            disconnect_delay=args.disconnect_delay,
            reconnect_timeout=args.reconnect_timeout,
        )
    except (DeviceResetError, FileNotFoundError) as error:
        raise SystemExit(str(error))

    print('CP3 reconnected successfully.')
    print(f'  Serial device: {after.serial_device}')
    print(f'  USB bus path: {after.usb_bus_path or "unknown"}')
    return 0


def image_to_png_bytes(image: Image.Image, compression: int = 1) -> bytes:
    buffer = BytesIO()
    image.convert("RGB").save(
        buffer,
        format="PNG",
        compress_level=max(0, min(9, compression)),
        optimize=False,
    )
    return buffer.getvalue()


def fit_frame(frame: Image.Image, fit: str) -> Image.Image:
    if fit == "contain":
        canvas = Image.new("RGB", (320, 240), (0, 0, 0))
        fitted = ImageOps.contain(
            frame.convert("RGB"),
            (320, 240),
            Image.Resampling.LANCZOS,
        )
        canvas.paste(fitted, ((320 - fitted.width) // 2, (240 - fitted.height) // 2))
        return canvas
    return ImageOps.fit(
        frame.convert("RGB"),
        (320, 240),
        method=Image.Resampling.LANCZOS,
    )


def load_gif_frames(path: Path, fit: str, compression: int):
    try:
        gif = Image.open(path)
    except OSError as error:
        raise SystemExit(f"Unable to open GIF: {error}")

    if getattr(gif, "n_frames", 1) < 2:
        raise SystemExit("The selected file is not an animated GIF.")

    frames = []
    durations = []
    for frame in ImageSequence.Iterator(gif):
        fitted = fit_frame(frame.copy(), fit)
        frames.append(image_to_png_bytes(fitted, compression))
        durations.append(max(0.01, frame.info.get("duration", gif.info.get("duration", 100)) / 1000.0))
    return frames, durations, gif.copy().convert("RGB")


def send_image_cmd(args):
    path = Path(args.image)
    if not path.is_file():
        raise SystemExit(f"Image not found: {path}")
    payload = path.read_bytes()
    width, height = parse_png_dimensions(payload)
    if (width, height) != (320, 240):
        raise SystemExit(f"Expected a 320x240 PNG, got {width}x{height}")

    if args.dry_run:
        print(f"PNG: {width}x{height}, {len(payload)} bytes")
        return 0

    with CP3Connection(args.device, args.timeout, args.chunk_delay, args.verbose) as connection:
        connection.send_png(payload, args.remote_name, args.retries)
    print("Image sent successfully.")
    return 0


def resolved_colors(args, background):
    if not args.auto_colors:
        return {
            "cpu": args.cpu_color,
            "memory": args.memory_color,
            "gpu": args.gpu_color,
            "text": args.text_color,
            "panel": args.panel_color,
        }
    palette = colors_from_background(background)
    if not args.quiet:
        print(
            "Auto colors: "
            f"CPU {palette['cpu']}, Memory {palette['memory']}, "
            f"GPU {palette['gpu']}, Text {palette['text']}"
        )
    return palette


def dashboard_cmd(args):
    gif = None
    gif_index = 0
    gif_frames = []
    gif_durations = []
    next_gif_frame = 0.0

    if args.background_gif:
        gif_path = Path(args.background_gif)
        if not gif_path.is_file():
            raise SystemExit(f"Background GIF not found: {gif_path}")
        gif = Image.open(gif_path)
        gif_frames = [fit_frame(frame.copy(), args.gif_fit) for frame in ImageSequence.Iterator(gif)]
        gif_durations = [
            max(args.gif_min_delay, frame.info.get("duration", gif.info.get("duration", 100)) / 1000.0)
            for frame in ImageSequence.Iterator(gif)
        ]
        next_gif_frame = time.monotonic()

    background_for_palette = gif_frames[0] if gif_frames else args.background
    palette = resolved_colors(args, background_for_palette)

    print(f"Dashboard started on {resolve_device(args.device)}")
    if gif_frames:
        print(f"Animated background: {len(gif_frames)} cached frames")
    print("Press Ctrl+C to stop.")

    frames = 0
    consecutive_failures = 0
    try:
        with CP3Connection(args.device, args.timeout, args.chunk_delay, args.verbose) as connection:
            while args.count == 0 or frames < args.count:
                started = time.monotonic()

                if gif_frames:
                    now = time.monotonic()
                    if now >= next_gif_frame:
                        gif_index = (gif_index + 1) % len(gif_frames)
                        next_gif_frame = now + gif_durations[gif_index]
                    background = gif_frames[gif_index]
                else:
                    background = args.background

                stats = collect_stats()
                image = render_dashboard(
                    stats,
                    theme=args.theme,
                    title=args.title,
                    background=background,
                    panel_alpha=args.panel_alpha,
                    overlay_alpha=args.overlay_alpha,
                    cpu_color=palette["cpu"],
                    memory_color=palette["memory"],
                    gpu_color=palette["gpu"],
                    text_color=palette["text"],
                    panel_color=palette["panel"],
                )

                if args.preview:
                    image.save(args.preview, format="PNG")

                payload = image_to_png_bytes(image, args.png_compression)

                try:
                    connection.send_png(payload, retries=args.retries)
                    consecutive_failures = 0
                except TransferError as error:
                    consecutive_failures += 1
                    print(f"Frame transfer failed: {error}")
                    if consecutive_failures >= args.max_failures:
                        raise
                    connection.reconnect(args.recovery_delay)
                    continue

                frames += 1
                if not args.quiet:
                    print(
                        f"Frame {frames}: CPU {stats.cpu_percent:.0f}% "
                        f"{_fmt_temp(stats.cpu_temp)}, RAM {stats.memory_percent:.0f}%"
                    )
                elapsed = time.monotonic() - started
                time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    return 0


def play_gif_cmd(args):
    path = Path(args.gif)
    if not path.is_file():
        raise SystemExit(f"GIF not found: {path}")

    print("Optimizing and caching GIF frames...")
    frames, preparation = prepare_gif(
        path,
        fit=args.fit,
        minimum_delay=args.min_delay,
        palette_colors=args.palette_colors,
        compression=args.png_compression,
        max_frames=args.max_frames,
        difference_threshold=args.difference_threshold,
        minimum_frame_duration=args.minimum_frame_duration,
    )

    total_bytes = sum(len(frame.payload) for frame in frames)
    average_bytes = int(total_bytes / max(1, len(frames)))
    print(
        f"Prepared {len(frames)}/{preparation.source_frames} frames; "
        f"merged {preparation.duplicate_frames_removed} similar frames; "
        f"average frame {average_bytes / 1024:.1f} KiB"
    )
    print(
        "Adaptive scheduler enabled: stale frames will be skipped "
        "instead of slowing the whole animation."
    )
    print("Press Ctrl+C to stop.")

    try:
        with CP3Connection(
            args.device,
            args.timeout,
            args.chunk_delay,
            args.verbose,
        ) as connection:
            player = SmoothAnimationPlayer(
                connection,
                frames,
                loops=args.loops,
                retries=args.retries,
                queue_depth=args.queue_depth,
                allow_frame_skip=not args.no_frame_skip,
            )
            stats = player.play()
    except KeyboardInterrupt:
        print("\nGIF playback stopped.")
        return 0

    print(
        f"Playback ended: sent {stats.frames_sent}, "
        f"skipped {stats.frames_skipped}, "
        f"errors {stats.transfer_errors}"
    )
    return 0


def layout_dashboard_cmd(args):
    layout = load_layout(args.layout)
    background_path = (
        Path(layout.background).expanduser()
        if layout.background
        else None
    )
    is_gif = bool(
        background_path
        and background_path.is_file()
        and (
            layout.background_type == "gif"
            or background_path.suffix.lower() == ".gif"
        )
    )

    print(f"Layout dashboard: {layout.name}")

    if is_gif and args.optimized_gif:
        print("Preparing optimized animated layout frames...")
        gif = Image.open(background_path)
        encoded_frames = []
        stats_snapshot = collect_stats()

        for index, source in enumerate(ImageSequence.Iterator(gif)):
            background_frame = source.copy().convert("RGB")
            rendered = render_layout(
                layout,
                stats_snapshot,
                background_frame=background_frame,
            )
            payload = image_to_png_bytes(
                rendered,
                args.png_compression,
            )
            duration = max(
                args.gif_min_delay,
                source.info.get(
                    "duration",
                    gif.info.get("duration", 100),
                ) / 1000.0,
            )
            encoded_frames.append(
                EncodedFrame(
                    payload=payload,
                    duration=duration,
                    digest=str(index),
                    source_index=index,
                )
            )

        print(
            f"Prepared {len(encoded_frames)} cached layout frames; "
            "adaptive skipping enabled."
        )

        try:
            with CP3Connection(
                args.device,
                args.timeout,
                args.chunk_delay,
                args.verbose,
            ) as connection:
                player = SmoothAnimationPlayer(
                    connection,
                    encoded_frames,
                    loops=0,
                    retries=args.retries,
                    queue_depth=1,
                    allow_frame_skip=True,
                )
                player.play()
        except KeyboardInterrupt:
            print("\nAnimated layout stopped.")
        return 0

    background_frames = []
    background_durations = []
    background_index = 0
    next_background_time = 0.0

    if is_gif:
        gif = Image.open(background_path)
        for source in ImageSequence.Iterator(gif):
            background_frames.append(
                source.copy().convert("RGB")
            )
            background_durations.append(
                max(
                    args.gif_min_delay,
                    source.info.get(
                        "duration",
                        gif.info.get("duration", 100),
                    ) / 1000.0,
                )
            )
        next_background_time = (
            time.monotonic() + background_durations[0]
        )
        print(
            f"Animated layout background: "
            f"{len(background_frames)} frames"
        )

    try:
        with CP3Connection(
            args.device,
            args.timeout,
            args.chunk_delay,
            args.verbose,
        ) as connection:
            frame = 0
            while args.count == 0 or frame < args.count:
                started = time.monotonic()

                background_frame = None
                if background_frames:
                    now = time.monotonic()
                    if now >= next_background_time:
                        background_index = (
                            background_index + 1
                        ) % len(background_frames)
                        next_background_time = (
                            now
                            + background_durations[
                                background_index
                            ]
                        )
                    background_frame = background_frames[
                        background_index
                    ]

                image = render_layout(
                    layout,
                    collect_stats(),
                    background_frame=background_frame,
                )
                payload = image_to_png_bytes(
                    image,
                    args.png_compression,
                )
                connection.send_png(
                    payload,
                    retries=args.retries,
                )
                frame += 1
                if not args.quiet:
                    print(f"Layout frame {frame}")
                elapsed = time.monotonic() - started
                time.sleep(
                    max(0.0, args.interval - elapsed)
                )
    except KeyboardInterrupt:
        print("\nLayout dashboard stopped.")
    return 0



def play_video_cmd(args):
    path = Path(args.video)
    if not path.is_file():
        raise SystemExit(f"Video not found: {path}")

    print(
        f"Playing video at target {args.fps:g} FPS. "
        "Press Ctrl+C to stop."
    )
    try:
        play_video(
            path,
            device=args.device,
            fps=args.fps,
            fit=args.fit,
            palette_colors=args.palette_colors,
            compression=args.png_compression,
            retries=args.retries,
            chunk_delay=args.chunk_delay,
            timeout=args.timeout,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        print("\nVideo playback stopped.")
    return 0


def video_layout_dashboard_cmd(args):
    layout = load_layout(args.layout)
    path = Path(layout.background).expanduser()
    if not path.is_file():
        raise SystemExit(f"Video background not found: {path}")

    frame_interval = 1.0 / max(1.0, args.fps)
    next_frame_time = time.monotonic()

    try:
        with CP3Connection(
            args.device,
            args.timeout,
            args.chunk_delay,
            args.verbose,
        ) as connection:
            for background_frame in raw_video_frames(
                path,
                fps=args.fps,
                fit=layout.background_fit,
                loop=True,
            ):
                rendered = render_layout(
                    layout,
                    collect_stats(),
                    background_frame=background_frame,
                )
                payload = video_png_bytes(
                    rendered,
                    palette_colors=args.palette_colors,
                    compression=args.png_compression,
                )
                connection.send_png(
                    payload,
                    retries=args.retries,
                )
                next_frame_time += frame_interval
                delay = next_frame_time - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -frame_interval:
                    next_frame_time = time.monotonic()
    except KeyboardInterrupt:
        print("\nVideo layout stopped.")
    return 0

def media_layout_dashboard_cmd(args):
    layout = load_layout(args.layout)
    if not layout.background:
        return layout_dashboard_cmd(args)
    with MediaSource(layout.background, size=(320, 240), fit=layout.background_fit, fps=args.media_fps) as media:
        with CP3Connection(args.device, args.timeout, args.chunk_delay, args.verbose) as connection:
            try:
                while True:
                    started=time.monotonic()
                    background=media.next_frame(1.0/args.media_fps)
                    image=render_layout(layout, collect_stats(), background_frame=background)
                    payload=image_to_png_bytes(image, args.png_compression)
                    connection.send_png(payload, retries=args.retries)
                    time.sleep(max(0.0, 1.0/args.media_fps-(time.monotonic()-started)))
            except KeyboardInterrupt:
                print("\nMedia layout stopped.")
    return 0

def startup_dashboard_cmd(args):
    config_path = config_dir() / "startup.json"
    if not config_path.is_file():
        raise SystemExit(
            "No startup layout selected. "
            "Choose one in PCCOOLER-LCD Control."
        )

    try:
        data = json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        raise SystemExit(
            f"Could not read startup configuration: {error}"
        )

    layout_path = Path(
        data.get("layout", "")
    ).expanduser()
    if not layout_path.is_file():
        raise SystemExit(
            f"Startup layout not found: {layout_path}"
        )

    layout_model = load_layout(layout_path)
    if layout_model.background and detect_media_type(layout_model.background) in {"gif", "video"}:
        forwarded = argparse.Namespace(
            layout=str(layout_path), device=args.device, timeout=args.timeout,
            chunk_delay=args.chunk_delay, verbose=args.verbose, retries=args.retries,
            media_fps=args.video_fps, png_compression=args.png_compression,
        )
        return media_layout_dashboard_cmd(forwarded)

    forwarded = argparse.Namespace(
        layout=str(layout_path),
        device=args.device,
        timeout=args.timeout,
        chunk_delay=args.chunk_delay,
        verbose=args.verbose,
        retries=args.retries,
        interval=args.interval,
        count=0,
        quiet=True,
        png_compression=args.png_compression,
        gif_min_delay=args.gif_min_delay,
        optimized_gif=True,
        palette_colors=args.palette_colors,
    )
    return layout_dashboard_cmd(forwarded)


def benchmark_transfer_cmd(args):
    from PIL import Image, ImageDraw
    from io import BytesIO
    import statistics

    sizes = []
    durations = []

    recorder = (
        ProtocolRecorder(args.session_trace)
        if getattr(args, "session_trace", None)
        else None
    )

    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
        recorder=recorder,
    ) as connection:
        for index in range(args.frames):
            image = Image.new(
                "RGB",
                (320, 240),
                (
                    (index * 37) % 256,
                    (index * 71) % 256,
                    (index * 19) % 256,
                ),
            )
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 310, 230), outline="white", width=3)
            draw.text((20, 20), f"Benchmark {index + 1}", fill="white")

            buffer = BytesIO()
            image.save(
                buffer,
                format="PNG",
                compress_level=args.png_compression,
                optimize=False,
            )
            payload = buffer.getvalue()

            started = time.monotonic()
            connection.send_png(payload, retries=args.retries)
            elapsed = time.monotonic() - started

            sizes.append(len(payload))
            durations.append(elapsed)
            print(
                f"Frame {index + 1}/{args.frames}: "
                f"{len(payload) / 1024:.1f} KiB in {elapsed:.3f}s"
            )

    average_seconds = statistics.mean(durations)
    average_size = statistics.mean(sizes) / 1024
    fps = 1.0 / average_seconds if average_seconds > 0 else 0.0

    print()
    print(f"Average frame: {average_size:.1f} KiB")
    print(f"Average transfer: {average_seconds:.3f}s")
    print(f"Measured maximum: {fps:.2f} FPS")
    print(f"Recommended stable animation FPS: {max(1.0, fps * 0.75):.2f}")
    return 0


def media_prepare_cmd(args):
    source = Path(args.media).expanduser()
    output = (
        Path(args.output).expanduser()
        if args.output
        else source.with_name(f"{source.stem}-cp3.mp4")
    )

    try:
        result = prepare_media(
            source,
            output,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fit=args.fit,
            crf=args.crf,
            preset=args.preset,
        )
    except NativeMediaError as error:
        raise SystemExit(str(error))

    print(f"Prepared: {result.output}")
    print(f"Codec: {result.codec}")
    print(f"Geometry: {result.width}x{result.height}")
    print(f"Frame rate: {result.fps:.3f}")
    print(f"Size: {result.size / (1024 * 1024):.2f} MiB")
    return 0


def media_info_cmd(args):
    try:
        info = probe_media(args.media)
    except NativeMediaError as error:
        raise SystemExit(str(error))
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0


def media_upload_cmd(args):
    source = Path(args.media).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Media file not found: {source}")

    prepared = source
    if not args.no_prepare:
        prepared = (
            Path(args.prepared_output).expanduser().resolve()
            if args.prepared_output
            else temporary_prepared_path(source)
        )
        try:
            result = prepare_media(
                source,
                prepared,
                width=args.width,
                height=args.height,
                fps=args.fps,
                fit=args.fit,
                crf=args.crf,
                preset=args.preset,
            )
        except NativeMediaError as error:
            raise SystemExit(str(error))
        prepared = result.output
        print(
            f"Prepared {prepared.name}: "
            f"{result.width}x{result.height}, "
            f"{result.fps:.2f} FPS, "
            f"{result.size / (1024 * 1024):.2f} MiB"
        )

    remote_name = args.remote_name or prepared.name
    payload = prepared.read_bytes()

    print("Experimental native-media file transfer")
    print(f"Local file: {prepared}")
    print(f"Remote name: {remote_name}")
    print(f"Payload: {len(payload)} bytes")
    print(
        "This uses the confirmed POST transport / POST transported "
        "block-transfer envelope."
    )
    print(
        "The media-list/select command is not yet confirmed, so successful "
        "transfer does not guarantee that the LCD will display the file."
    )

    if not args.execute:
        print("Dry run only. Add --execute to send the file.")
        return 0

    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
    ) as connection:
        connection.send_file(
            payload,
            remote_name,
            retries=args.retries,
        )

    print("The CP3 accepted the file-transfer transaction.")
    print(
        "Next step: inspect the device/media response and recover the "
        "selection command."
    )
    return 0


def protocol_request_cmd(args):
    try:
        content = json.loads(args.json)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON: {error}")
    if not isinstance(content, dict):
        raise SystemExit("--json must decode to an object")

    sequence = args.sequence or 1000
    date_ms = args.date_ms or int(time.time() * 1000)
    preview = request_preview(
        args.method,
        sequence,
        date_ms,
        content,
    )

    if args.trace:
        trace_path = Path(args.trace).expanduser()
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            json.dumps(preview, indent=2),
            encoding="utf-8",
        )
        print(f"Request preview saved to {trace_path}")

    print(json.dumps(preview, indent=2))

    if not args.execute:
        print("Dry run only. Add --execute to send this request.")
        return 0

    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
    ) as connection:
        reply = connection.request(
            args.method,
            content,
            sequence=sequence,
            date_ms=date_ms,
        )

    result = {
        "status": reply.status,
        "ack_number": reply.ack_number,
        "content": reply.content,
        "raw_hex": reply.raw.hex(),
        "frame": describe_frame(reply.raw),
    }
    print(json.dumps(result, indent=2))

    if args.trace:
        reply_path = Path(args.trace).expanduser().with_suffix(
            ".reply.json"
        )
        reply_path.write_text(
            json.dumps(result, indent=2),
            encoding="utf-8",
        )
        print(f"Reply saved to {reply_path}")
    return 0


def protocol_catalog_cmd(_args):
    print(json.dumps(protocol_catalog(), indent=2))
    return 0


def protocol_decode_cmd(args):
    if args.hex:
        raw = bytes.fromhex(args.hex)
    else:
        raw = Path(args.file).expanduser().read_bytes()

    decoded = decode_packet_text(raw)
    print(json.dumps(decoded, indent=2))
    return 0


def protocol_trace_show_cmd(args):
    events = load_trace(args.trace)
    if args.summary:
        for event in events:
            print(
                f"{event.get('iso_time', '')} "
                f"{event.get('direction', ''):7} "
                f"{event.get('label', ''):20} "
                f"{len(event.get('raw_hex', '')) // 2} bytes"
            )
    else:
        print(json.dumps(events, indent=2))
    return 0


def protocol_replay_cmd(args):
    events = load_trace(args.trace)
    candidates = [
        event for event in events
        if event.get("direction") == "TX"
        and event.get("label") not in {
            "POST transport",
            "POST transported",
        }
    ]
    if not candidates:
        raise SystemExit(
            "No replayable non-file request was found in the trace."
        )

    index = args.index
    if index < 0 or index >= len(candidates):
        raise SystemExit(
            f"Replay index must be between 0 and {len(candidates) - 1}"
        )

    event = candidates[index]
    raw = bytes.fromhex(event["raw_hex"])
    decoded = decode_packet_text(raw)

    print(json.dumps(decoded, indent=2))
    if not args.execute:
        print("Dry run only. Add --execute to replay the packet.")
        return 0

    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
        recorder=ProtocolRecorder(args.output_trace)
        if args.output_trace
        else None,
    ) as connection:
        if not connection.port:
            raise SystemExit("Serial connection failed to open")
        connection.port.reset_input_buffer()
        connection.port.write(raw)
        connection.port.flush()
        reply = connection._reply(
            f"replay:{event.get('label', 'packet')}"
        )

    print(
        json.dumps(
            {
                "status": reply.status,
                "ack_number": reply.ack_number,
                "content": reply.content,
                "raw_hex": reply.raw.hex(),
            },
            indent=2,
        )
    )
    return 0


def protocol_probe_cmd(args):
    methods = [
        line.strip()
        for line in Path(args.methods).expanduser().read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not methods:
        raise SystemExit("No methods found in the methods file")

    if not args.execute:
        print("Probe plan:")
        for method in methods:
            print(f"  {method}")
        print("Dry run only. Add --execute to send requests.")
        return 0

    recorder = (
        ProtocolRecorder(args.trace)
        if args.trace
        else None
    )

    failures = 0
    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
        recorder=recorder,
    ) as connection:
        for method in methods:
            try:
                reply = connection.request(
                    method,
                    {},
                )
                failures = 0
                print(
                    f"{method}: status={reply.status} "
                    f"content={reply.content}"
                )
            except Exception as error:
                failures += 1
                print(f"{method}: no valid reply ({error})")
                if failures >= args.stop_after:
                    print(
                        f"Stopping after {failures} consecutive failures."
                    )
                    break
            time.sleep(args.interval)
    return 0


def native_media_state_path() -> Path:
    path = config_dir() / "native-media-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_native_media_state(data: dict) -> None:
    native_media_state_path().write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def media_loop_prepare_cmd(args):
    source = Path(args.media).expanduser()
    output = (
        Path(args.output).expanduser()
        if args.output
        else source.with_name(f"{source.stem}-cp3-loop.mp4")
    )

    try:
        result = prepare_looped_media(
            source,
            output,
            duration_minutes=args.duration_minutes,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fit=args.fit,
            crf=args.crf,
            preset=args.preset,
        )
    except NativeMediaError as error:
        raise SystemExit(str(error))

    print(f"Prepared long-loop MP4: {result.output}")
    print(f"Geometry: {result.width}x{result.height}")
    print(f"Frame rate: {result.fps:.3f}")
    print(f"Size: {result.size / (1024 * 1024):.2f} MiB")
    print(
        f"Approximate playback duration: "
        f"{args.duration_minutes:.1f} minutes"
    )
    return 0


def native_media_activate_cmd(args):
    source = Path(args.media).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Media file not found: {source}")

    prepared = (
        Path(args.prepared_output).expanduser().resolve()
        if args.prepared_output
        else source.with_name(f"{source.stem}-cp3-loop.mp4")
    )

    try:
        result = prepare_looped_media(
            source,
            prepared,
            duration_minutes=args.duration_minutes,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fit=args.fit,
            crf=args.crf,
            preset=args.preset,
        )
    except NativeMediaError as error:
        raise SystemExit(str(error))

    remote_name = args.remote_name or prepared.name
    print(
        f"Prepared native media: {prepared.name} "
        f"({result.size / (1024 * 1024):.2f} MiB)"
    )
    print(
        "Uploading this file will make it persistent on the CP3. "
        "The device has already been confirmed to play uploaded MP4 files "
        "after reboot."
    )
    print(
        "Linux does not yet know the Windows overlay/loop-control command. "
        "This build uses one long repeated MP4 as a temporary loop."
    )

    if not args.execute:
        print("Dry run only. Add --execute to upload and activate.")
        return 0

    recorder = (
        ProtocolRecorder(args.trace)
        if args.trace
        else None
    )

    with CP3Connection(
        args.device,
        args.timeout,
        args.chunk_delay,
        args.verbose,
        recorder=recorder,
    ) as connection:
        connection.send_file(
            prepared.read_bytes(),
            remote_name,
            retries=args.retries,
        )

    state = {
        "source": str(source),
        "prepared": str(prepared),
        "remote_name": remote_name,
        "duration_minutes": args.duration_minutes,
        "width": result.width,
        "height": result.height,
        "fps": result.fps,
        "size": result.size,
        "status": "uploaded",
        "notes": (
            "Native MP4 accepted. Windows is still required to restore "
            "hardware-info overlays until the control command is recovered."
        ),
    }
    save_native_media_state(state)

    print("Native MP4 upload completed successfully.")
    print(
        "Power-cycle the device if playback does not begin immediately. "
        "The CP3 should play the uploaded MP4 after boot."
    )
    return 0


def native_media_status_cmd(_args):
    path = native_media_state_path()
    if not path.is_file():
        print("No Linux native-media state has been recorded.")
        return 0
    print(path.read_text(encoding="utf-8"))
    return 0


def native_media_clear_state_cmd(_args):
    path = native_media_state_path()
    if path.exists():
        path.unlink()
    print(
        "Local native-media state cleared. "
        "This does not erase media stored on the CP3."
    )
    return 0

def _fmt_temp(value):
    return "--°C" if value is None else f"{value:.0f}°C"


def add_transport_options(command):
    command.add_argument("--device", default=default_device())
    command.add_argument("--timeout", type=float, default=4.0)
    command.add_argument("--chunk-delay", type=float, default=0.001)
    command.add_argument("--verbose", action="store_true")
    command.add_argument("--retries", type=int, default=2)


def main():
    parser = argparse.ArgumentParser(prog="pccooler-lcd")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    command = sub.add_parser("scan")
    command.set_defaults(func=scan_cmd)

    command = sub.add_parser("diagnose")
    command.add_argument("--device", default=default_device())
    command.set_defaults(func=diagnose_cmd)

    command = sub.add_parser(
        "inspect-device",
        help="Inspect CP3 serial and USB state",
    )
    command.add_argument("--device", default=default_device())
    command.add_argument("--json", action="store_true")
    command.set_defaults(func=inspect_device_cmd)

    command = sub.add_parser(
        "reset-device",
        help="Reset the CP3 through Linux USB sysfs",
    )
    command.add_argument("--device", default=default_device())
    command.add_argument(
        "--sudo",
        action="store_true",
        help="Use sudo only for the sysfs authorization writes",
    )
    command.add_argument("--disconnect-delay", type=float, default=1.0)
    command.add_argument("--reconnect-timeout", type=float, default=15.0)
    command.set_defaults(func=reset_device_cmd)

    command = sub.add_parser("send-image")
    command.add_argument("image")
    add_transport_options(command)
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--remote-name")
    command.set_defaults(func=send_image_cmd)

    command = sub.add_parser("dashboard")
    add_transport_options(command)
    command.add_argument("--interval", type=float, default=1.0)
    command.add_argument("--theme", choices=("cyber", "amber", "ice", "nasa"), default="cyber")
    command.add_argument("--title", default="PCCOOLER LINUX")
    command.add_argument("--background")
    command.add_argument("--background-gif")
    command.add_argument("--gif-fit", choices=("cover", "contain"), default="cover")
    command.add_argument("--gif-min-delay", type=float, default=0.08)
    command.add_argument("--panel-alpha", type=int, default=205)
    command.add_argument("--overlay-alpha", type=int, default=55)
    command.add_argument("--cpu-color")
    command.add_argument("--memory-color")
    command.add_argument("--gpu-color")
    command.add_argument("--text-color")
    command.add_argument("--panel-color")
    command.add_argument("--auto-colors", action="store_true")
    command.add_argument("--png-compression", type=int, default=1)
    command.add_argument("--count", type=int, default=0)
    command.add_argument("--preview")
    command.add_argument("--quiet", action="store_true")
    command.add_argument("--max-failures", type=int, default=10)
    command.add_argument("--recovery-delay", type=float, default=0.5)
    command.set_defaults(func=dashboard_cmd)

    command = sub.add_parser("play-gif")
    command.add_argument("gif")
    add_transport_options(command)
    command.add_argument("--loops", type=int, default=0)
    command.add_argument("--fit", choices=("cover", "contain"), default="cover")
    command.add_argument("--frame-delay", type=float)
    command.add_argument("--min-delay", type=float, default=0.06)
    command.add_argument("--png-compression", type=int, default=0)
    command.add_argument("--palette-colors", type=int, default=32)
    command.add_argument("--queue-depth", type=int, default=1)
    command.add_argument("--max-frames", type=int, default=0)
    command.add_argument("--no-frame-skip", action="store_true")
    command.add_argument("--difference-threshold", type=float, default=0.015)
    command.add_argument("--minimum-frame-duration", type=float, default=0.0)
    command.set_defaults(func=play_gif_cmd)

    command = sub.add_parser("layout-dashboard")
    command.add_argument("layout")
    add_transport_options(command)
    command.add_argument("--interval", type=float, default=1.0)
    command.add_argument("--count", type=int, default=0)
    command.add_argument("--quiet", action="store_true")
    command.add_argument("--png-compression", type=int, default=1)
    command.add_argument("--gif-min-delay", type=float, default=0.08)
    command.add_argument("--optimized-gif", action="store_true")
    command.add_argument("--palette-colors", type=int, default=96)
    command.set_defaults(func=layout_dashboard_cmd)

    command = sub.add_parser("media-layout-dashboard", help="Run a layout with any supported animated media background")
    command.add_argument("layout")
    add_transport_options(command)
    command.add_argument("--media-fps", type=float, default=6.0)
    command.add_argument("--png-compression", type=int, default=1)
    command.set_defaults(func=media_layout_dashboard_cmd)

    command = sub.add_parser(
        "play-video",
        help="Play a video full-screen using the media engine",
    )
    command.add_argument("video")
    add_transport_options(command)
    command.add_argument("--fps", type=float, default=1.6)
    command.add_argument(
        "--fit",
        choices=("cover", "contain"),
        default="cover",
    )
    command.add_argument("--palette-colors", type=int, default=32)
    command.add_argument("--png-compression", type=int, default=9)
    command.set_defaults(func=play_video_cmd)

    command = sub.add_parser(
        "benchmark-transfer",
        help="Measure realistic CP3 full-frame transfer speed",
    )
    add_transport_options(command)
    command.add_argument("--frames", type=int, default=10)
    command.add_argument("--png-compression", type=int, default=9)
    command.set_defaults(func=benchmark_transfer_cmd)

    command = sub.add_parser(
        "media-info",
        help="Inspect media with FFprobe",
    )
    command.add_argument("media")
    command.set_defaults(func=media_info_cmd)

    command = sub.add_parser(
        "media-prepare",
        help="Prepare an MP4 using recovered CP3 media settings",
    )
    command.add_argument("media")
    command.add_argument("--output")
    command.add_argument("--width", type=int, default=320)
    command.add_argument("--height", type=int, default=240)
    command.add_argument("--fps", type=float, default=30.0)
    command.add_argument(
        "--fit",
        choices=("cover", "contain"),
        default="cover",
    )
    command.add_argument("--crf", type=int, default=23)
    command.add_argument("--preset", default="medium")
    command.set_defaults(func=media_prepare_cmd)

    command = sub.add_parser(
        "media-upload",
        help="Experimentally upload prepared media using CP3 block transfer",
    )
    command.add_argument("media")
    add_transport_options(command)
    command.add_argument("--execute", action="store_true")
    command.add_argument("--no-prepare", action="store_true")
    command.add_argument("--prepared-output")
    command.add_argument("--remote-name")
    command.add_argument("--width", type=int, default=320)
    command.add_argument("--height", type=int, default=240)
    command.add_argument("--fps", type=float, default=30.0)
    command.add_argument(
        "--fit",
        choices=("cover", "contain"),
        default="cover",
    )
    command.add_argument("--crf", type=int, default=23)
    command.add_argument("--preset", default="medium")
    command.set_defaults(func=media_upload_cmd)

    command = sub.add_parser(
        "protocol-request",
        help="Preview or send a raw CP3 request envelope",
    )
    command.add_argument("method")
    command.add_argument("--json", default="{}")
    command.add_argument("--sequence", type=int)
    command.add_argument("--date-ms", type=int)
    command.add_argument("--trace")
    command.add_argument(
        "--session-trace",
        help="Record actual TX/RX packets to JSON",
    )
    command.add_argument("--execute", action="store_true")
    add_transport_options(command)
    command.set_defaults(func=protocol_request_cmd)

    command = sub.add_parser(
        "protocol-catalog",
        help="Show confirmed and unknown CP3 protocol operations",
    )
    command.set_defaults(func=protocol_catalog_cmd)

    command = sub.add_parser(
        "protocol-decode",
        help="Decode a CP3 packet from hex or a binary file",
    )
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--hex")
    source.add_argument("--file")
    command.set_defaults(func=protocol_decode_cmd)

    command = sub.add_parser(
        "protocol-trace-show",
        help="Display a saved protocol trace",
    )
    command.add_argument("trace")
    command.add_argument("--summary", action="store_true")
    command.set_defaults(func=protocol_trace_show_cmd)

    command = sub.add_parser(
        "protocol-replay",
        help="Replay one non-file TX packet from a trace",
    )
    command.add_argument("trace")
    command.add_argument("--index", type=int, default=0)
    command.add_argument("--execute", action="store_true")
    command.add_argument("--output-trace")
    add_transport_options(command)
    command.set_defaults(func=protocol_replay_cmd)

    command = sub.add_parser(
        "protocol-probe",
        help="Rate-limited probing from a text file of candidate methods",
    )
    command.add_argument("methods")
    command.add_argument("--execute", action="store_true")
    command.add_argument("--interval", type=float, default=1.0)
    command.add_argument("--stop-after", type=int, default=5)
    command.add_argument("--trace")
    add_transport_options(command)
    command.set_defaults(func=protocol_probe_cmd)

    command = sub.add_parser(
        "media-loop-prepare",
        help="Create one long repeated MP4 for native CP3 playback",
    )
    command.add_argument("media")
    command.add_argument("--output")
    command.add_argument("--duration-minutes", type=float, default=60.0)
    command.add_argument("--width", type=int, default=320)
    command.add_argument("--height", type=int, default=240)
    command.add_argument("--fps", type=float, default=30.0)
    command.add_argument(
        "--fit",
        choices=("cover", "contain"),
        default="cover",
    )
    command.add_argument("--crf", type=int, default=23)
    command.add_argument("--preset", default="medium")
    command.set_defaults(func=media_loop_prepare_cmd)

    command = sub.add_parser(
        "native-media-activate",
        help="Prepare and upload a persistent long-loop MP4",
    )
    command.add_argument("media")
    add_transport_options(command)
    command.add_argument("--execute", action="store_true")
    command.add_argument("--prepared-output")
    command.add_argument("--remote-name")
    command.add_argument("--duration-minutes", type=float, default=60.0)
    command.add_argument("--width", type=int, default=320)
    command.add_argument("--height", type=int, default=240)
    command.add_argument("--fps", type=float, default=30.0)
    command.add_argument(
        "--fit",
        choices=("cover", "contain"),
        default="cover",
    )
    command.add_argument("--crf", type=int, default=23)
    command.add_argument("--preset", default="medium")
    command.add_argument("--trace")
    command.set_defaults(func=native_media_activate_cmd)

    command = sub.add_parser(
        "native-media-status",
        help="Show the last Linux native-media upload state",
    )
    command.set_defaults(func=native_media_status_cmd)

    command = sub.add_parser(
        "native-media-clear-state",
        help="Clear local native-media state without touching the CP3",
    )
    command.set_defaults(func=native_media_clear_state_cmd)

    command = sub.add_parser(
        "startup-dashboard",
        help="Run the layout selected for automatic startup",
    )
    add_transport_options(command)
    command.add_argument("--interval", type=float, default=1.0)
    command.add_argument("--png-compression", type=int, default=1)
    command.add_argument("--gif-min-delay", type=float, default=0.05)
    command.add_argument("--palette-colors", type=int, default=96)
    command.add_argument("--video-fps", type=float, default=6.0)
    command.set_defaults(func=startup_dashboard_cmd)

    command = sub.add_parser("screensaver")
    command.add_argument("gif")
    add_transport_options(command)
    command.add_argument("--fit", choices=("cover", "contain"), default="cover")
    command.add_argument("--frame-delay", type=float)
    command.add_argument("--min-delay", type=float, default=0.06)
    command.add_argument("--png-compression", type=int, default=0)
    command.add_argument("--palette-colors", type=int, default=32)
    command.add_argument("--queue-depth", type=int, default=1)
    command.add_argument("--max-frames", type=int, default=0)
    command.add_argument("--no-frame-skip", action="store_true")
    command.add_argument("--difference-threshold", type=float, default=0.015)
    command.add_argument("--minimum-frame-duration", type=float, default=0.0)
    command.set_defaults(
        func=lambda args: play_gif_cmd(
            argparse.Namespace(**{**vars(args), "loops": 0})
        )
    )

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
