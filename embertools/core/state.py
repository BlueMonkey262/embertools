"""What embertools has changed on a device.

Two copies are kept so the record survives moving to another computer:

* local   -- ~/.embertools/state/<serial>.json  (fast, offline history)
* device  -- /data/local/tmp/embertools.json     (travels with the tablet;
             survives reboot, wiped only by a factory reset)

On load the two are merged (device wins on conflict).  `apply` / `revert` write
both.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

HOME = Path.home() / ".embertools"
STATE_DIR = HOME / "state"
DEVICE_PATH = "/data/local/tmp/embertools.json"


class State:
    def __init__(self, adb):
        self.adb = adb
        self.serial = adb.serial or "unknown"
        self.local = STATE_DIR / f"{self.serial}.json"
        self.data = {"serial": self.serial, "mods": {}}

        local = _read_json_file(self.local)
        device = _read_json_text(adb.shell(f"cat {DEVICE_PATH} 2>/dev/null"))
        for src in (local, device):                 # device merged last -> wins
            if src and isinstance(src.get("mods"), dict):
                self.data["mods"].update(src["mods"])

    # -- writes -----------------------------------------------------------

    def _flush(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(self.data, indent=2)
        self.local.write_text(blob)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            tf.write(blob)
            tmp = tf.name
        try:
            self.adb.push(tmp, DEVICE_PATH)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def mark_applied(self, mod: str, opts: dict | None = None) -> None:
        self.data["mods"][mod] = {"at": _now(), "opts": opts or {}}
        self._flush()

    def mark_reverted(self, mod: str) -> None:
        self.data["mods"].pop(mod, None)
        self._flush()

    # -- reads ----------------------------------------------------------

    def is_applied(self, mod: str) -> bool:
        return mod in self.data["mods"]

    def opts(self, mod: str) -> dict:
        return self.data["mods"].get(mod, {}).get("opts", {})

    def applied_mods(self) -> list[str]:
        return sorted(self.data["mods"].keys())


def _read_json_file(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _read_json_text(s: str) -> dict | None:
    s = (s or "").strip()
    if not s or s.startswith("cat:") or "No such file" in s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
