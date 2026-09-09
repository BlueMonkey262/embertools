"""Open the embertools GUI in a real window instead of a browser tab.

Order of preference, all optional, no Electron:
  1. pywebview  -> a native OS webview window   (pip install embertools[gui])
  2. Chrome / Edge / Brave / Chromium `--app`  -> a chromeless app window
  3. the default browser (plain tab)           -> fallback
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

from . import server

WIN_W, WIN_H = 1120, 760
UIDATA = Path.home() / ".embertools" / "uidata"

_CHROMIUM_NAMES = [
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    "brave-browser", "microsoft-edge", "microsoft-edge-stable",
]
_CHROMIUM_MAC = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
_CHROMIUM_WIN = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
]


def find_chromium() -> str | None:
    for name in _CHROMIUM_NAMES:
        p = shutil.which(name)
        if p:
            return p
    cands = _CHROMIUM_MAC if platform.system() == "Darwin" else (
        _CHROMIUM_WIN if platform.system() == "Windows" else [])
    for p in cands:
        if Path(p).exists():
            return p
    return None


def _free_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


def open_window(url: str) -> None:
    if os.environ.get("EMBERTOOLS_UI_NO_WINDOW"):
        print(f"(EMBERTOOLS_UI_NO_WINDOW set — not opening a window) {url}")
        return

    # 1. pywebview
    try:
        import webview  # type: ignore
        webview.create_window("embertools", url, width=WIN_W, height=WIN_H)
        webview.start()
        return
    except ImportError:
        pass
    except Exception as e:  # webview present but failed to start
        print(f"pywebview window failed ({e}); falling back", file=sys.stderr)

    # 2. Chromium app mode -- own profile dir so it never touches the user's
    #    running browser; terminate it cleanly when this returns.
    chrome = find_chromium()
    if chrome:
        UIDATA.mkdir(parents=True, exist_ok=True)
        proc = None
        try:
            proc = subprocess.Popen([
                chrome, f"--app={url}",
                f"--window-size={WIN_W},{WIN_H}",
                f"--user-data-dir={UIDATA}",
                "--no-first-run", "--no-default-browser-check",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
            return
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"chrome --app failed ({e}); falling back", file=sys.stderr)
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
        if proc is not None:
            return

    # 3. plain tab
    print("Opening embertools in your browser. For a real window, "
          "`pip install pywebview` or install Chrome/Edge/Brave.")
    webbrowser.open(url)
    try:
        input("embertools GUI running — press Enter to stop.\n")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> None:
    port = _free_port(8765)
    httpd = server.start("127.0.0.1", port)
    url = server.url_for(httpd)
    print(f"embertools GUI: {url}")
    try:
        open_window(url)
    finally:
        httpd.shutdown()
        httpd.server_close()
