#!/usr/bin/env python3
"""
fire_launcher_swap.py  --  use your preferred launcher on an Amazon Fire tablet

Makes Nova / Lawnchair / any home app behave as the default launcher on a locked,
un-rooted Fire OS 7 tablet (tested: Fire HD 10 2019, KFMAWI, Fire OS 7.3.3.1 /
Android 9).  ADB only -- no root, no bootloader unlock, no /system changes.

HOW IT WORKS
------------
Fire OS blocks every normal way to set a third-party launcher as default, and
after each Home press the system refuses foreground switches from background apps
for 5 seconds (AOSP's APP_SWITCH_DELAY_TIME).  This installs a tiny helper app
that:

  1. runs an AccessibilityService which, whenever the Fire launcher comes to the
     front, immediately starts your chosen launcher instead; and
  2. registers itself as the device's voice-interaction ("assistant") service.
     Android grants the current assistant's UID a permanent exemption from the
     post-Home app-switch lock (ActivityManagerService.mAllowAppSwitchUids, set
     by VoiceInteractionManagerService).  That is what makes the redirect
     instant (~150 ms) instead of taking ~4.5 s.

Nothing else on a de-registered Fire tablet uses voice interaction, so there is
no collateral.  Side effects: the long-press-Home / assist gesture does nothing,
and a Fire OS update will reset the settings -- just re-run this script.

USAGE
-----
  python3 fire_launcher_swap.py                 # install + configure, target = Nova
  python3 fire_launcher_swap.py --launcher lawnchair
  python3 fire_launcher_swap.py --launcher com.pkg/com.pkg.HomeActivity
  python3 fire_launcher_swap.py --debloat       # also disable Amazon consumer apps
  python3 fire_launcher_swap.py --status        # show current state
  python3 fire_launcher_swap.py --undo          # remove everything, restore stock
  python3 fire_launcher_swap.py --reboot        # reboot at the end (most reliable bind)

Requires: python3, adb on PATH, USB debugging enabled, one device attached
(or pass --serial <id>).
"""

import argparse
import base64
import subprocess
import sys
import tempfile
import time
import os

APP_ID   = "mzbqt2.zbokg.jg1we7u"
ACC_SVC  = f"{APP_ID}/{APP_ID}.RedirectService"
VIS_SVC  = f"{APP_ID}/{APP_ID}.AssistShimService"
REC_SVC  = f"{APP_ID}/{APP_ID}.AssistRecognitionService"
MAIN_ACT = f"{APP_ID}/{APP_ID}.MainActivity"
TARGET_FILE = "/data/local/tmp/embertools_target"

LAUNCHERS = {
    "nova":       ("com.teslacoilsw.launcher", "com.teslacoilsw.launcher.NovaLauncher"),
    "lawnchair":  ("ch.deletescape.lawnchair", "ch.deletescape.lawnchair.Launcher"),
    "lawnchair2": ("app.lawnchair",            "app.lawnchair.LawnchairLauncher"),
    "lawnchair12":("app.lawnchair",            "app.lawnchair.LawnchairLauncher"),
    "kvaesitso":  ("de.mm20.launcher2.release","de.mm20.launcher2.ui.launcher.LauncherActivity"),
    "niagara":    ("bitpit.launcher",          "bitpit.launcher.MainActivity"),
    "smartlauncher":("ginlemon.flowerfree",    "ginlemon.flower.HomeScreen"),
}

# Amazon consumer apps to disable with --debloat. `pm disable-user` sticks across
# reboot on Fire OS 7; `pm uninstall --user 0` gets reverted on boot.
DEBLOAT = [
    "com.amazon.avod", "com.amazon.dee.app", "com.amazon.photos", "com.amazon.kindle",
    "com.audible.application.kindle", "com.amazon.tahoe", "com.amazon.cloud9",
    "com.amazon.mp3", "com.amazon.windowshop", "com.amazon.imdb.tv.mobile.app",
    "com.amazon.weather", "com.amazon.sneakpeek", "com.amazon.kor.demo",
    "com.amazon.bioscope", "com.amazon.redstone", "com.amazon.recess", "com.amazon.hedwig",
    "com.amazon.kindle.unifiedSearch", "com.amazon.kindle.starsight",
    "com.amazon.comms.kids", "com.amazon.cloud9.kids", "com.amazon.firespotlight",
]

ADB = "adb"
SERIAL = None


def adb(*args, check=False, timeout=60):
    cmd = [ADB]
    if SERIAL:
        cmd += ["-s", SERIAL]
    cmd += list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        sys.exit(f"! adb {' '.join(args)}\n{r.stdout}{r.stderr}")
    return (r.stdout + r.stderr).strip()


def sh(cmd, check=False, timeout=60):
    """Run a shell command on the device."""
    return adb("shell", cmd, check=check, timeout=timeout)


