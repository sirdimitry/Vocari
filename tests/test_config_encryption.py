import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vocari.config import dpapi
from vocari.config.settings import AppConfig, ConfigEncryptionError, ConfigSaveError


class ConfigEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"
        self.config = AppConfig()
        self.config.twitch.oauth_token = "oauth:test-secret-never-write-plaintext"

    def test_encryption_failures_preserve_previous_file(self):
        for error in (OSError, ImportError, ValueError):
            with self.subTest(error=error):
                self.path.write_bytes(b"previous encrypted settings")
                with patch.object(dpapi, "protect", side_effect=error(self.config.twitch.oauth_token)):
                    with self.assertRaises(ConfigEncryptionError) as raised:
                        self.config.save(self.path)
                self.assertEqual(self.path.read_bytes(), b"previous encrypted settings")
                self.assertNotIn(self.config.twitch.oauth_token, str(raised.exception))

    def test_failed_first_save_creates_no_file(self):
        with patch.object(dpapi, "protect", side_effect=OSError("unavailable")):
            with self.assertRaises(ConfigEncryptionError):
                self.config.save(self.path)
        self.assertFalse(self.path.exists())

    def test_disk_failure_never_retries_with_plaintext(self):
        with patch.object(dpapi, "protect", return_value=b"encrypted"), \
                patch("vocari.config.settings._atomic_write", side_effect=OSError("disk full")) as write:
            with self.assertRaises(ConfigSaveError):
                self.config.save(self.path)
        write.assert_called_once_with(self.path.with_name("config.json.bak"), b"encrypted")

    def test_missing_cryptography_refuses_plaintext_on_non_windows(self):
        original_import = builtins.__import__

        def import_without_crypto(name, *args, **kwargs):
            if name == "cryptography.fernet":
                raise ImportError("not installed")
            return original_import(name, *args, **kwargs)

        with patch.object(dpapi, "_IS_WINDOWS", False), \
                patch("builtins.__import__", side_effect=import_without_crypto):
            with self.assertRaises(OSError):
                dpapi.protect(b"secret")

    @unittest.skipUnless(dpapi._IS_WINDOWS, "Requires Windows DPAPI")
    def test_real_encrypted_save_and_legacy_migration(self):
        self.config.save(self.path)
        self.assertNotIn(self.config.twitch.oauth_token.encode(), self.path.read_bytes())
        self.assertEqual(AppConfig.load(self.path).twitch.oauth_token, self.config.twitch.oauth_token)
        self.path.write_text('{"twitch":{"oauth_token":"legacy-secret"}}', encoding="utf-8")
        migrated = AppConfig.load(self.path)
        migrated.save(self.path)
        self.assertNotIn(b"legacy-secret", self.path.read_bytes())
        self.assertNotIn(b"legacy-secret", self.path.with_name("config.json.bak").read_bytes())
        self.assertEqual(AppConfig.load(self.path).twitch.oauth_token, "legacy-secret")

    def test_save_failure_is_reported_to_user(self):
        from vocari.main import _log_unhandled_exception

        app = Mock()
        error = ConfigEncryptionError("Settings encryption failed")
        with patch("vocari.main.QApplication.instance", return_value=app), \
                patch("vocari.main.QMessageBox.warning") as warning, \
                self.assertLogs("vocari.main", level="ERROR"):
            _log_unhandled_exception(type(error), error, None)
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[0], app.activeWindow())
        self.assertEqual(warning.call_args.args[2], str(error))

    def test_write_failure_is_reported_to_user(self):
        from vocari.main import _log_unhandled_exception

        error = ConfigSaveError("Settings write failed")
        with patch("vocari.main.QApplication.instance", return_value=Mock()), \
                patch("vocari.main.QMessageBox.warning") as warning, \
                self.assertLogs("vocari.main", level="ERROR"):
            _log_unhandled_exception(type(error), error, None)
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
