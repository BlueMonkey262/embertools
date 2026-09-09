# AGENTS.md

Guidance for coding agents (Claude Code, Codex, Cursor, Aider, …) working in this
repo.

## What embertools is

A no-root toolkit that modifies people's Amazon Fire tablets over ADB. Every mod
issues real `adb` / `pm` / `settings` commands against a physical device. A bad
mod can disable the wrong system package and soft-brick someone's tablet. Treat
contributions accordingly.

- stdlib only. No pip dependencies in `embertools/` (the `gui` extra is the sole,
  optional exception).
- Mods live in `embertools/shared/<name>/mod.py`, each defining `MOD` (a `Mod`
  subclass). See `docs/DESIGN.md` for the contract.
- Every mod must be **idempotent** and have a working **`revert`**.
- The CLI (`main.py` / `embertools/cli.py`) is the primary interface; the GUI is
  a thin optional layer over the same mod objects.

## Mods and models — how compatibility is declared

A mod says which devices it works on; the loader only offers a mod on a device it
claims to support. Get this right — the point is that a user never sees a mod
that will misbehave on their tablet.

### `Meta` (in each `mod.py`)

```python
meta = Meta(
    name="ota_block",            # dir name; unique
    summary="…",                 # one line, shown in list/GUI
    supported=["*"],             # model codes, or ["*"] for "any Fire tablet"
    fireos=[7],                  # major Fire OS lines, or None for "any"
    needs_build=False,           # True if the mod builds/pushes a helper APK
    reversible=True,             # must be True unless genuinely impossible
    risk="low",                  # low | medium | high  (medium/high prompts)
    order=10,                    # lower = runs earlier in "apply all"
    options=[...],               # form fields; see private_dns/launcher_swap
)
```

- `supported` and `fireos` are **claims that you tested**, not hopes. A mod is
  shown to the user iff `dev.model in supported (or "*")` **and**
  `dev.fireos_major in fireos (or fireos is None)`.
- Use `["*"]` only when the mechanism is genuinely OS/model-agnostic (a plain
  `settings put`, a `pm disable-user` of an app that exists on all Fire OS). If
  it depends on a specific package, framework behavior, or SoC, list explicit
  model codes.
- Do **not** widen `supported` / `fireos` to "make it match" a device you want to
  cover. Add a code only after `apply → status → revert` worked on that exact
  model, or ship the PR as `[needs testing]` and say which entries are unproven.

### `embertools/models/registry.py`

One dict entry per real device, keyed by its exact `ro.product.model`
(`adb shell getprop ro.product.model`). Shape:

```python
"KFMAWI": {"name": "Fire HD 10 (2019, 9th Gen)", "soc": "MediaTek MT8183",
           "fireos": 7, "quirks": ["tested"]},
```

- `name`: the marketing name + generation, exactly as on Amazon's
  [device list](https://developer.amazon.com/docs/device-specs/ft-identify-tablet-devices.html).
  Don't invent model codes or names — look them up.
- `fireos`: the major line the device tops out on (5/6/7/8).
- `quirks`: free-form flags a mod may check via `dev.quirks`
  (`"tested"`, `"untested"`, `"low-ram"`, `"fireos8"`, …). A new device you
  haven't run on is `"untested"`.

### Shared mod vs. device-specific mod

- **Default:** put the mod in `embertools/shared/<name>/` and list the models it
  supports. One implementation, many devices.
- **Only if a device genuinely needs different logic:** add
  `embertools/models/<CODE>/<name>/mod.py` defining a `MOD` with the same
  `meta.name`. It shadows the shared mod on that model only. Use this for real
  divergence (e.g. Fire OS 8 needs a different launcher method), not for
  per-model tweaks that belong behind a `quirks` check.

### Adding support for a new device — the honest path

1. Add it to `registry.py` with `quirks: ["untested"]`.
2. For each shared mod you think applies: read the mod, decide if the mechanism
   really holds on that OS/SoC. If yes and you tested it, add the code to
   `supported` and flip its quirk to `"tested"`. If you didn't test it, leave it
   out or ship `[needs testing]`.
3. Never bulk-add a model to every mod's `supported` list hoping something works.

## Local checks before proposing changes

- `python3 -m compileall -q embertools main.py`
- `python3 main.py list` against a connected device (or confirm it degrades
  cleanly with none).
- For a new/changed mod: apply it, check `status`, **revert it**, check `status`
  again, on a real tablet.

## Testing is required

A mod PR must be tested on real hardware (apply → status → revert → status). If
you cannot test on a device:

- the PR **title must start with `[needs testing]`**,
- the body must list exactly what is unverified and on which models, and
- do not present it to the user as ready to merge.

Never claim a mod was tested when it wasn't.

## Opening a pull request — required user quiz

**Before you open or push a PR, you MUST walk the user through what it contains
and get their explicit approval.** The user is publishing this under their name;
they need to actually understand it. Do not open the PR until every point below
has been put to the user *in your own words about this specific change* and they
have confirmed.

Ask, and wait for answers:

1. **Plain-English summary** — "This PR adds/changes X. In one sentence, it does
   Y. Is that what you want to submit?"
2. **Device commands** — list every `adb` / `pm` / `settings` / shell command the
   change will run on a tablet, and what each one does. Confirm the user is okay
   with each.
3. **What it changes on the device** — packages disabled/installed, settings
   written, files pushed, whether it triggers a reboot.
4. **Reversibility** — how `revert` undoes it, and anything it *can't* undo.
5. **Blast radius** — worst realistic outcome if it misbehaves on an untested
   device/Fire OS version. Which models/Fire OS versions is it claimed to
   support, and which were **actually tested** (apply/status/revert on hardware)?
   If none were, the PR title starts with `[needs testing]` — tell the user.
6. **New network calls or downloads** — any URL the change fetches from, and why
   that source is trustworthy.
7. **New dependencies** — there should be none; if the change adds one, stop and
   get explicit sign-off.
8. **Attribution** — confirm the user wants their name/GitHub account on this
   commit and PR.

Then show the user the final diff and the exact PR title + body, and ask one
last time: **"Ready for me to open this PR as you?"** Only proceed on an
unambiguous yes.

If the user is not present to answer, do not open the PR — leave the branch and
report what's pending.

## Style

Match the surrounding code: terse, lowercase log lines, `ctx.log(...)` inside
mods, no comments restating the obvious. Keep mods small.
