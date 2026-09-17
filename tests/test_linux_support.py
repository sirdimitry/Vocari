import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import vocari.paths as paths
from vocari.hotkey import GlobalHotkeyManager
from vocari.runtime_deps import TORCH_CPU, download


class LinuxSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(
            ["linux-support-test", "-platform", "offscreen"]
        )

    def test_frozen_linux_uses_xdg_data_and_seeds_assets(self):
        old_root = paths._cached_root
        try:
            with TemporaryDirectory() as directory:
                base = Path(directory)
                install = base / "opt" / "vocari"
                bundled = install / "assets" / "models" / "Ariral"
                bundled.mkdir(parents=True)
                (bundled / "model.json").write_text("{}", encoding="utf-8")
                data_home = base / "data"

                paths._cached_root = None
                with (
                    patch.object(paths.sys, "frozen", True, create=True),
                    patch.object(paths.sys, "platform", "linux"),
                    patch.object(paths.sys, "executable", str(install / "Vocari")),
                    patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False),
                ):
                    root = paths.app_root()

                self.assertEqual(root, data_home / "vocari")
                self.assertTrue((root / "assets" / "models" / "Ariral" / "model.json").is_file())
                self.assertTrue((root / ".bundled-assets-version").is_file())
        finally:
            paths._cached_root = old_root

    def test_unsupported_torch_bundle_is_rejected_before_download(self):
        with patch("vocari.runtime_deps.TORCH_RUNTIME_DOWNLOAD_SUPPORTED", False):
            with self.assertRaisesRegex(RuntimeError, "не поддерживается"):
                download(TORCH_CPU, lambda _done, _total: None)

    def test_non_windows_hotkey_fails_cleanly_instead_of_crashing(self):
        with (
            patch("vocari.hotkey._IS_WINDOWS", False),
            patch("vocari.hotkey._IS_LINUX", False),
        ):
            manager = GlobalHotkeyManager(self.app)
            self.addCleanup(manager.shutdown)
            self.assertFalse(manager.set_binding("F9"))
            self.assertTrue(manager.set_binding(""))

    def test_arch_packaging_files_are_complete(self):
        root = Path(__file__).resolve().parent.parent
        template = (root / "linux" / "PKGBUILD.template").read_text(encoding="utf-8")
        workflow = (root / ".github" / "workflows" / "linux-endeavouros.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("xorg-xwayland", template)
        self.assertIn("@ARCHIVE_SHA256@", template)
        self.assertIn("archlinux:latest", workflow)
        self.assertIn("pacman -U", workflow)


if __name__ == "__main__":
    unittest.main()
