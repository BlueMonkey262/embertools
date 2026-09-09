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

import json
import re
import tempfile
import time
import urllib.error
import urllib.request
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
    "nova":        ["com.teslacoilsw.launcher"],
    "lawnchair":   ["app.lawnchair", "app.lawnchair.play", "app.lawnchair.nightly", "ch.deletescape.lawnchair"],
    "kvaesitso":   ["de.mm20.launcher2.release", "de.mm20.launcher2"],
    "niagara":     ["bitpit.launcher"],
    "olauncher":   ["app.olauncher"],
    "smartlauncher": ["ginlemon.flowerfree", "ginlemon.flowerpro"],
}

# When the chosen launcher isn't installed, embertools can fetch the open-source
# ones from F-Droid (HTTPS, F-Droid-signed).  Proprietary launchers have no clean
# download API -- for those we point the user at a store + `main.py install`.
FDROID_LAUNCHER = {
    "kvaesitso": "de.mm20.launcher2.release",
    "olauncher": "app.olauncher",
}
STORE_LAUNCHER = {
    "nova": ("Nova Launcher", "https://play.google.com/store/apps/details?id=com.teslacoilsw.launcher",
             "https://www.apkmirror.com/apk/teslacoil-software/nova-launcher/"),
    "lawnchair": ("Lawnchair", "https://play.google.com/store/apps/details?id=app.lawnchair",
                  "https://github.com/LawnchairLauncher/lawnchair/releases"),
    "niagara": ("Niagara Launcher", "https://play.google.com/store/apps/details?id=bitpit.launcher",
                "https://www.apkmirror.com/apk/peter-huber/niagara-launcher-fresh-clean/"),
    "smartlauncher": ("Smart Launcher", "https://play.google.com/store/apps/details?id=ginlemon.flowerfree",
                      "https://www.apkmirror.com/apk/smart-launcher-team/"),
}


def _fdroid_apk_url(pkg: str) -> str:
    with urllib.request.urlopen(
            f"https://f-droid.org/api/v1/packages/{pkg}", timeout=30) as r:
        data = json.load(r)
    vc = data.get("suggestedVersionCode") or data["packages"][0]["versionCode"]
    return f"https://f-droid.org/repo/{pkg}_{vc}.apk"


def _fetch_launcher(ctx, name: str) -> str | None:
    """Download and install the launcher `name` if we have a source. Returns the
    installed package, or None if there's no automatic source."""
    fdroid_pkg = FDROID_LAUNCHER.get(name)
    if fdroid_pkg:
        try:
            url = _fdroid_apk_url(fdroid_pkg)
            ctx.log("source: F-Droid (f-droid.org), APK signed by the F-Droid build server")
            ctx.log(f"fetching {url}")
            with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tf:
                with urllib.request.urlopen(url, timeout=180) as r:
                    tf.write(r.read())
                apk = tf.name
            try:
                ctx.log("  " + ctx.adb.install(apk, "-r"))
            finally:
                Path(apk).unlink(missing_ok=True)
        except (urllib.error.URLError, OSError) as e:
            ctx.log(f"could not fetch {name} from F-Droid: {e}")
            return None
        return fdroid_pkg if ctx.adb.pkg_installed(fdroid_pkg) else None

    store = STORE_LAUNCHER.get(name)
    if store:
        label, play, apkmirror = store
        raise RuntimeError(
            f"{label} isn't installed and has no automatic download source "
            f"(proprietary). Install it from {play} , or download the APK from "
            f"{apkmirror} and run:  python3 main.py install <that.apk>  then re-run.")
    return None


def _activity_from_output(pkg: str, output: str) -> str:
    for line in reversed((output or "").splitlines()):
        line = line.strip()
        if re.fullmatch(r"\.[A-Za-z0-9_.$]+", line):
            return pkg + line
        match = re.search(
            rf"(?<![A-Za-z0-9_.]){re.escape(pkg)}/([A-Za-z0-9_.$]+)",
            line,
        )
        if match:
            activity = match.group(1)
            return pkg + activity if activity.startswith(".") else activity
    return ""


