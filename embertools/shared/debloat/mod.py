"""debloat -- disable Amazon consumer apps.

Uses `pm disable-user --user 0` (sticks across reboot; Fire OS reverts
`pm uninstall` on boot).  Disabled apps lose their launcher entry, so they also
vanish from a third-party launcher's app drawer.  Fully reversible.
"""

from __future__ import annotations

import re
from pathlib import Path

from embertools.core.mod import Mod, Meta, Status

HERE = Path(__file__).resolve().parent


def _load_list(fireos_major: int) -> list[str]:
    f = HERE / "lists" / f"fireos{fireos_major}.txt"
    if not f.exists():
        f = HERE / "lists" / "fireos7.txt"
    pkgs = []
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pkgs.append(line)
    return pkgs


class Debloat(Mod):
    meta = Meta(
        name="debloat",
        summary="Disable Amazon apps (Prime Video, Alexa, Silk, Kindle, lock-screen ads, ...)",
        supported=["*"],
        fireos=[6, 7, 8],
        reversible=True,
        risk="low",
        order=30,
    )

    def _pkgs(self, ctx) -> list[str]:
        return _load_list(ctx.dev.fireos_major or 7)

    def status(self, ctx) -> Status:
        pkgs = self._pkgs(ctx)
        disabled = ctx.adb.shell("pm list packages -d")
        n = sum(1 for p in pkgs if f"package:{p}" in disabled)
        return Status(n > len(pkgs) // 2, f"{n}/{len(pkgs)} disabled")

    def apply(self, ctx) -> None:
        protected, done, absent = [], 0, 0
        for p in self._pkgs(ctx):
            r = ctx.adb.shell(f"pm disable-user --user 0 {p}")
            if "new state: disabled" in r:
                done += 1
            elif "protected" in r:
                protected.append(p)
            elif "Unable to find" in r or not r.strip():
                absent += 1
            else:
                ctx.log(f"  {p}: {r.splitlines()[0][:60]}")
        ctx.log(f"disabled {done}, absent {absent}, protected {len(protected)}")
        if protected:
            ctx.log("protected (can't disable via ADB -- hide them in your launcher's "
                    "app drawer): " + ", ".join(protected))
        ctx.state.mark_applied(self.meta.name, {"count": done})

    def revert(self, ctx) -> None:
        n = 0
        for p in self._pkgs(ctx):
            r = ctx.adb.shell(f"pm enable {p}")
            if "enabled" in r:
                n += 1
        ctx.log(f"re-enabled {n}")
        ctx.state.mark_reverted(self.meta.name)


MOD = Debloat()
