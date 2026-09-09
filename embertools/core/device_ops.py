"""Small, stdlib-only device-management operations for the GUI."""

from __future__ import annotations

import re


_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+\Z")
_POWER_ACTIONS = {"reboot", "recovery", "shutdown"}


def _check_pkg(pkg: str) -> None:
    if not isinstance(pkg, str) or not _PACKAGE.fullmatch(pkg):
        raise ValueError("invalid package name")


def _packages(output: str) -> set[str]:
    result = set()
    for line in (output or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkg = line[len("package:"):].strip()
            if pkg:
                result.add(pkg)
    return result


def list_packages(adb) -> list[dict]:
    """Return third-party packages, including disabled third-party packages."""
    all_packages = _packages(adb.shell("pm list packages -3"))
    disabled = _packages(adb.shell("pm list packages -d -3"))
    all_packages.update(disabled)
    return [
        {"pkg": pkg, "enabled": pkg not in disabled, "system": False}
        for pkg in sorted(all_packages)
    ]


def _success(result) -> bool:
    text = str(result or "").lower()
    return "success" in text and "failure" not in text


def uninstall(adb, pkg: str, log) -> None:
    _check_pkg(pkg)
    try:
        result = adb.uninstall(pkg)
        if _success(result):
            log(f"uninstalled {pkg}: {result}")
            return
        log(f"adb uninstall {pkg} failed: {result or 'no result'}; trying user uninstall")
    except Exception as exc:
        log(f"adb uninstall {pkg} failed: {exc}; trying user uninstall")
    result = adb.shell(f"pm uninstall --user 0 {pkg}")
    log(f"user uninstall {pkg}: {result}")
    if not _success(result):
        raise RuntimeError(f"could not uninstall {pkg}: {result or 'no result'}")


def set_enabled(adb, pkg: str, enabled: bool, log) -> None:
    _check_pkg(pkg)
    command = f"pm enable {pkg}" if enabled else f"pm disable-user --user 0 {pkg}"
    result = adb.shell(command)
    log(f"{('enabled' if enabled else 'disabled')} {pkg}: {result}")


def power(adb, action: str, log) -> None:
    if action not in _POWER_ACTIONS:
        raise ValueError(f"unknown power action: {action}")
    log(f"power: {action} (the ADB connection is expected to drop)")
    if action == "reboot":
        result = adb.raw("reboot")
    elif action == "recovery":
        result = adb.raw("reboot", "recovery")
    else:
        result = adb.shell("reboot -p")
    if result:
        log(str(result))
