import unittest
from types import SimpleNamespace
from unittest.mock import patch

from embertools.core.mod import Status
from embertools.shared.launcher_swap.mod import LAUNCHERS, LauncherSwap, resolve_target


class FakeAdb:
    def __init__(self, installed=(), dumpsys_package="app.lawnchair"):
        self.installed = set(installed)
        self.dumpsys_package = dumpsys_package
        self.calls = []
        self.install_calls = []

    def pkg_installed(self, package):
        return package in self.installed

    def install(self, *args):
        self.install_calls.append(args)

    def shell(self, command):
        self.calls.append(command)
        if command.startswith("cmd package resolve-activity"):
            return "app.lawnchair/app.lawnchair.LawnchairLauncher"
        if command.startswith("dumpsys activity activities"):
            return f"mResumedActivity: ActivityRecord{{ u0 {self.dumpsys_package}/.Home }}"
        return ""


def context(adb, launcher="lawnchair"):
    return SimpleNamespace(
        adb=adb,
        opts={"launcher": launcher},
        log=lambda _message: None,
        state=SimpleNamespace(),
    )


class LauncherSwapTests(unittest.TestCase):
    def test_current_lawnchair_target(self):
        adb = FakeAdb(installed=("app.lawnchair",))
        self.assertEqual(
            resolve_target(context(adb), "lawnchair"),
            ("app.lawnchair", "app.lawnchair.LawnchairLauncher"),
        )

    def test_free_form_absolute_target(self):
        self.assertEqual(
            resolve_target(context(FakeAdb()), "com.foo/com.foo.Home"),
            ("com.foo", "com.foo.Home"),
        )

    def test_free_form_relative_target(self):
        self.assertEqual(
            resolve_target(context(FakeAdb()), "com.foo/.Home"),
            ("com.foo", "com.foo.Home"),
        )

    def test_resolve_target_rejects_missing_packages(self):
        with self.assertRaisesRegex(RuntimeError, "none of the lawnchair packages"):
            resolve_target(context(FakeAdb()), "lawnchair")

    def test_apply_rejects_missing_launcher_before_install(self):
        adb = FakeAdb()
        with self.assertRaisesRegex(RuntimeError, "none of the lawnchair packages"):
            LauncherSwap().apply(context(adb))
        self.assertEqual(adb.install_calls, [])

    @patch("embertools.shared.launcher_swap.mod.time.sleep")
    def test_verify_passes_for_target_launcher_without_opening_settings(self, sleep):
        adb = FakeAdb(installed=("app.lawnchair",), dumpsys_package="app.lawnchair")
        status = LauncherSwap().verify(
            context(adb)
        )
        self.assertEqual(status, Status(True, "Home opens app.lawnchair"))
        self.assertEqual(adb.calls.count("input keyevent KEYCODE_HOME"), 1)
        self.assertFalse(any(call.startswith("am start -n com.android.settings") for call in adb.calls))
        sleep.assert_called_once_with(1.5)

    @patch("embertools.shared.launcher_swap.mod.time.sleep")
    def test_verify_fails_after_three_home_checks(self, sleep):
        adb = FakeAdb(installed=("app.lawnchair",), dumpsys_package="com.amazon.firelauncher")
        status = LauncherSwap().verify(
            context(adb)
        )
        self.assertEqual(status, Status(
            False,
            "Home opened com.amazon.firelauncher instead of app.lawnchair",
        ))
        self.assertEqual(adb.calls.count("input keyevent KEYCODE_HOME"), 3)
        self.assertEqual(sleep.call_count, 3)
        self.assertTrue(all(call.args == (1.5,) for call in sleep.call_args_list))

    def test_launcher_keys(self):
        self.assertEqual(
            list(LAUNCHERS),
            [
                "nova",
                "lawnchair",
                "kvaesitso",
                "niagara",
                "olauncher",
                "smartlauncher",
            ],
        )


if __name__ == "__main__":
    unittest.main()
