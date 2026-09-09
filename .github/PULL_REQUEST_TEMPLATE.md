<!--
If a mod PR is not tested on hardware, prefix the PR title with: [needs testing]
-->

## What this changes

<!-- one or two sentences -->

## Device impact

- Commands it runs on the tablet (`adb` / `pm` / `settings` / shell):
- What it changes (packages, settings, files, reboot?):
- How `revert` undoes it, and anything it can't undo:

## Testing

- [ ] `python3 -m compileall -q embertools main.py` passes
- [ ] Tested on a real tablet: `apply` → `status` → `revert` → `status`
- Model(s) + Fire OS version tested:
- What is **not** verified:

## Scope

- [ ] No new pip dependencies
- [ ] Mod is idempotent and reversible
- [ ] `supported` list reflects only models this should work on
