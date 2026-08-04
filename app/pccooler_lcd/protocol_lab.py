from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import time


@dataclass(slots=True)
class ProtocolEvent:
    timestamp: float
    direction: str
    label: str
    raw_hex: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["iso_time"] = datetime.fromtimestamp(
            self.timestamp,
            tz=timezone.utc,
        ).isoformat()
        return result


class ProtocolRecorder:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path).expanduser().resolve()
            if path
            else None
        )
        self.events: list[ProtocolEvent] = []

    def record(
        self,
        direction: str,
        label: str,
        raw: bytes,
        **metadata: Any,
    ) -> None:
        event = ProtocolEvent(
            timestamp=time.time(),
            direction=direction,
            label=label,
            raw_hex=raw.hex(),
            metadata=metadata,
        )
        self.events.append(event)
        if self.path is not None:
            self.flush()

    def flush(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [event.to_dict() for event in self.events],
                indent=2,
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.events.clear()
        self.flush()


CONFIRMED_COMMANDS = {
    "POST transport": {
        "status": "confirmed",
        "purpose": "Announce a file transfer",
        "risk": "low",
    },
    "POST transported": {
        "status": "confirmed",
        "purpose": "Finalize a completed file transfer",
        "risk": "low",
    },
}

UNKNOWN_COMMANDS = {
    "GET media": {
        "status": "unsupported-or-unknown",
        "result": "no reply",
    },
    "GET mediaList": {
        "status": "unsupported-or-unknown",
        "result": "no reply",
    },
    "GET fileList": {
        "status": "unsupported-or-unknown",
        "result": "no reply",
    },
    "GET storage": {
        "status": "unsupported-or-unknown",
        "result": "no reply",
    },
}


def protocol_catalog() -> dict[str, Any]:
    return {
        "confirmed": CONFIRMED_COMMANDS,
        "unknown": UNKNOWN_COMMANDS,
        "notes": [
            "Electron IPC channel names are not necessarily wire methods.",
            "Unknown requests must be treated as experimental.",
            "Destructive probing is intentionally disabled.",
        ],
    }


def load_trace(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).expanduser()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Trace file must contain a JSON list")
    return data
