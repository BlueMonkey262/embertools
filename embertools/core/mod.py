"""Mod interface + discovery.

A mod is a directory under ``shared/`` (or ``models/<CODE>/``) containing a
``mod.py`` that defines a module-level ``MOD`` -- an instance of a ``Mod``
subclass.  The loader imports every such file and keeps the ones whose
``supports(device)`` returns True.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
MODELS = ROOT / "models"


@dataclass
class Meta:
    name: str
    summary: str
    supported: list[str] = field(default_factory=lambda: ["*"])  # model codes or ["*"]
    fireos: list[int] | None = None       # e.g. [7] or [7, 8]; None = any
    needs_build: bool = False
    reversible: bool = True
    risk: str = "low"                      # low | medium | high
    order: int = 100                       # lower applies earlier in "apply all"
    options: list[dict] = field(default_factory=list)


@dataclass
class Status:
    applied: bool | None                   # True / False / None (unknown)
    detail: str = ""


class Mod:
    meta: Meta

    def supports(self, dev) -> bool:
        if "*" not in self.meta.supported and dev.model not in self.meta.supported:
            return False
        if self.meta.fireos is not None and dev.fireos_major not in self.meta.fireos:
            return False
        return True

    # subclasses implement these
    def status(self, ctx) -> Status:        # noqa: D401
        return Status(None)

    def apply(self, ctx) -> None:
        raise NotImplementedError

    def verify(self, ctx) -> Status:
        return Status(None, "")

    def revert(self, ctx) -> None:
        raise NotImplementedError


@dataclass
class Context:
    adb: Any
    dev: Any
    state: Any
    opts: dict = field(default_factory=dict)
    on_log: Any = None

    def log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)
        print(f"  {msg}")

    def build_helper(self, helper_dir: Path) -> Path:
        from .build import build_apk
        return build_apk(helper_dir)


def _load_mod_file(path: Path) -> Mod | None:
    spec = importlib.util.spec_from_file_location(f"embertools_mod_{path.parent.name}", path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mod = getattr(module, "MOD", None)
    return mod if isinstance(mod, Mod) else None


def discover(dev) -> list[Mod]:
    """All mods applicable to this device, sorted by order then name."""
    found: dict[str, Mod] = {}
    search = list(SHARED.glob("*/mod.py"))
    if dev.model:
        search += list((MODELS / dev.model).glob("*/mod.py"))
    for f in search:
        try:
            m = _load_mod_file(f)
        except Exception as e:  # a broken mod shouldn't kill the whole tool
            print(f"  ! skipping {f.parent.name}: {e}")
            continue
        if m and m.supports(dev):
            found[m.meta.name] = m           # model-specific overrides shared (loaded later)
    return sorted(found.values(), key=lambda m: (m.meta.order, m.meta.name))
