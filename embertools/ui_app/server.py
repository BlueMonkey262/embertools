"""Small stdlib-only HTTP/SSE server for the optional embertools GUI."""

from __future__ import annotations

import json
import mimetypes
import queue
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..core.adb import Adb
from ..core.device import Device
from ..core.mod import Context, Status, discover
from ..core.state import State

UI_DIR = Path(__file__).resolve().parent
jobs: dict[str, queue.Queue] = {}
_jobs_lock = threading.Lock()


class ConnectionProblem(RuntimeError):
    """A friendly, expected failure while looking for an ADB device."""


def _connect(adb_bin: str = "adb") -> tuple[Adb, Device]:
    if Adb.any_unauthorized(adb_bin):
        raise ConnectionProblem(
            "Device shows as 'unauthorized' — tap 'Allow USB debugging' on the tablet."
        )
    devices = Adb.list_devices(adb_bin)
    if not devices:
        raise ConnectionProblem(
            "No device. Check the cable and enable Developer options → USB debugging."
        )
    if len(devices) > 1:
        raise ConnectionProblem(
            f"Multiple devices {devices} — disconnect extras before using the GUI."
        )
    adb = Adb(serial=devices[0], adb_bin=adb_bin)
    return adb, Device.detect(adb)


def _no_device(message: str) -> dict:
    return {"device": {"connected": False, "message": message}, "mods": []}


def _state_payload() -> dict:
    try:
        adb, dev = _connect()
    except ConnectionProblem as exc:
        return _no_device(str(exc))
    except Exception as exc:
        return _no_device(f"Could not connect to ADB: {exc}")

    try:
        state = State(adb)
        mods = discover(dev)
    except Exception as exc:
        return _no_device(f"Could not inspect the device: {exc}")

    ctx = Context(adb=adb, dev=dev, state=state)
    result = {
        "device": {
            "name": dev.name,
            "model": dev.model,
            "fireos": dev.fireos_str,
            "connected": True,
        },
        "mods": [],
    }
    for mod in mods:
        try:
            status = mod.status(ctx)
        except Exception as exc:
            status = Status(None, f"status error: {exc}")
        result["mods"].append({
            "name": mod.meta.name,
            "summary": mod.meta.summary,
            "risk": mod.meta.risk,
            "reversible": mod.meta.reversible,
            "needs_build": mod.meta.needs_build,
            "options": mod.meta.options,
            "status": {"applied": status.applied, "detail": status.detail},
            "applied_via_embertools": state.is_applied(mod.meta.name),
        })
    return result


def _option_values(mod, supplied: dict) -> dict:
    values = dict(supplied or {})
    for option in mod.meta.options:
        values.setdefault(option["name"], option.get("default"))
    return values


def _run_job(job_id: str, action: str, mod_name: str, supplied_opts: dict) -> None:
    with _jobs_lock:
        out = jobs[job_id]

    def log(message: str) -> None:
        out.put({"kind": "log", "line": str(message)})

    try:
        adb, dev = _connect()
        state = State(adb)
        mods = {mod.meta.name: mod for mod in discover(dev)}
        mod = mods.get(mod_name)
        if mod is None:
            raise RuntimeError(f"No available mod named '{mod_name}'.")
        if action == "revert" and not mod.meta.reversible:
            raise RuntimeError(f"{mod_name} is not reversible.")

        ctx = Context(
            adb=adb,
            dev=dev,
            state=state,
            opts=_option_values(mod, supplied_opts),
            on_log=log,
        )
        log(f"{action}: {mod_name}")
        if action == "apply":
            mod.apply(ctx)
        else:
            mod.revert(ctx)
        out.put({"kind": "done", "ok": True})
    except ConnectionProblem as exc:
        log(f"no device: {exc}")
        out.put({"kind": "done", "ok": False, "error": str(exc)})
    except Exception as exc:
        log(f"error: {exc}")
        out.put({"kind": "done", "ok": False, "error": str(exc)})


def _json(handler: BaseHTTPRequestHandler, value: dict, status: int = 200) -> None:
    body = json.dumps(value).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "embertools/0.1"

    def log_message(self, _format, *args):
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            _json(self, _state_payload())
            return
        if path.startswith("/api/stream/"):
            self._stream(path.rsplit("/", 1)[-1])
            return
        self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            _json(self, {"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            action = payload.get("action")
            mod_name = payload.get("mod")
            opts = payload.get("opts") or {}
            if action not in ("apply", "revert") or not isinstance(mod_name, str):
                raise ValueError("action must be apply or revert and mod is required")
            if not isinstance(opts, dict):
                raise ValueError("opts must be an object")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            _json(self, {"error": str(exc)}, 400)
            return

        job_id = uuid.uuid4().hex
        with _jobs_lock:
            jobs[job_id] = queue.Queue()
        threading.Thread(
            target=_run_job,
            args=(job_id, action, mod_name, opts),
            name=f"embertools-job-{job_id[:8]}",
            daemon=True,
        ).start()
        _json(self, {"job_id": job_id})

    def _stream(self, job_id: str) -> None:
        with _jobs_lock:
            out = jobs.get(job_id)
        if out is None:
            _json(self, {"error": "unknown job"}, 404)
            return

        self.close_connection = True          # close cleanly once the job is done
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        while True:
            try:
                event = out.get(timeout=15)
            except queue.Empty:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                continue
            if event["kind"] == "log":
                data = json.dumps(event["line"])
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
            else:
                data = json.dumps({k: v for k, v in event.items() if k != "kind"})
                self.wfile.write(f"event: done\ndata: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                return
            self.wfile.flush()

    def _static(self, path: str) -> None:
        relative = Path(unquote(path.lstrip("/"))) if path != "/" else Path("index.html")
        candidate = (UI_DIR / relative).resolve()
        if candidate == UI_DIR or UI_DIR not in candidate.parents or not candidate.is_file():
            _json(self, {"error": "not found"}, 404)
            return
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(candidate))[0]
                         or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start the server in a background thread and return it. Caller stops it
    with `httpd.shutdown()`."""
    httpd = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=httpd.serve_forever, name="embertools-ui", daemon=True).start()
    return httpd


def url_for(httpd: ThreadingHTTPServer) -> str:
    host, port = httpd.server_address[0], httpd.server_port
    return f"http://{host}:{port}/"


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Serve the GUI until interrupted (blocking)."""
    httpd = start(host, port)
    url = url_for(httpd)
    print(f"embertools GUI: {url}   (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.15, webbrowser.open, args=(url,)).start()
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()
