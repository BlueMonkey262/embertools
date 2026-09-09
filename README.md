# embertools

A modular, **no-root** toolkit for reclaiming Amazon Fire tablets: replace the
launcher, strip Amazon apps, block ads, stop forced updates. ADB only; no
bootloader unlock, no `/system` changes.

> Status: early. Fully tested on the **Fire HD 10 2019 (KFMAWI)** / Fire OS 7.3.3.1.
> Other Fire OS 7 devices are wired up but need testers. Fire OS 8 is work in progress.

## Why

Fire Toolbox is Windows-only and closed; Fire-Tools is effectively unmaintained
and its launcher method no longer works on current Fire OS 7. embertools' headline
trick: it makes a third-party launcher the **instant** default on locked Fire OS
by registering a tiny helper as the device's *assistant*, which grants it the
same "launch over anything" exemption assistants get. That sidesteps the 5-second
post-Home app-switch lock that makes every LauncherHijack-style tool feel broken.

## Install

```bash
git clone https://github.com/OWNER/embertools && cd embertools
pipx install .        # or: pip install --user .
```

Requirements on your computer:
- `adb` (Android platform-tools) on PATH
- a JDK 17+ (only for mods that build a helper APK, e.g. `launcher_swap`).
  The Android build-tools are downloaded automatically into `~/.embertools/`.

On the tablet: Settings, Device Options, Developer Options, **USB debugging** on.

## Use

CLI (primary):

```bash
python3 main.py list                  # what's available for your tablet
python3 main.py apply                 # interactive picker
python3 main.py apply launcher_swap --launcher nova --reboot
python3 main.py apply ota_block debloat private_dns keyboard --yes
python3 main.py status
python3 main.py revert                # interactive: pick what to undo
python3 main.py revert all
python3 main.py install path/to/app.apk path/to/splits.apkm
```

(If installed with `pipx`/`pip`, the `embertools` command is equivalent to
`python3 main.py`.)

GUI (work in progress):

```bash
python3 main.py --ui                  # opens the GUI in a window
```

Install the launcher you want first (Nova, Lawnchair, ...) from the Play Store or
APKMirror, then run `launcher_swap`.

## Mods

| mod | what it does | risk |
|---|---|---|
| `ota_block` | block automatic Fire OS updates (**run first**) | medium |
| `debloat` | disable Prime Video, Alexa, Silk, Kindle, lock-screen ads, ... | low |
| `private_dns` | system-wide ad/tracker blocking via Private DNS | low |
| `launcher_swap` | third-party launcher as instant default (builds a helper APK) | low |
| `keyboard` | install a real keyboard (HeliBoard, FlorisBoard, ..., or Gboard), set it default, fix the stray iWnn CJK setup | low |

Every mod is idempotent and has `revert`. State is tracked per device in
`~/.embertools/state/<serial>.json` and mirrored to the tablet.

Mods may implement `verify(ctx)` for a post-apply hardware self-check;
`launcher_swap` uses it to press Home and confirm the target launcher appears.

`install` is also available from the CLI and GUI for regular APKs, split-APK
archives (`.apkm` / `.xapk` / `.apks`), and directory batches.

## How `launcher_swap` works

1. A small `AccessibilityService` starts your launcher whenever the Fire launcher
   comes forward.
2. The helper is also set as `voice_interaction_service`. Android's
   `VoiceInteractionManagerService` then adds its uid to
   `ActivityManagerService.mAllowAppSwitchUids`, exempting it from
   `APP_SWITCH_DELAY_TIME` (the 5s lock after Home). Redirect drops from ~4.5s to
   ~150ms; the Fire launcher never renders.

Side effects: the long-press-Home / assist gesture does nothing while active; a
Fire OS update resets the settings (re-run the mod). `revert` clears everything
and uninstalls the helper.

Helper source: [`shared/launcher_swap/helper/`](embertools/shared/launcher_swap/helper).
No APK is shipped; it's built on your machine (Gradle-free: aapt2 + javac + d8 +
apksigner, with a persistent debug key so rebuilds stay `install -r`-compatible).
The helper's package name is **randomised per machine** (`~/.embertools/helper_id`)
so a manufacturer launcher blacklist has no fixed name to match. The app also
has no drawer icon and a generic label.

## Contributing

**Anyone can submit a new mod via a pull request.** A mod is a directory under
`embertools/shared/<name>/` with a `mod.py` defining a `MOD` (see any existing
mod and [`docs/DESIGN.md`](docs/DESIGN.md)). Keep it idempotent, reversible, and
stdlib-only; declare which models it supports.

**Test it on a real tablet** (`apply`, check `status`, `revert`, check `status`
again), and say so in the PR with your model and Fire OS version. If you couldn't
test it on hardware, that's fine, but the PR title must start with
`[needs testing]` and say what's unverified, so it isn't merged blind.

**Adding a device:** add it to
[`embertools/models/registry.py`](embertools/models/registry.py) (keyed by the
real `ro.product.model`), then add its code to the `supported` list of the mods
you've **verified** on it. Device-specific mods go in
`embertools/models/<CODE>/<mod>/mod.py` and override the shared one of the same
name. [`AGENTS.md`](AGENTS.md) has the exact `Meta` / registry format and the
rule against widening `supported` to "make it match": don't.

If you use a coding agent to prepare a PR, see [`AGENTS.md`](AGENTS.md). The
agent must walk you through exactly what it's submitting before opening it.

### Help wanted: device coverage

**Own a Fire tablet that isn't fully supported? Please test the mods on it and
send a PR.** Most of the work is running four commands and reporting what
happened. You don't need to write code:

```bash
python3 main.py list                       # does it detect your model?
python3 main.py apply debloat --yes        # then: status, revert, status
python3 main.py apply private_dns --yes    # same
python3 main.py apply keyboard --keyboard heliboard   # same
python3 main.py apply launcher_swap --launcher <yours> --reboot   # Fire OS 7 only
```

Then add your device to
[`embertools/models/registry.py`](embertools/models/registry.py) and each mod's
`supported` list, and open a PR noting your model, Fire OS version, and what
worked. Used Fire tablets are $10-15 on Marketplace or free in Buy Nothing groups
if you want to cover a version you don't own.

**Scope:** Fire OS **5 through 8**, i.e. every Android-based Fire *tablet*
(roughly 2015-2024 hardware). Fire OS 8 (Android 11) is the newest for tablets
and has been the ceiling since 2021, so it's in scope, not a moving target. The
methods are most stable on Fire OS 5-7, where Amazon has stopped patching. Once
you have a device on an old Fire OS, run `ota_block` and don't let it update, so
it stays a reference for that version.

Not in scope: Fire OS 14/16 (those are Fire **TV**, renumbered to match the
Android version), Vega OS (Amazon's Linux OS for cheap devices), and the
rumored AOSP-Android high-end tablet (plain Android sets a launcher the normal
way, so it won't need `launcher_swap`).

## Disclaimer

You own your tablet; this only uses documented ADB and Android APIs. But you can
still soft-brick a Fire tablet by disabling the wrong system package; `revert`
and, worst case, a factory reset are your safety nets. No warranty.