def need_device():
    global SERIAL
    out = adb("devices")
    rows = [l.split() for l in out.splitlines()[1:] if l.strip()]
    if any(r[1:2] == ["unauthorized"] for r in rows):
        sys.exit("! Device is 'unauthorized' -- tap 'Allow USB debugging' on the tablet.")
    devs = [r[0] for r in rows if r[1:2] == ["device"]]
    if not devs:
        sys.exit("! No device. Check the cable, enable USB debugging, run `adb devices`.")
    if len(devs) > 1 and not SERIAL:
        sys.exit(f"! Multiple devices {devs}; pass --serial <id>.")
    if not SERIAL:
        SERIAL = devs[0]
    model = sh("getprop ro.product.model")
    fireos = sh("getprop ro.build.version.name")
    print(f"  device: {model}  {fireos}  ({SERIAL})")


def app_uid():
    out = sh(f"dumpsys package {APP_ID} | grep -m1 userId=")
    for tok in out.replace("=", " ").split():
        if tok.isdigit():
            return tok
    return None


def resolve_target(spec):
    spec = (spec or "nova").strip()
    if spec.lower() in LAUNCHERS:
        return LAUNCHERS[spec.lower()]
    if "/" in spec:
        pkg, act = spec.split("/", 1)
        if not act.startswith(pkg) and act.startswith("."):
            act = pkg + act
        return (pkg, act)
    return (spec, spec + ".Launcher")   # bare package guess


def is_installed(pkg):
    return pkg in sh(f"pm list packages {pkg}")


# ------------------------------------------------------------------ actions ----

def do_install(target_spec, want_reboot):
    pkg, act = resolve_target(target_spec)
    print(f"\n== target launcher: {pkg}/{act}")
    if not is_installed(pkg):
        print(f"  ! {pkg} is NOT installed. Install it first (Play Store / APKMirror),")
        print(f"    then re-run. Continuing anyway so the helper is ready.")

    apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
    apk.write(base64.b64decode(_APK_B64))
    apk.close()
    try:
        print("\n== installing helper app")
        print("  " + adb("install", "-r", apk.name))
    finally:
        os.unlink(apk.name)

    # overlay perm (harmless; only used by older builds of the helper)
    sh(f"appops set {APP_ID} SYSTEM_ALERT_WINDOW allow")

    print("\n== writing target + secure settings")
    tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    tf.write(f"{pkg}\n{act}\n")
    tf.close()
    adb("push", tf.name, TARGET_FILE)
    os.unlink(tf.name)
    # toggle so AccessibilityManager re-reads the list, then set it
    sh("settings put secure enabled_accessibility_services com.invalid/x")
    time.sleep(1)
    sh(f"settings put secure enabled_accessibility_services {ACC_SVC}")
    sh("settings put secure accessibility_enabled 1")
    # the assistant role -> app-switch-lock exemption
    sh(f"settings put secure voice_interaction_service {VIS_SVC}")
    sh(f"settings put secure voice_recognition_service {REC_SVC}")

    sh(f"am start -n {MAIN_ACT}")
    time.sleep(3)

    if want_reboot:
        print("\n== rebooting (most reliable way to bind the service)")
        adb("reboot")
        adb("wait-for-device", timeout=180)
        time.sleep(35)
        sh("input keyevent KEYCODE_WAKEUP")
        time.sleep(3)

    do_status()
    print("\nDone. Press Home on the tablet -- your launcher should come up instantly.")
    print("If it still shows the Fire launcher, run once with --reboot.")


def do_status():
    print("\n== status")
    tgt = sh(f"cat {TARGET_FILE} 2>/dev/null").replace("\n", " / ") or "(not set)"
    print(f"  target launcher       : {tgt}")

    installed = is_installed(APP_ID)
    print(f"  helper app installed  : {'yes' if installed else 'NO'}")

    vis = sh("settings get secure voice_interaction_service")
    vis_ok = APP_ID in vis
    print(f"  assistant role        : {vis}  {'OK' if vis_ok else '<-- expected ' + VIS_SVC}")

    acc = sh("settings get secure enabled_accessibility_services")
    print(f"  accessibility setting : {acc}")

    # Fire OS's dumpsys accessibility is terse: a non-empty services:{...} block
    # with our label means our (and only our) service is bound and running.
    acc_dump = sh("dumpsys accessibility")
    a11y_bound = "services:{Service[" in acc_dump.replace(" ", "")
    print(f"  a11y service bound    : {'yes' if a11y_bound else 'NO  (run with --reboot)'}")

    allow_line = ""
    for l in sh("dumpsys activity | grep -A4 mAllowAppSwitchUids").splitlines():
        if "VoiceInteraction" in l:
            allow_line = l.strip()
    if allow_line:
        print(f"  app-switch exemption  : GRANTED  ({allow_line})")
    else:
        print(f"  app-switch exemption  : NOT granted  (redirect will be slow; run --reboot)")

    foc = sh("dumpsys window windows | grep -m1 mFocusedApp")
    foc = foc.split("u0 ")[-1].rstrip("}") if "u0 " in foc else foc
    print(f"  focused window        : {foc}")


