import unittest

from embertools.core import device_ops


class FakeAdb:
    def __init__(self, package_output="", disabled_output="", uninstall_result="Failure"):
        self.package_output = package_output
        self.disabled_output = disabled_output
        self.uninstall_result = uninstall_result
        self.calls = []

    def shell(self, command):
        self.calls.append(("shell", command))
        if command == "pm list packages -3":
            return self.package_output
        if command == "pm list packages -d -3":
            return self.disabled_output
        if command == "pm uninstall --user 0 com.example.app":
            return "Success"
        return ""

    def raw(self, *args):
        self.calls.append(("raw", args))
        if args == ("uninstall", "com.example.app"):
            return self.uninstall_result
        return ""

    def uninstall(self, pkg):
        return self.raw("uninstall", pkg)


class DeviceOpsTests(unittest.TestCase):
    def test_list_packages_parses_enabled_and_disabled(self):
        adb = FakeAdb(
            package_output="package:com.example.enabled\npackage:com.example.disabled\n",
            disabled_output="package:com.example.disabled\n",
        )
        self.assertEqual(
            device_ops.list_packages(adb),
            [
                {"pkg": "com.example.disabled", "enabled": False, "system": False},
                {"pkg": "com.example.enabled", "enabled": True, "system": False},
            ],
        )

    def test_power_reboot_calls_adb_reboot(self):
        adb = FakeAdb()
        device_ops.power(adb, "reboot", lambda _message: None)
        self.assertIn(("raw", ("reboot",)), adb.calls)

    def test_uninstall_falls_back_to_user_uninstall(self):
        adb = FakeAdb(uninstall_result="Failure [DELETE_FAILED_INTERNAL_ERROR]")
        device_ops.uninstall(adb, "com.example.app", lambda _message: None)
        self.assertIn(("raw", ("uninstall", "com.example.app")), adb.calls)
        self.assertIn(("shell", "pm uninstall --user 0 com.example.app"), adb.calls)


if __name__ == "__main__":
    unittest.main()
