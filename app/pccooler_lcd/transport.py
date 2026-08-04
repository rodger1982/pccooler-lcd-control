from __future__ import annotations

import random
import time

import serial

from .device import resolve_device
from .platform import default_device, is_windows
from .protocol_cp3 import (
    announce_frame,
    complete_frame,
    generated_filename,
    parse_png_dimensions,
    make_request,
    parse_reply,
    read_frame,
)


class TransferError(RuntimeError):
    pass


class CP3Connection:
    """Persistent serial connection for the CP3 LCD controller."""

    def __init__(
        self,
        device: str | None = None,
        timeout: float = 4.0,
        chunk_delay: float = 0.002,
        verbose: bool = False,
    ) -> None:
        self.device = device or default_device()
        self.timeout = timeout
        self.chunk_delay = chunk_delay
        self.verbose = verbose
        self.path: str | None = None
        self.port: serial.Serial | None = None

    def open(self) -> None:
        if self.port and self.port.is_open:
            return
        self.path = resolve_device(self.device)
        serial_options = {
            "port": self.path,
            "baudrate": 115200,
            "timeout": 0.15,
            "write_timeout": 3,
        }
        if not is_windows():
            serial_options["exclusive"] = True
        self.port = serial.Serial(**serial_options)
        self.port.reset_input_buffer()
        self.port.reset_output_buffer()

    def close(self) -> None:
        if self.port:
            try:
                self.port.close()
            finally:
                self.port = None

    def reconnect(self, delay: float = 0.25) -> None:
        self.close()
        time.sleep(delay)
        self.open()

    def __enter__(self) -> "CP3Connection":
        self.open()
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _reply(self, label: str):
        if not self.port:
            raise TransferError("Serial connection is not open")
        raw = read_frame(self.port, self.timeout)
        reply = parse_reply(raw)
        if self.verbose:
            print(f"{label} raw: {raw.hex() if raw else 'none'}")
            print(
                f"{label}: status={reply.status}, "
                f"ack={reply.ack_number}, content={reply.content}"
            )
        if not reply.successful:
            raise TransferError(
                f"{label} failed: display did not return status 200"
            )
        return reply


def request(
    self,
    method: str,
    content: dict,
    *,
    sequence: int | None = None,
    date_ms: int | None = None,
):
    if not self.port:
        raise TransferError("Serial connection is not open")
    sequence = sequence or random.randint(100, 60000)
    date_ms = date_ms or int(time.time() * 1000)
    packet = make_request(method, sequence, date_ms, content)
    self.port.reset_input_buffer()
    self.port.write(packet)
    self.port.flush()
    return self._reply(method)

def send_file(
    self,
    payload: bytes,
    remote_name: str,
    retries: int = 2,
) -> None:
    if not payload:
        raise ValueError("Cannot upload an empty file")
    if not remote_name or "/" in remote_name or "\\" in remote_name:
        raise ValueError("remote_name must be a simple filename")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            self.open()
            self._send_once(payload, remote_name)
            return
        except (
            TransferError,
            serial.SerialException,
            OSError,
        ) as error:
            last_error = error
            if attempt >= retries:
                break
            delay = 0.30 * (attempt + 1)
            print(
                f"File-transfer attempt {attempt + 1} failed: "
                f"{error}; reconnecting in {delay:.2f}s..."
            )
            self.reconnect(delay)

    raise TransferError(
        f"File transfer failed after {retries + 1} attempts: "
        f"{last_error}"
    )

    def send_png(
        self,
        image: bytes,
        remote_name: str | None = None,
        retries: int = 2,
    ) -> None:
        width, height = parse_png_dimensions(image)
        if (width, height) != (320, 240):
            raise ValueError(f"Expected a 320x240 PNG, got {width}x{height}")

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                self.open()
                self._send_once(image, remote_name)
                return
            except (
                TransferError,
                serial.SerialException,
                OSError,
            ) as error:
                last_error = error
                if attempt >= retries:
                    break
                delay = 0.30 * (attempt + 1)
                print(
                    f"Transfer attempt {attempt + 1} failed: {error}; "
                    f"reconnecting in {delay:.2f}s..."
                )
                self.reconnect(delay)

        raise TransferError(
            f"Image transfer failed after {retries + 1} attempts: {last_error}"
        )

    def _send_once(self, image: bytes, remote_name: str | None) -> None:
        if not self.port:
            raise TransferError("Serial connection is not open")

        file_name = remote_name or generated_filename()
        sequence = random.randint(100, 60000)
        date_ms = int(time.time() * 1000)

        self.port.reset_input_buffer()
        self.port.write(
            announce_frame(sequence, date_ms, file_name, len(image))
        )
        self.port.flush()
        announcement = self._reply("announce")

        block_size = 1000
        if announcement.content and announcement.content.get("blockMaxSize"):
            block_size = min(
                1000, int(announcement.content["blockMaxSize"])
            )

        for offset in range(0, len(image), block_size):
            self.port.write(image[offset : offset + block_size])
            self.port.flush()
            if self.chunk_delay:
                time.sleep(self.chunk_delay)

        self._reply("image")

        completion = complete_frame(
            sequence + 1, date_ms + 1, file_name
        )
        for completion_attempt in range(3):
            self.port.write(completion)
            self.port.flush()
            try:
                self._reply("complete")
                return
            except TransferError:
                if completion_attempt >= 2:
                    raise
                if self.verbose:
                    print("Final ACK missing; retrying completion frame...")
                time.sleep(0.15 * (completion_attempt + 1))
                self.port.reset_input_buffer()
