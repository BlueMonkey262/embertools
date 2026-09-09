# embertools — design

## Goals

- **No root, no unlock, no `/system` edits.** Only documented ADB + Android APIs.
- **Modular.** Each capability ("mod") is independent, idempotent, reversible.
- **Model-aware.** Mods declare which Fire tablets they support; the tool only
  offers what fits the connected device.
- **Zero Python dependencies.** stdlib only. A JDK + `adb` are the real
  requirements (JDK only for mods that build a helper APK).
- **CLI/TUI first.** A GUI can wrap the same mods later (see `docs/mockups/`).
  Fire-Tools' GUI-first design is why it rotted.

## Layout

```
embertools/
  cli.py                 entry: connect → discover mods → menu/dispatch
  core/
    adb.py               serial-bound adb wrapper
    device.py            ro.product.model + Fire OS → Device, via models/registry.py
    mod.py               Mod / Meta / Status / Context + discover()
    build.py             Gradle-free APK build + SDK bootstrap + persistent key
    state.py             ~/.embertools/state/<serial>.json — what each mod changed
    ui.py                orange/grey terminal helpers, stdlib only
  models/
    registry.py          MODELS: {code: {name, soc, fireos, quirks}}
    <CODE>/<mod>/mod.py   device-specific mods; override shared ones of same name
  shared/<mod>/
    mod.py               defines module-level MOD = <Mod subclass>()
    helper/              (if needs_build) APK source: manifest, src/, res/, no .apk
```

## The Mod contract

```python
class MyMod(Mod):
    meta = Meta(name=..., summary=..., supported=[...codes or "*"],
                fireos=[7], needs_build=False, reversible=True,
                risk="low", order=100)
    def status(self, ctx) -> Status        # Status(applied: bool|None, detail: str)
    def apply(self, ctx) -> None
    def verify(self, ctx) -> Status  # optional post-apply hardware self-check
    def revert(self, ctx) -> None
MOD = MyMod()
```

`ctx` gives `adb`, `dev`, `state`, `opts` (CLI flags), `log()`, `build_helper(dir)`.
`discover(dev)` loads every `shared/*/mod.py` + `models/<code>/*/mod.py`, keeps the
ones whose `supports(dev)` passes, sorts by `order`. Model-specific mods loaded
last, so they shadow a shared mod with the same `name`.

Mods may implement `verify(ctx)` for a post-apply hardware self-check;
`launcher_swap` uses it to press Home and confirm the target launcher appears.

## Compatibility model

The user's chosen model: a shared mod carries the list of models it works on
(`supported=["KFMAWI", "KFTRWI", ...]`, or `["*"]`). Adding a device = adding it
to `models/registry.py` and appending its code to the `supported` lists of the
mods it can use. No code duplication; a fix to `launcher_swap` fixes every device.

## APK build (`core/build.py`)

We ship **no APKs**. `needs_build` mods carry helper source; `build.py`:

1. Finds a JDK (17+ recommended) and an Android SDK (`ANDROID_HOME`,
   `~/Android/Sdk`, …) or bootstraps build-tools + one platform jar into
   `~/.embertools/sdk` via `sdkmanager` (~200 MB, once).
2. Pipeline, no Gradle: `aapt2 compile/link` → `javac -source 8 -target 8
   -bootclasspath android.jar` → `d8 --lib android.jar` → `zipalign` →
   `apksigner` with a **persistent** debug key at `~/.embertools/debug.keystore`
   (so rebuilds stay `adb install -r`-compatible).
3. Caches the result by a hash of the helper source tree.

## launcher_swap — the headline mod

Locked Fire OS 7 blocks every normal launcher-default path, and AOSP's
`APP_SWITCH_DELAY_TIME` makes any background app wait ~5 s to take the foreground
after Home — which is why every LauncherHijack-style tool feels broken.

`launcher_swap`:
1. Installs an `AccessibilityService` that starts the chosen launcher whenever a
   stock launcher (`com.amazon.firelauncher`, …) comes forward.
2. Sets that helper as `Settings.Secure.voice_interaction_service`.
   `VoiceInteractionManagerService.switchImplementationIfNeededLocked()` then
   calls `ActivityManagerService.setAllowAppSwitches(uid)` — adding the helper's
   uid to `mAllowAppSwitchUids`, which `checkAppSwitchAllowedLocked()` treats as
   exempt from the post-Home lock. Redirect: ~4.5 s → ~150 ms.

The helper also ships the `VoiceInteractionSessionService` + `RecognitionService`
stubs the metadata parser requires (`supportsAssist=false` so the assist gesture
just no-ops). `revert` clears the settings, waits for VIMS to drop the uid, and
uninstalls the helper.

**Known limits:** assist/long-press-Home does nothing while active; a Fire OS
update wipes the secure settings (re-run the mod); Fire OS 8 needs a variant
(BAL rules + the "restricted setting" accessibility gate).

## Safety

- `ota_block` has `order=10` (runs first) and `risk="medium"` (prompts).
- Every mod is reversible; `revert` with no args reverts everything in the state
  file.
- Worst case for a bad `pm disable-user` is a factory reset — documented in the
  README.
