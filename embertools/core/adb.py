"""Thin wrapper around the `adb` CLI, bound to one device serial."""

from __future__ import annotations

import shutil
import subprocess
import time


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, serial: str | None = None, adb_bin: str = "adb"):
        self.adb_bin = shutil.which(adb_bin) or adb_bin
        self.serial = serial

    # -- low level -----------------------------------------------------------

    def raw(self, *args: str, timeout: int = 60, check: bool = False) -> str:
        cmd = [self.adb_bin]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise AdbError(f"adb not found ({self.adb_bin!r}). Install platform-tools.")
        except subprocess.TimeoutExpired:
            raise AdbError(f"adb {' '.join(args)} timed out after {timeout}s")
        out = (r.stdout + r.stderr).strip()
        if check and r.returncode != 0:
            raise AdbError(f"adb {' '.join(args)} failed:\n{out}")
        return out

    def shell(self, cmd: str, timeout: int = 60, check: bool = False) -> str:
        return self.raw("shell", cmd, timeout=timeout, check=check)

    # -- helpers -----------------------------------------------------------

    def getprop(self, key: str) -> str:
        return self.shell(f"getprop {key}").strip()

    def get_secure(self, key: str) -> str:
        v = self.shell(f"settings get secure {key}").strip()
        return "" if v in ("null", "") else v

    def get_global(self, key: str) -> str:
        v = self.shell(f"settings get global {key}").strip()
        return "" if v in ("null", "") else v

    def put_secure(self, key: str, value: str) -> None:
        self.shell(f"settings put secure {key} {value}")

    def put_global(self, key: str, value: str) -> None:
        self.shell(f"settings put global {key} {value}")

    def delete_secure(self, key: str) -> None:
        self.shell(f"settings delete secure {key}")

    def install(self, apk_path: str, *flags: str) -> str:
        return self.raw("install", *flags, apk_path, timeout=180)

    def uninstall(self, pkg: str) -> str:
        return self.raw("uninstall", pkg)

    def push(self, local: str, remote: str) -> str:
        return self.raw("push", local, remote, timeout=120)

    def pkg_installed(self, pkg: str) -> bool:
        return f"package:{pkg}" in self.shell(f"pm list packages {pkg}")

    def pkg_disabled(self, pkg: str) -> bool:
        return f"package:{pkg}" in self.shell("pm list packages -d")

    def reboot_wait(self, settle: int = 35, timeout: int = 240) -> None:
        self.raw("reboot")
        time.sleep(3)
        self.raw("wait-for-device", timeout=timeout)
        time.sleep(settle)
        self.shell("input keyevent KEYCODE_WAKEUP")

    # -- discovery -------------------------------------------------------

    @staticmethod
    def list_devices(adb_bin: str = "adb") -> list[str]:
        exe = shutil.which(adb_bin) or adb_bin
        try:
            r = subprocess.run([exe, "devices"], capture_output=True, text=True, timeout=15)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        devs = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devs.append(parts[0])
        return devs

    @staticmethod
    def any_unauthorized(adb_bin: str = "adb") -> bool:
        exe = shutil.which(adb_bin) or adb_bin
        try:
            r = subprocess.run([exe, "devices"], capture_output=True, text=True, timeout=15)
        except Exception:
            return False
        return any(p.split()[1:2] == ["unauthorized"] for p in r.stdout.splitlines()[1:] if p.strip())
