"""launcher_swap -- use a third-party launcher as the real default on locked
Fire OS, with an instant redirect (no ~4.5s app-switch-lock delay).

Mechanism:
  1. Install a small AccessibilityService helper that, whenever the stock
     launcher comes to the foreground, immediately starts your chosen launcher.
  2. Register that helper as the device's voice-interaction ("assistant")
     service.  Android grants the assistant's uid a standing exemption from the
     post-Home app-switch lock (ActivityManagerService.mAllowAppSwitchUids, set
     by VoiceInteractionManagerService) -- which is what makes step 1 instant.

Neither step needs root or unlocking.  A Fire OS update wipes the secure
settings; just re-run this mod.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from embertools.core.mod import Mod, Meta, Status
from embertools.core.build import helper_package

HERE = Path(__file__).resolve().parent
HELPER = HERE / "helper"

TARGET_FILE = "/data/local/tmp/embertools_target"


def _components(pkg: str) -> dict:
    return {
        "app": pkg,
        "acc": f"{pkg}/{pkg}.RedirectService",
        "vis": f"{pkg}/{pkg}.AssistShimService",
        "rec": f"{pkg}/{pkg}.AssistRecognitionService",
        "main": f"{pkg}/{pkg}.MainActivity",
    }

LAUNCHERS = {
    "nova":        ("com.teslacoilsw.launcher", "com.teslacoilsw.launcher.NovaLauncher"),
    "lawnchair":   ("ch.deletescape.lawnchair", "ch.deletescape.lawnchair.Launcher"),
    "lawnchair2":  ("app.lawnchair", "app.lawnchair.LawnchairLauncher"),
    "kvaesitso":   ("de.mm20.launcher2.release", "de.mm20.launcher2.ui.launcher.LauncherActivity"),
    "niagara":     ("bitpit.launcher", "bitpit.launcher.MainActivity"),
    "smart":       ("ginlemon.flowerfree", "ginlemon.flower.HomeScreen"),
    "olauncher":   ("app.olauncher", "app.olauncher.MainActivity"),
}


def resolve_target(spec: str) -> tuple[str, str]:
    spec = (spec or "nova").strip()
    if spec.lower() in LAUNCHERS:
        return LAUNCHERS[spec.lower()]
    if "/" in spec:
        pkg, act = spec.split("/", 1)
        if act.startswith("."):
            act = pkg + act
        return pkg, act
    return spec, spec + ".Launcher"


class LauncherSwap(Mod):
    meta = Meta(
        name="launcher_swap",
        summary="Use Nova / Lawnchair / any launcher as default (instant redirect, no root)",
        supported=["KFMAWI", "KFTRWI", "KFTRPWI", "KFONWI", "KFMUWI", "KFKAWI"],
        fireos=[7],
        needs_build=True,
        reversible=True,
        risk="low",
        order=50,
        options=[
            {"name": "launcher", "label": "Target launcher", "type": "choice",
             "choices": list(LAUNCHERS), "default": "nova"},
            {"name": "reboot", "label": "Reboot after (most reliable)", "type": "bool",
             "default": True},
        ],
    )

    # -- helpers --------------------------------------------------------

    def _target(self, ctx) -> tuple[str, str]:
        return resolve_target(ctx.opts.get("launcher", "nova"))

    def _exempt_line(self, ctx) -> str:
        for l in ctx.adb.shell("dumpsys activity | grep -A4 mAllowAppSwitchUids").splitlines():
            if "VoiceInteraction" in l:
                return l.strip()
        return ""

    def _a11y_bound(self, ctx) -> bool:
        return "services:{Service[" in ctx.adb.shell("dumpsys accessibility").replace(" ", "")

    def _helper_pkg(self, ctx) -> str:
        # prefer what we recorded (in case the machine's random id changed since)
        return ctx.state.opts(self.meta.name).get("helper_pkg") or helper_package()

    # -- interface -----------------------------------------------------

    def status(self, ctx) -> Status:
        c = _components(self._helper_pkg(ctx))
        if not ctx.adb.pkg_installed(c["app"]):
            return Status(False, "helper not installed")
        role = c["app"] in ctx.adb.get_secure("voice_interaction_service")
        bound = self._a11y_bound(ctx)
        exempt = bool(self._exempt_line(ctx))
        bits = [
            "assistant role SET" if role else "assistant role MISSING",
            "a11y bound" if bound else "a11y NOT bound",
            "app-switch exemption GRANTED" if exempt else "exemption MISSING",
        ]
        tgt = ctx.adb.shell(f"cat {TARGET_FILE} 2>/dev/null").replace("\n", "/")
        return Status(role and bound, f"target={tgt or '?'}; " + ", ".join(bits))

    def apply(self, ctx) -> None:
        pkg, act = self._target(ctx)
        hp = helper_package()
        c = _components(hp)
        ctx.log(f"target launcher: {pkg}/{act}")
        ctx.log(f"helper package:  {hp}")
        if not ctx.adb.pkg_installed(pkg):
            ctx.log(f"! {pkg} is not installed on the tablet -- install it first "
                    f"(Play Store / APKMirror). Continuing so the helper is ready.")

        ctx.log("building helper APK...")
        apk = ctx.build_helper(HELPER)
        ctx.log(f"installing {apk.name}")
        ctx.log("  " + ctx.adb.install(str(apk), "-r"))

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
            tf.write(f"{pkg}\n{act}\n")
            tmp = tf.name
        ctx.adb.push(tmp, TARGET_FILE)
        Path(tmp).unlink(missing_ok=True)

        # toggle so AccessibilityManager re-reads, then set
        ctx.adb.put_secure("enabled_accessibility_services", "com.invalid/x")
        time.sleep(1)
        ctx.adb.put_secure("enabled_accessibility_services", c["acc"])
        ctx.adb.put_secure("accessibility_enabled", "1")
        # the assistant role -> app-switch-lock exemption
        ctx.adb.put_secure("voice_interaction_service", c["vis"])
        ctx.adb.put_secure("voice_recognition_service", c["rec"])

        ctx.adb.shell(f"am start -n {c['main']}")
        time.sleep(3)

        if ctx.opts.get("reboot"):
            ctx.log("rebooting (most reliable way to bind the service)...")
            ctx.adb.reboot_wait()

        exemption = self._exempt_line(ctx)
        bound = self._a11y_bound(ctx)
        ctx.log(f"a11y bound: {'yes' if bound else 'NO'}")
        ctx.log(f"app-switch exemption: {exemption or 'NOT GRANTED -- re-run with --reboot'}")
        ctx.state.mark_applied(self.meta.name,
                               {"launcher": ctx.opts.get("launcher", "nova"),
                                "pkg": pkg, "activity": act, "helper_pkg": hp})
        if not (bound and exemption):
            ctx.log("Not fully active yet. Re-run:  python3 -m embertools apply launcher_swap --reboot")
        else:
            ctx.log("Done. Press Home on the tablet -- your launcher comes up instantly.")

    def revert(self, ctx) -> None:
        c = _components(self._helper_pkg(ctx))
        ctx.adb.delete_secure("voice_interaction_service")
        ctx.adb.delete_secure("voice_recognition_service")
        ctx.adb.put_secure("enabled_accessibility_services", "com.invalid/x")
        ctx.adb.delete_secure("enabled_accessibility_services")
        ctx.adb.put_secure("accessibility_enabled", "0")
        time.sleep(2)                      # let VIMS drop the uid from the allowlist
        ctx.adb.shell(f"rm -f {TARGET_FILE}")
        ctx.log("  " + ctx.adb.uninstall(c["app"]))
        ctx.state.mark_reverted(self.meta.name)
        ctx.log("Stock launcher restored. A reboot is recommended.")


MOD = LauncherSwap()
