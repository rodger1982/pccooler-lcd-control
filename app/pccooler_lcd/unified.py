from __future__ import annotations

import sys


CLI_COMMANDS = {
    "scan",
    "diagnose",
    "send-image",
    "dashboard",
    "layout-dashboard",
    "startup-dashboard",
    "play-gif",
    "screensaver",
    "play-video",
    "video-layout-dashboard",
}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in {"gui", "studio", "designer"}:
        from .qt.app import main as gui_main
        if args:
            sys.argv = [sys.argv[0], *args[1:]]
        gui_main()
        return

    if args[0] in {"--help", "-h"}:
        print(
            "PCCOOLER-LCD Control\n\n"
            "Usage:\n"
            "  pccooler-lcd-control            Open the Qt application\n"
            "  pccooler-lcd-control gui        Open the Qt application\n"
            "  pccooler-lcd-control scan       Find supported displays\n"
            "  pccooler-lcd-control dashboard  Run the default dashboard\n"
            "  pccooler-lcd-control startup-dashboard\n"
            "  pccooler-lcd-control play-gif FILE\n"
            "  pccooler-lcd-control play-video FILE\n"
        )
        return

    if args[0] not in CLI_COMMANDS and args[0] != "--version":
        raise SystemExit(f"Unknown command: {args[0]}")

    from .cli import main as cli_main
    sys.argv = ["pccooler-lcd", *args]
    cli_main()


if __name__ == "__main__":
    main()
