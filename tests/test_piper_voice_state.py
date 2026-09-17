import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from vocari.tts import piper_provider
from vocari.tts.piper_provider import PiperTTSProvider
from vocari.tts.piper_voices import PIPER_VOICES, PiperVoice
from vocari.ui.piper_tab import PiperTab


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PiperVoiceStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["piper-state-test", "-platform", "offscreen"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.voice_id = PIPER_VOICES[0].voice_id
        self.model = b"verified onnx"
        self.config = b'{"verified":true}'
        self.voice = PiperVoice(
            self.voice_id, "ru", "Test voice", 1, digest(self.model), digest(self.config)
        )
        self.patches = [
            patch.object(piper_provider, "VOICES_DIR", self.root),
            patch.dict(piper_provider._VOICES_BY_ID, {self.voice_id: self.voice}, clear=True),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        piper_provider._VOICE_CHECK_CACHE.clear()
        self.addCleanup(piper_provider._VOICE_CHECK_CACHE.clear)
        self.provider = PiperTTSProvider()

    @property
    def model_path(self):
        return self.root / f"{self.voice_id}.onnx"

    @property
    def config_path(self):
        return self.root / f"{self.voice_id}.onnx.json"

    def test_voice_requires_both_files(self):
        self.assertEqual(self.provider.voice_state(self.voice_id), "missing")
        self.model_path.write_bytes(self.model)
        self.assertEqual(self.provider.voice_state(self.voice_id), "incomplete")
        self.assertFalse(self.provider.is_voice_available(self.voice_id))
        self.assertEqual(self.provider.available_voices(), [])

    def test_both_verified_files_are_ready_and_listed(self):
        self.model_path.write_bytes(self.model)
        self.config_path.write_bytes(self.config)
        self.assertEqual(self.provider.voice_state(self.voice_id), "ready")
        self.assertTrue(self.provider.is_voice_available(self.voice_id))
        self.assertEqual(self.provider.available_voices(), [self.voice_id])

    def test_corrupt_model_or_config_is_rejected(self):
        for model, config in ((b"bad model", self.config), (self.model, b"bad config")):
            with self.subTest(model=model, config=config):
                self.model_path.write_bytes(model)
                self.config_path.write_bytes(config)
                piper_provider._VOICE_CHECK_CACHE.clear()
                self.assertEqual(self.provider.voice_state(self.voice_id), "corrupt")
                self.assertFalse(self.provider.is_voice_available(self.voice_id))

    def test_incomplete_voice_cannot_reach_piper_process(self):
        self.model_path.write_bytes(self.model)
        with patch.object(self.provider, "is_engine_available", return_value=True), \
                patch.object(self.provider, "_synthesize_sync") as synthesize:
            with self.assertRaisesRegex(RuntimeError, "не скачан"):
                asyncio.run(self.provider.synthesize("test", self.voice_id, "ru"))
        synthesize.assert_not_called()

    def test_ui_offers_redownload_for_incomplete_and_corrupt_voice(self):
        original = PIPER_VOICES[0]
        self.model_path.write_bytes(self.model)
        with patch.object(PiperTTSProvider, "is_engine_available", return_value=True):
            tab = PiperTab()
            tab._refresh_voice_state(original)
            self.assertEqual(tab.voice_status[self.voice_id].text(), "скачан не полностью")
            self.assertEqual(tab.voice_buttons[self.voice_id].text(), "Скачать заново")
            self.assertTrue(tab.voice_buttons[self.voice_id].isEnabled())

            self.config_path.write_bytes(b"bad config")
            piper_provider._VOICE_CHECK_CACHE.clear()
            tab._refresh_voice_state(original)
            self.assertEqual(tab.voice_status[self.voice_id].text(), "файлы повреждены")
            self.assertEqual(tab.voice_buttons[self.voice_id].text(), "Скачать заново")

    def test_successful_download_invalidates_old_cached_state(self):
        self.model_path.write_bytes(b"bad model")
        self.config_path.write_bytes(b"bad config")
        self.assertEqual(self.provider.voice_state(self.voice_id), "corrupt")

        def verified_download(_url, destination, _progress, *, sha256, is_cancelled=None):
            data = self.model if destination.suffix == ".onnx" else self.config
            self.assertEqual(digest(data), sha256)
            destination.write_bytes(data)

        with patch.object(piper_provider, "download_raw_file", side_effect=verified_download):
            piper_provider.download_voice(self.voice, lambda *_: None)
        self.assertEqual(self.provider.voice_state(self.voice_id), "ready")


if __name__ == "__main__":
    unittest.main()
