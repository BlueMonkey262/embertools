# embertools GUI

The GUI is an optional thin web layer over the same mod system used by the CLI. The CLI remains the primary interface.

## Run it

From the project directory:

```sh
python3 main.py --ui
```

This starts a stdlib-only server on `127.0.0.1` (a free port near 8765) and opens
the GUI in a **window**, picking the best available option:

1. **pywebview** — a native OS webview window. `pip install embertools[gui]`
   (or just `pip install pywebview`) enables it.
2. **Chrome / Edge / Brave / Chromium `--app` mode** — a chromeless app-style
   window. No install needed if you have any of those.
3. **plain browser tab** — the fallback; the terminal then waits for Enter.

The frameless traffic-light titlebar requires `pip install embertools[gui]` (pywebview); Chromium/browser mode uses the OS titlebar and hides the in-app one.

Closing the window stops the server. It binds locally, uses no authentication,
and adds no *required* pip dependencies. ADB connection and device inspection are
lazy — they happen when `/api/state` or a run needs them.

## Endpoints

- `GET /` serves the self-contained dark GUI.
- `GET /api/state` returns the connected device and the compatible mods, including status, risk, reversibility, build requirements, and form option metadata. Missing, multiple, or unauthorized devices return HTTP 200 with `connected: false` and a message.
- `POST /api/run` accepts `{ "action": "apply"|"revert", "mod": "...", "opts": {} }` and returns a background `job_id`.
- `POST /api/install` accepts the raw file body with `Content-Type: application/octet-stream` and an `X-Filename` header. The filename must end in `.apk`, `.apkm`, `.xapk`, or `.apks`; it returns a background `job_id`.
- `GET /api/stream/<job_id>` is an SSE stream of job log lines (including `Context.log` lines for mod runs), followed by an `event: done` record containing `{ "ok": true }` or `{ "ok": false, "error": "..." }`.

The Install APK sidebar entry opens a dashed drop zone. Drop one or more APK files
there, or click the zone to choose them; files are uploaded and installed one at a
time, with each job's progress shown in the console panel.

The GUI calls `embertools.core` directly; it does not invoke or replace the CLI.