def resolve_target(ctx, spec: str, fetch: bool = False) -> tuple[str, str]:
    spec = (spec or "nova").strip()
    if "/" in spec:
        pkg, act = spec.split("/", 1)
        if act.startswith("."):
            act = pkg + act
        return pkg, act

    name = spec.lower()
    candidates = LAUNCHERS.get(name, [spec])
    pkg = next((c for c in candidates if ctx.adb.pkg_installed(c)), None)
    if not pkg and fetch:
        pkg = _fetch_launcher(ctx, name)      # download+install, or raise with guidance
    if not pkg:
        raise RuntimeError(
            f"none of the {spec} packages are installed: {', '.join(candidates)}. "
            "Install one (or use a launcher embertools can fetch: "
            f"{', '.join(sorted(FDROID_LAUNCHER))}), then re-run.")

    commands = [
        f"cmd package resolve-activity --brief -c android.intent.category.HOME {pkg}",
        f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {pkg}",
        f"cmd package resolve-activity --brief {pkg}",
    ]
    for command in commands:
        activity = _activity_from_output(pkg, ctx.adb.shell(command))
        if activity:
            return pkg, activity
    raise RuntimeError(f"could not resolve an activity for {pkg} on the tablet. Install one, then re-run.")


class LauncherSwap(Mod):
    meta = Meta(
        name="launcher_swap",
        summary="Use Nova / Lawnchair / any launcher as default (instant redirect, no root)",
        supported=["KFMAWI", "KFTRWI", "KFTRPWI", "KFONWI", "KFMUWI", "KFKAWI"],
        fireos=[7],
        needs_build=True,
        reversible=True,
        risk="low",
        confirm="Installs a helper app and, if 'reboot after' is on, restarts the tablet. Continue?",
        order=50,
        options=[
            {"name": "launcher", "label": "Target launcher", "type": "choice",
             "choices": list(LAUNCHERS), "default": "nova"},
            {"name": "reboot", "label": "Reboot after (most reliable)", "type": "bool",
             "default": True},
        ],
    )

    # -- helpers --------------------------------------------------------

    def _target(self, ctx, fetch: bool = False) -> tuple[str, str]:
        return resolve_target(ctx, ctx.opts.get("launcher", "nova"), fetch=fetch)

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

    @staticmethod
    def _component_package(output: str) -> str:
        for line in (output or "").splitlines():
            match = re.search(r"\b(?:u\d+\s+)?([A-Za-z0-9_][A-Za-z0-9_.]*)/[A-Za-z0-9_.$]+", line)
            if match:
                return match.group(1)
        return ""

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
        pkg, act = self._target(ctx, fetch=True)
        ctx.log(f"target launcher: {pkg}/{act}")
        hp = helper_package()
        c = _components(hp)
        ctx.log(f"helper package:  {hp}")

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
        ctx.log("Press Home to check that the target launcher opens instantly.")
        if not (bound and exemption):
            ctx.log("Not fully active yet. Re-run:  python3 -m embertools apply launcher_swap --reboot")

    def verify(self, ctx) -> Status:
        pkg, _act = self._target(ctx)
        results = []
        last_package = ""
        last_error = ""
        for attempt in range(3):
            try:
                ctx.adb.shell("input keyevent KEYCODE_HOME")
                time.sleep(1.5)
                output = ctx.adb.shell(
                    "dumpsys activity activities | grep -m1 mResumedActivity"
                )
                last_package = self._component_package(output)
                passed = last_package == pkg
                results.append(passed)
                if passed:
                    return Status(True, f"Home opens {pkg}")
            except Exception as exc:
                last_error = str(exc)
                results.append(False)

        if sum(results) >= 2:
            return Status(True, f"Home opens {pkg}")
        opened = last_package or last_error or "no launcher activity found"
        return Status(False, f"Home opened {opened} instead of {pkg}")

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
