import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vocari.config import dpapi
from vocari.config.settings import AppConfig, ConfigSaveError


class AtomicConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        key_patch = patch.object(dpapi, "_KEY_PATH", self.root / ".key")
        key_patch.start()
        self.addCleanup(key_patch.stop)
        self.path = self.root / "config.json"
        self.backup = self.root / "config.json.bak"
        self.config = AppConfig()
        self.config.tts.max_backlog_messages = 10
        self.config.save(self.path)

    def test_success_keeps_previous_settings_in_encrypted_backup(self):
        self.config.tts.max_backlog_messages = 100
        self.config.save(self.path)
        self.assertEqual(AppConfig.load(self.path).tts.max_backlog_messages, 100)
        self.assertEqual(AppConfig.load(self.backup).tts.max_backlog_messages, 10)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_failed_replace_preserves_primary_and_valid_backup(self):
        original = self.path.read_bytes()
        replace = os.replace

        def fail_primary(source, destination):
            if destination == self.path:
                raise OSError("Simulated blocked replacement")
            replace(source, destination)

        self.config.tts.max_backlog_messages = 100
        with patch("vocari.config.settings.os.replace", side_effect=fail_primary), self.assertRaises(ConfigSaveError):
            self.config.save(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(AppConfig.load(self.backup).tts.max_backlog_messages, 10)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_flush_failure_preserves_both_files(self):
        original, backup = self.path.read_bytes(), self.backup.read_bytes()
        self.config.tts.max_backlog_messages = 100
        with patch("vocari.config.settings.os.fsync", side_effect=OSError("Disk full")), self.assertRaises(ConfigSaveError):
            self.config.save(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), backup)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_corrupt_primary_recovers_without_overwriting_good_backup(self):
        original_backup = self.backup.read_bytes()
        for corrupt in (b"broken ciphertext", b"[]", b'{"tts":null}'):
            with self.subTest(corrupt=corrupt):
                self.path.write_bytes(corrupt)
                with self.assertLogs("vocari.config.settings", level="WARNING"):
                    restored = AppConfig.load(self.path)
                self.assertEqual(restored.tts.max_backlog_messages, 10)
                restored.tts.max_backlog_messages = 50
                restored.save(self.path)
                self.assertEqual(self.backup.read_bytes(), original_backup)
                self.assertEqual(AppConfig.load(self.path).tts.max_backlog_messages, 50)

    def test_missing_primary_recovers_backup(self):
        self.path.unlink()
        with self.assertLogs("vocari.config.settings", level="WARNING"):
            restored = AppConfig.load(self.path)
        self.assertEqual(restored.tts.max_backlog_messages, 10)

    def test_first_save_has_recoverable_backup(self):
        self.path.write_bytes(b"truncated")
        with self.assertLogs("vocari.config.settings", level="WARNING"):
            restored = AppConfig.load(self.path)
        self.assertEqual(restored.tts.max_backlog_messages, 10)


if __name__ == "__main__":
    unittest.main()
