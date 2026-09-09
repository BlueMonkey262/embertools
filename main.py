#!/usr/bin/env python3
"""embertools entry point.

CLI is the primary interface:

    python3 main.py list
    python3 main.py apply launcher_swap --launcher nova
    python3 main.py status
    python3 main.py revert

The GUI (work in progress) launches with:

    python3 main.py --ui
"""

import sys
import webbrowser
from pathlib import Path


def _launch_ui() -> int:
    gui = Path(__file__).resolve().parent / "embertools" / "ui_app" / "index.html"
    if gui.exists():
        webbrowser.open(gui.as_uri())
        return 0
    mock = Path(__file__).resolve().parent / "docs" / "mockups" / "mockup-1.html"
    print("The embertools GUI isn't built yet — opening the design mockup instead.")
    print("For now, use the CLI:  python3 main.py list")
    if mock.exists():
        webbrowser.open(mock.as_uri())
    return 0


def main() -> None:
    if "--ui" in sys.argv[1:]:
        sys.exit(_launch_ui())
    from embertools.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
