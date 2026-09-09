# embertools GUI mockups

Two static HTML concepts for an optional desktop GUI front-end to `embertools`
(today a no-root Python CLI for customizing Amazon Fire tablets over ADB).
Open either file directly in a browser — self-contained, inline CSS, no external
requests, tiny vanilla JS only (fake sidebar selection + console auto-scroll).

Window is sized ~1100x720 and centered on a neutral backdrop to read as a
desktop app window, complete with a titlebar strip and an `**ember**tools`
wordmark (lowercase, "ember" in orange).

## Shared skeleton

- **Left sidebar (~240px, scrollable)** — device header with a green connection
  dot ("Fire HD 10 (2019) · Fire OS 7.3.3.1 · KFMAWI"), then the mod list. Each
  row has a status dot (green = applied, hollow gray = available, amber ring =
  needs attention), the mod name, and a one-line gray description. The selected
  row gets an orange left-border and an orange-tinted background. Real mod list:
  `ota_block`, `debloat`, `private_dns`, `launcher_swap`, `play_store`,
  `disable_telemetry`.
- **Main content area** — shows the selected mod: breadcrumb, title, a risk/state
  chip, description paragraph, then either a settings form or a run + logs view,
  with a persistent bottom action bar carrying the primary action.

## mockup-1.html — dark theme, settings view

Selected mod: **launcher_swap**. Dark-gray chrome (`#1e1f22`) with lighter
`#26282c` panels. Main area is a settings form: a "Target launcher" dropdown
(Nova / Lawnchair / Kvaesitso / Custom…), a checked "Reboot after (most
reliable)" checkbox with helper text, a divider, and a "low risk" green chip
with a reversibility note. The bottom action bar has a secondary **Revert**
button and a primary orange **Apply** button.

## mockup-2.html — light theme, run + logs view (mid-run)

Selected mod: **debloat** (already applied, "20/22", now re-running). Light
theme: off-white ground, white panels, gray borders, orange accents. Main area
shows a disabled **Apply** button next to a spinner and a "Running debloat…"
label, an orange progress bar ("14 of 22 packages"), and a dark monospace
console panel streaming output — green `✓` lines for disabled packages, amber
`!` lines for protected/skipped ones, dim setup lines, and a blinking caret. The
action bar swaps the primary action for a **Cancel** button while running.

## Design rationale

- **Orange + gray, calm not flashy.** A warm ember/amber accent
  (`#f2851e` → `#e8630a`) is reserved for the one primary action per screen,
  selection state, and progress — never decoration. Everything else is neutral
  gray so the tool reads as a developer utility.
- **One dark, one light** so the palette can be compared in both directions;
  both use a system font stack, subtle rounded corners (6–12px), and generous
  spacing with a clear title → description → controls → action hierarchy.
- **Status is legible at a glance.** The three-state dot vocabulary in the
  sidebar plus small badges ("recommended", "20/22") let a user see what's done,
  what's pending, and what needs attention without opening each mod.
- **Consistent action model.** Every mod resolves to a single primary button in
  a fixed bottom bar; settings-type mods add a secondary Revert, run-type mods
  turn the console on and swap in Cancel. The console is always dark for
  contrast, even in the light theme.
- **Accessible contrast**, `aria-current` on the selected row, a `progressbar`
  role, and real `<label>`/checkbox semantics in the form.
