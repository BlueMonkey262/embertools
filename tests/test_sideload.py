import tempfile
import unittest
import zipfile
from pathlib import Path

from embertools.core.sideload import install_path


class FakeAdb:
    def __init__(self):
        self.install_calls = []
        self.raw_calls = []

    def install(self, *args):
        self.install_calls.append(args)
        return "Success"

    def raw(self, *args, **kwargs):
        self.raw_calls.append((args, kwargs))
        return "Success"


class SideloadTests(unittest.TestCase):
    def test_apkm_uses_install_multiple_for_all_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.apkm"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("base.apk", b"base")
                archive.writestr("config.arm64.apk", b"arm64")
            adb = FakeAdb()

            result = install_path(adb, str(path), log=lambda _line: None)

            self.assertTrue(result["ok"])
            self.assertEqual(adb.install_calls, [])
            self.assertEqual(len(adb.raw_calls), 1)
            args, kwargs = adb.raw_calls[0]
            self.assertEqual(args[:3], ("install-multiple", "-r", "-g"))
            self.assertEqual(len(args[3:]), 2)
            self.assertEqual(kwargs["timeout"], 180)
            self.assertTrue(kwargs["check"])

    def test_plain_apk_uses_install(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.apk"
            path.write_bytes(b"apk")
            adb = FakeAdb()

            result = install_path(adb, str(path), log=lambda _line: None)

            self.assertTrue(result["ok"])
            self.assertEqual(adb.install_calls, [(str(path), "-r", "-g")])
            self.assertEqual(adb.raw_calls, [])

    def test_unknown_suffix_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("not an apk")
            adb = FakeAdb()

            result = install_path(adb, str(path), log=lambda _line: None)

            self.assertFalse(result["ok"])
            self.assertEqual(len(result["failed"]), 1)
            self.assertEqual(adb.install_calls, [])
            self.assertEqual(adb.raw_calls, [])


if __name__ == "__main__":
    unittest.main()
