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

## Local checks before proposing changes

- `python3 -m compileall -q embertools main.py`
- `python3 main.py list` against a connected device (or confirm it degrades
  cleanly with none).
- For a new/changed mod: apply it, check `status`, **revert it**, check `status`
  again — on a real tablet if you have one, otherwise say so explicitly in the PR.

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
   support, and which were actually tested?
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
