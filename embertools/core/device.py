"""Detect the connected Fire tablet and look it up in the model registry."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .adb import Adb
from ..models.registry import MODELS


@dataclass
class Device:
    serial: str
    model: str                 # e.g. "KFMAWI"
    fireos_str: str            # e.g. "Fire OS 7.3.3.1 (PS7331/4463)"
    fireos_major: int          # 5 / 6 / 7 / 8, 0 if unknown
    sdk: int                   # API level, e.g. 28
    abi: str                   # e.g. "armeabi-v7a"
    name: str = "Unknown Fire tablet"
    soc: str = ""
    known: bool = False
    quirks: list[str] = field(default_factory=list)

    @classmethod
    def detect(cls, adb: Adb) -> "Device":
        model = adb.getprop("ro.product.model") or "unknown"
        fireos_str = (adb.getprop("ro.build.version.name")
                      or adb.getprop("ro.build.mktg.fireos") or "")
        m = re.search(r"(?:Fire OS|Fire ?OS)\s*(\d+)", fireos_str)
        if not m:
            m = re.search(r"\b(\d+)\.\d+", fireos_str)
        fireos_major = int(m.group(1)) if m else 0
        try:
            sdk = int(adb.getprop("ro.build.version.sdk") or 0)
        except ValueError:
            sdk = 0
        abi = adb.getprop("ro.product.cpu.abi") or ""

        dev = cls(serial=adb.serial or "?", model=model, fireos_str=fireos_str,
                  fireos_major=fireos_major, sdk=sdk, abi=abi)

        entry = MODELS.get(model)
        if entry:
            dev.known = True
            dev.name = entry.get("name", dev.name)
            dev.soc = entry.get("soc", "")
            dev.quirks = list(entry.get("quirks", []))
            if not dev.fireos_major and entry.get("fireos"):
                dev.fireos_major = int(str(entry["fireos"]).split("-")[0])
        return dev

    def describe(self) -> str:
        tag = "" if self.known else "  (not in registry -- generic mode)"
        return f"{self.name} [{self.model}]  {self.fireos_str or 'Fire OS ?'}{tag}"
