"""ota_block -- stop Fire OS from auto-updating.

Updates re-enable debloated apps, wipe launcher_swap's settings, and can patch
the mechanisms embertools relies on.  Blocking OTA keeps your changes stable.

Method (all no-root, all reversible):
  1. Settings.Global `ota_disable_automatic_update = 1` -- the documented Fire OS
     knob; works on every build tested.
  2. `pm disable-user` the OTA packages -- works on older Fire OS; newer builds
     mark them "protected" and this is skipped (the setting above still applies).

Run this FIRST.  To update deliberately later: `embertools revert ota_block`,
update, then re-apply.
"""

from __future__ import annotations

from embertools.core.mod import Mod, Meta, Status

SETTING = "ota_disable_automatic_update"
OTA_PKGS = [
    "com.amazon.device.software.ota",
    "com.amazon.device.software.ota.override",
    "com.amazon.settings.systemupdates",
    "com.amazon.otaverifier",
]


class OtaBlock(Mod):
    meta = Meta(
        name="ota_block",
        summary="Block automatic Fire OS updates (do this first)",
        supported=["*"],
        fireos=[5, 6, 7, 8],
        reversible=True,
        risk="medium",
        order=10,
    )

    def status(self, ctx) -> Status:
        setting_on = ctx.adb.get_global(SETTING) == "1"
        disabled = ctx.adb.shell("pm list packages -d")
        present = [p for p in OTA_PKGS if ctx.adb.pkg_installed(p)]
        n_dis = sum(1 for p in present if f"package:{p}" in disabled)
        detail = f"auto-update setting {'OFF' if setting_on else 'ON'}"
        if present:
            detail += f", {n_dis}/{len(present)} OTA pkgs disabled"
        return Status(setting_on, detail)

    def apply(self, ctx) -> None:
        ctx.adb.put_global(SETTING, "1")
        ok = ctx.adb.get_global(SETTING) == "1"
        ctx.log(f"{SETTING} -> 1  ({'ok' if ok else 'FAILED'})")

        protected = 0
        for p in OTA_PKGS:
            if not ctx.adb.pkg_installed(p):
                continue
            r = ctx.adb.shell(f"pm disable-user --user 0 {p}")
            if "new state: disabled" in r:
                ctx.log(f"  disabled {p}")
            elif "protected" in r:
                protected += 1
            else:
                ctx.log(f"  {p}: {r.splitlines()[0][:60]}")
        if protected:
            ctx.log(f"  {protected} OTA package(s) are protected on this build and "
                    f"stay enabled -- the auto-update setting still applies.")

        if not ok:
            raise RuntimeError("could not set the auto-update flag")
        ctx.log("Automatic updates blocked.")
        ctx.state.mark_applied(self.meta.name)

    def revert(self, ctx) -> None:
        ctx.adb.put_global(SETTING, "0")
        for p in OTA_PKGS:
            if ctx.adb.pkg_installed(p):
                ctx.adb.shell(f"pm enable {p}")
        ctx.state.mark_reverted(self.meta.name)
        ctx.log("OTA re-enabled.")


MOD = OtaBlock()
