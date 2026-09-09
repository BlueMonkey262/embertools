"""Install APK files and split-APK archives over ADB."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path


_ARCHIVE_SUFFIXES = {".apkm", ".xapk", ".apks"}
_SUPPORTED_SUFFIXES = {".apk", *_ARCHIVE_SUFFIXES}


def _log_output(log, output) -> None:
    for line in str(output or "").splitlines():
        if line.strip():
            log(line)


def _looks_like_failure(output) -> bool:
    text = str(output or "").lower()
    return "failure [" in text or "install_failed" in text or "error:" in text


def _checked_call(method, *args, **kwargs):
    """Call an Adb method with checking, while keeping simple test doubles usable."""
    try:
        output = method(*args, **kwargs)
    except TypeError as exc:
        # Small stubs commonly expose only *args; the real Adb methods accept
        # check/timeout keywords. Do not hide unrelated TypeErrors.
        if not any(word in str(exc) for word in ("keyword", "positional argument", "unexpected")):
            raise
        output = method(*args)
    if _looks_like_failure(output):
        raise RuntimeError(str(output).strip())
    return output


def _safe_extract(archive: zipfile.ZipFile, root: Path) -> None:
    root = root.resolve()
    for member in archive.infolist():
        if member.is_dir():
            continue
        destination = (root / member.filename).resolve()
        if root != destination and root not in destination.parents:
            raise ValueError(f"archive contains an unsafe path: {member.filename}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(member))


def _manifest_package(value):
    if isinstance(value, dict):
        for key in ("package_name", "packageName", "package"):
            package = value.get(key)
            if isinstance(package, str) and package:
                return package
        for child in value.values():
            package = _manifest_package(child)
            if package:
                return package
    elif isinstance(value, list):
        for child in value:
            package = _manifest_package(child)
            if package:
                return package
    return None


def _valid_package(package) -> bool:
    return bool(package) and all(char.isalnum() or char in "._" for char in package)


def _install_one(adb, path: Path, log) -> tuple[bool, str]:
    name = path.name
    suffix = path.suffix.lower()
    try:
        if suffix == ".apk":
            log(f"installing {name}")
            output = _checked_call(adb.install, str(path), "-r", "-g")
            _log_output(log, output)
        elif suffix in _ARCHIVE_SUFFIXES:
            log(f"extracting {name}")
            with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(
                prefix="embertools-sideload-"
            ) as temp:
                root = Path(temp)
                manifest = None
                if suffix == ".xapk" and "manifest.json" in archive.namelist():
                    try:
                        manifest = json.loads(archive.read("manifest.json"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        log(f"warning: could not read manifest.json: {exc}")
                _safe_extract(archive, root)
                apks = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".apk")
                obbs = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".obb")
                if not apks:
                    raise ValueError("archive contains no .apk files")
                log(f"installing {len(apks)} split APKs")
                output = _checked_call(
                    adb.raw,
                    "install-multiple",
                    "-r",
                    "-g",
                    *(str(apk) for apk in apks),
                    timeout=180,
                    check=True,
                )
                _log_output(log, output)

                if obbs:
                    package = _manifest_package(manifest)
                    if not _valid_package(package):
                        log("warning: xapk has obb files but no usable package in manifest.json; skipping obb")
                    else:
                        remote_dir = f"/sdcard/Android/obb/{package}"
                        _checked_call(adb.shell, f"mkdir -p {remote_dir}", check=True)
                        for obb in obbs:
                            remote = f"{remote_dir}/{obb.name}"
                            log(f"pushing {obb.name} to {remote}")
                            _checked_call(adb.push, str(obb), remote, check=True)
        else:
            raise ValueError("unsupported file type; expected .apk, .apkm, .xapk, or .apks")
    except Exception as exc:
        reason = " ".join(str(exc).splitlines()) or exc.__class__.__name__
        log(f"failed: {name}: {reason}")
        return False, reason
    log(f"ok: {name}")
    return True, ""


def install_path(adb, path: str, log=print) -> dict:
    """Install one APK/archive or every supported package in a directory."""
    target = Path(path).expanduser()
    installed = []
    failed = []

    if target.is_dir():
        candidates = sorted(
            (item for item in target.rglob("*")
             if item.is_file() and item.suffix.lower() in _SUPPORTED_SUFFIXES),
            key=lambda item: str(item),
        )
        if not candidates:
            failed.append((target.name or str(target), "directory contains no supported APK files"))
            log(f"failed: {target}: directory contains no supported APK files")
        for item in candidates:
            ok, reason = _install_one(adb, item, log)
            if ok:
                installed.append(item.name)
            else:
                failed.append((item.name, reason))
    elif target.is_file():
        ok, reason = _install_one(adb, target, log)
        if ok:
            installed.append(target.name)
        else:
            failed.append((target.name, reason))
    else:
        name = target.name or str(target)
        reason = "path does not exist or is not a file/directory"
        failed.append((name, reason))
        log(f"failed: {name}: {reason}")

    log(f"installed {len(installed)}, failed {len(failed)}")
    return {"ok": not failed, "installed": installed, "failed": failed}