def do_debloat():
    print("\n== disabling Amazon consumer apps (pm disable-user, sticks across reboot)")
    for p in DEBLOAT:
        r = sh(f"pm disable-user --user 0 {p}")
        tag = "ok" if "new state: disabled" in r else ("protected" if "protected" in r
              else ("absent" if "Unable to find" in r or not r else r.split("\n")[0][:50]))
        print(f"  {p:<34} {tag}")
    print("\n  Still visible in Nova (protected -- hide via Nova > App drawer > Hide apps):")
    for l in sh("cmd package query-activities --brief -a android.intent.action.MAIN "
                "-c android.intent.category.LAUNCHER").splitlines():
        if any(k in l.lower() for k in ("amazon", "kindle", "audible")):
            print("    " + l.strip())


def do_undo():
    print("\n== reverting to stock")
    sh("settings delete secure voice_interaction_service")
    sh("settings delete secure voice_recognition_service")
    sh("settings put secure enabled_accessibility_services com.invalid/x")
    sh("settings delete secure enabled_accessibility_services")
    sh("settings put secure accessibility_enabled 0")
    time.sleep(2)  # let VoiceInteractionManagerService drop the uid from the allowlist
    sh(f"rm -f {TARGET_FILE}")
    print("  " + adb("uninstall", APP_ID))
    print("\n  Re-enable Amazon apps that --debloat disabled? run:")
    print("    for p in $(adb shell pm list packages -d | sed 's/package://'); do "
          "adb shell pm enable $p; done   # (re-enables ALL disabled pkgs)")
    print("  or just factory reset. Reboot recommended.")


def main():
    global ADB, SERIAL
    ap = argparse.ArgumentParser(description="Use your own launcher on a Fire tablet (no root).")
    ap.add_argument("--launcher", default="nova",
                    help="nova (default) | lawnchair | lawnchair2 | niagara | kvaesitso | "
                         "smartlauncher | <pkg>/<HomeActivity>")
    ap.add_argument("--debloat", action="store_true", help="also disable Amazon consumer apps")
    ap.add_argument("--status", action="store_true", help="show current state and exit")
    ap.add_argument("--undo", action="store_true", help="remove the helper, restore stock launcher")
    ap.add_argument("--reboot", action="store_true", help="reboot at the end (most reliable)")
    ap.add_argument("--serial", help="adb device serial (if more than one attached)")
    ap.add_argument("--adb", default="adb", help="path to adb")
    args = ap.parse_args()

    ADB = args.adb
    SERIAL = args.serial

    need_device()

    if args.status:
        do_status(); return
    if args.undo:
        do_undo(); return

    do_install(args.launcher, args.reboot)
    if args.debloat:
        do_debloat()


# The helper APK (~17 KB), base64.  Randomly-named package "mzbqt2.zbokg.jg1we7u", debug-signed.
# Built from embertools/shared/launcher_swap/helper/ via tools/make_standalone.py
_APK_B64 = """\
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
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
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
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
APgPAAAAAAAAQVBLIFNpZyBCbG9jayA0MlBLAQIAAAAAAAAIAACAnwHF/m2pGQUAALwRAAATAAAA
AAAAAAAAAAAAAAAAAABBbmRyb2lkTWFuaWZlc3QueG1sUEsBAgAAAAAAAAgAAICfAXEQ2SIxAQAA
KAIAACgAAAAAAAAAAAAAAAAASgUAAHJlcy94bWwvYWNjZXNzaWJpbGl0eV9zZXJ2aWNlX2NvbmZp
Zy54bWxQSwECAAAAAAAACAAAgJ8BNnP79SsBAAAsAgAAFwAAAAAAAAAAAAAAAADBBgAAcmVzL3ht
bC9pbnRlcmFjdGlvbi54bWxQSwECAAAAAAAACAAAgJ8BeFvcFYwAAAD0AAAAFgAAAAAAAAAAAAAA
AAAhCAAAcmVzL3htbC9yZWNvZ25pemVyLnhtbFBLAQIAAAAAAAAAAACAnwH3NepHyAMAAMgDAAAO
AAAAAAAAAAAAAAAAAOEIAAByZXNvdXJjZXMuYXJzY1BLAQIUAxQAAAAIAJmRKF1CgdEdnhAAAAAg
AAALAAAAAAAAAAAAAACkgdgMAABjbGFzc2VzLmRleFBLAQIUABQAAAgIAJmRKF3t2oT6ygEAAMkC
AAAUAAAAAAAAAAAAAAAAAJ8dAABNRVRBLUlORi9FTUJFUlRPTy5TRlBLAQIUABQAAAgIAJmRKF2/
JG2sFwQAAHEEAAAVAAAAAAAAAAAAAAAAAJsfAABNRVRBLUlORi9FTUJFUlRPTy5SU0FQSwECFAAU
AAAICACZkShdywoA8HcBAABKAgAAFAAAAAAAAAAAAAAAAADlIwAATUVUQS1JTkYvTUFOSUZFU1Qu
TUZQSwUGAAAAAAkACQBcAgAAAEAAAAAA"""

if __name__ == "__main__":
    main()
