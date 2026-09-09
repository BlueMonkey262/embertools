"""keyboard -- install a real keyboard and make it the default input method.

Fire tablets ship the OMRON iWnn IME, sometimes wired up with only CJK language
packs (so typing produces Chinese/Korean).  This mod installs a proper keyboard,
sets it as the default IME, and disables the stray iWnn CJK packs.

OSS keyboards are fetched from F-Droid (HTTPS, F-Droid-signed).  Gboard isn't on
F-Droid -- install it from the Play Store (or the `play_store` mod) first, then
run this with `--keyboard gboard` to select it.
"""

from __future__ import annotations

import json
import tempfile
import time
import urllib.request
from pathlib import Path

from embertools.core.mod import Mod, Meta, Status

# name -> (package id, source).  source "fdroid" downloads; "installed" just selects.
KEYBOARDS = {
    "heliboard":      ("helium314.keyboard", "fdroid"),        # maintained OpenBoard fork
    "florisboard":    ("dev.patrickgold.florisboard", "fdroid"),
    "openboard":      ("org.dslul.openboard.inputmethod.latin", "fdroid"),
    "anysoftkeyboard":("com.menny.android.anysoftkeyboard", "fdroid"),
    "unexpected":     ("juloo.keyboard2", "fdroid"),           # Unexpected Keyboard
    "thumbkey":       ("com.dessalines.thumbkey", "fdroid"),
    "simple":         ("rkr.simplekeyboard.inputmethod", "fdroid"),
    "gboard":         ("com.google.android.inputmethod.latin", "installed"),
}
DEFAULT = "heliboard"

IWNN_CJK = [
    "jp.co.omronsoft.iwnnime.languagepack.zhcn_az",
    "jp.co.omronsoft.iwnnime.languagepack.zhtw_az",
    "jp.co.omronsoft.iwnnime.languagepack.kokr_az",
]


def _fdroid_apk_url(pkg: str) -> str:
    with urllib.request.urlopen(
            f"https://f-droid.org/api/v1/packages/{pkg}", timeout=30) as r:
        data = json.load(r)
    vc = data.get("suggestedVersionCode") or data["packages"][0]["versionCode"]
    return f"https://f-droid.org/repo/{pkg}_{vc}.apk"


class Keyboard(Mod):
    meta = Meta(
        name="keyboard",
        summary="Install a real keyboard (HeliBoard/FlorisBoard/… or Gboard) and set it default",
        supported=["*"],
        fireos=[5, 6, 7, 8],
        reversible=True,
        risk="low",
        confirm="Downloads and installs the selected keyboard, then makes it your default input method. Continue?",
        order=60,
        options=[
            {"name": "keyboard", "label": "Keyboard", "type": "choice",
             "choices": list(KEYBOARDS), "default": "heliboard"},
        ],
    )

    def _choice(self, ctx) -> tuple[str, str, str]:
        name = (ctx.opts.get("keyboard") or DEFAULT).lower()
        if name not in KEYBOARDS:
            raise RuntimeError(f"unknown keyboard '{name}'. options: {', '.join(KEYBOARDS)}")
        pkg, src = KEYBOARDS[name]
        return name, pkg, src

    def _ime_component(self, ctx, pkg: str, wait: float = 8.0) -> str:
        # the IME manager can take a few seconds to register a freshly-installed keyboard
        deadline = time.time() + wait
        while True:
            for line in ctx.adb.shell("ime list -a -s").splitlines():
                if line.strip().startswith(pkg + "/"):
                    return line.strip()
            if time.time() > deadline:
                return ""
            time.sleep(1)

    def status(self, ctx) -> Status:
        cur = ctx.adb.get_secure("default_input_method")
        iwnn = "iwnn" in cur.lower() or "omron" in cur.lower()
        detail = f"default IME: {cur or '?'}"
        if iwnn:
            detail += "  (iWnn -- may type CJK)"
        return Status(bool(cur) and not iwnn, detail)

    def apply(self, ctx) -> None:
        name, pkg, src = self._choice(ctx)

        if not ctx.adb.pkg_installed(pkg):
            if src == "installed":
                raise RuntimeError(
                    f"{name} ({pkg}) isn't installed. Install it from the Play Store "
                    f"first, then re-run.")
            url = _fdroid_apk_url(pkg)
            ctx.log("source: F-Droid (f-droid.org), APK signed by the F-Droid build server")
            ctx.log(f"fetching {url}")
            with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tf:
                with urllib.request.urlopen(url, timeout=120) as r:
                    tf.write(r.read())
                apk = tf.name
            try:
                ctx.log("  " + ctx.adb.install(apk, "-r"))
            finally:
                Path(apk).unlink(missing_ok=True)

        comp = self._ime_component(ctx, pkg)
        if not comp:
            raise RuntimeError(f"{pkg} installed but exposes no IME service?")
        ctx.adb.shell(f"ime enable {comp}")
        ctx.adb.shell(f"ime set {comp}")
        ctx.log(f"default IME -> {comp}")

        disabled = 0
        for p in IWNN_CJK:
            if ctx.adb.pkg_installed(p) and "disabled" in ctx.adb.shell(
                    f"pm disable-user --user 0 {p}"):
                disabled += 1
        if disabled:
            ctx.log(f"disabled {disabled} stray iWnn CJK language pack(s)")

        ctx.state.mark_applied(self.meta.name, {"keyboard": name, "pkg": pkg})
        ctx.log("Done. Tap a text field on the tablet to check.")

    def revert(self, ctx) -> None:
        opts = ctx.state.opts(self.meta.name)
        pkg = opts.get("pkg")
        for p in IWNN_CJK:
            if ctx.adb.pkg_installed(p):
                ctx.adb.shell(f"pm enable {p}")

        # pick a fallback IME that isn't the (often broken) iWnn one
        others = [l.strip() for l in ctx.adb.shell("ime list -a -s").splitlines()
                  if l.strip() and (not pkg or not l.strip().startswith(pkg + "/"))]
        good = [c for c in others if "iwnn" not in c.lower() and "omron" not in c.lower()]

        if good:
            ctx.adb.shell(f"ime set {good[0]}")
            ctx.log(f"default IME -> {good[0]}")
            if pkg and opts.get("keyboard") != "gboard":
                ctx.log("  " + ctx.adb.uninstall(pkg))
        else:
            # the only alternative is iWnn -- keep our keyboard so the user can type
            ctx.log(f"kept {opts.get('keyboard', pkg)} installed -- the only other IME on "
                    f"this device is the iWnn one, which may not type Latin text.")
        ctx.state.mark_reverted(self.meta.name)


MOD = Keyboard()
