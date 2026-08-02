from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .paths import ensure_tree


@dataclass(slots=True)
class Settings:
    device: str = "/dev/pccooler-lcd"
    refresh_interval: float = 1.0
    video_fps: float = 6.0
    gif_min_delay: float = 0.05
    palette_colors: int = 96
    start_at_login: bool = False
    last_layout: str = ""


def load_settings() -> Settings:
    path = ensure_tree()["settings"]
    if not path.is_file():
        settings = Settings()
        save_settings(settings)
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        valid = {
            key: value
            for key, value in data.items()
            if key in Settings.__dataclass_fields__
        }
        return Settings(**valid)
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    path = ensure_tree()["settings"]
    path.write_text(
        json.dumps(asdict(settings), indent=2),
        encoding="utf-8",
    )
