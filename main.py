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
    try:
        from embertools.ui_app.launch import main as ui_main
    except ImportError:
        mock = Path(__file__).resolve().parent / "docs" / "mockups" / "mockup-1.html"
        print("Could not load the GUI; opening the design mockup instead.")
        print("Use the CLI:  python3 main.py list")
        if mock.exists():
            webbrowser.open(mock.as_uri())
        return 0
    ui_main()
    return 0


def main() -> None:
    if "--ui" in sys.argv[1:]:
        sys.exit(_launch_ui())
    from embertools.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
