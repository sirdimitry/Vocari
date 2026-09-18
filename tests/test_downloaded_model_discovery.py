import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QLabel

from vocari.config.settings import AppConfig
from vocari import runtime_deps
from vocari.tts import piper_provider
from vocari.tts import silero_provider
from vocari.tts.piper_provider import PiperTTSProvider
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.ui.piper_tab import PiperTab
from vocari.ui.silero_tab import SileroTab
from vocari.ui.tts_tab import TTSTab


class DownloadedModelDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["model-discovery-test", "-platform", "offscreen"])

    def test_silero_finds_and_removes_current_and_legacy_cache_layouts(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(silero_provider, "CACHE_DIR", Path(folder)):
            provider = SileroTTSProvider()
            current, legacy = provider._model_candidates("ru")
            current.parent.mkdir(parents=True)
            legacy.parent.mkdir(parents=True)
            current.write_bytes(b"current")
            legacy.write_bytes(b"legacy")

            self.assertTrue(provider.has_cached_model("ru"))
            provider.remove_cached_model("ru")
            self.assertFalse(current.exists())
            self.assertFalse(legacy.exists())
            self.assertFalse(provider.has_cached_model("ru"))

    def test_silero_tab_auto_loads_every_cached_language(self):
        provider = Mock()
        provider.is_loaded.return_value = False
        provider.has_cached_model.side_effect = lambda lang: lang in {"ru", "en"}
        provider.speakers.side_effect = lambda lang: [f"{lang}_voice_1", f"{lang}_voice_2"]
        received = {}
        with patch("vocari.ui.silero_tab._torch_available", return_value=True):
            tab = SileroTab(provider, lambda lang, voices: received.__setitem__(lang, voices))
        with patch.object(tab, "_start_preload") as start:
            tab._auto_load_cached_models()
        self.assertEqual([call.args[0] for call in start.call_args_list], ["ru", "en"])
        self.assertTrue(all(call.kwargs == {"cached_only": True} for call in start.call_args_list))

        tab._on_preload_finished("en", "2", "")
        self.assertEqual(received["en"], ["en_voice_1", "en_voice_2"])
        tab.shutdown()

    def test_restart_discovers_and_verifies_every_silero_language_and_layout(self):
        for layout in (0, 1):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as folder, \
                    patch.object(silero_provider, "CACHE_DIR", Path(folder)):
                first_run = SileroTTSProvider()
                hashes = {}
                for lang in silero_provider.MODEL_ID_BY_LANG:
                    content = f"cached {lang}".encode()
                    path = first_run._model_candidates(lang)[layout]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    hashes[lang] = hashlib.sha256(content).hexdigest()
                restarted = SileroTTSProvider()
                with patch.dict(silero_provider.MODEL_SHA256_BY_LANG, hashes), \
                        patch.object(silero_provider, "download_raw_file") as download:
                    for lang in hashes:
                        self.assertFalse(restarted.is_loaded(lang))
                        self.assertTrue(restarted.has_cached_model(lang))
                        self.assertEqual(
                            restarted._verified_model_path(lang, allow_download=False),
                            restarted._model_candidates(lang)[layout],
                        )
                    download.assert_not_called()

    def test_startup_rejects_corrupt_silero_without_downloading(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(silero_provider, "CACHE_DIR", Path(folder)), \
                patch.object(silero_provider, "download_raw_file") as download:
            provider = SileroTTSProvider()
            path = provider._model_candidates("ru")[0]
            path.parent.mkdir(parents=True)
            path.write_bytes(b"truncated")
            with self.assertRaises(ValueError):
                provider._verified_model_path("ru", allow_download=False)
            download.assert_not_called()

    def test_silero_republishes_loaded_models_without_starting_workers(self):
        provider = Mock()
        provider.is_loaded.return_value = True
        provider.speakers.return_value = ["speaker_a", "speaker_b"]
        received = {}
        with patch("vocari.ui.silero_tab._torch_available", return_value=True):
            tab = SileroTab(provider, lambda lang, voices: received.__setitem__(lang, voices))
        tab._auto_load_cached_models()
        self.assertEqual(received, {"ru": ["speaker_a", "speaker_b"], "en": ["speaker_a", "speaker_b"]})
        self.assertFalse(tab._threads)
        provider.preload.assert_not_called()
        tab.shutdown()

    def test_silero_reports_cached_models_even_without_torch(self):
        provider = Mock()
        provider.has_cached_model.side_effect = lambda lang: lang == "ru"
        with patch("vocari.ui.silero_tab._torch_available", return_value=False):
            tab = SileroTab(provider)
        labels = [label.text() for label in tab.findChildren(QLabel)]
        self.assertTrue(any("Русский (v4_ru): скачана;" in label for label in labels))
        self.assertTrue(any("English (v3_en): не скачана" in label for label in labels))
        provider.preload.assert_not_called()
        tab.shutdown()

    def test_piper_distinguishes_existing_unverified_engine_from_missing(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(piper_provider, "ENGINE_DIR", Path(folder) / "engine" / "piper"), \
                patch.object(piper_provider, "is_downloaded", return_value=False):
            provider = PiperTTSProvider()
            self.assertEqual(provider.engine_state(), "missing")
            piper_provider.ENGINE_DIR.mkdir(parents=True)
            self.assertEqual(provider.engine_state(), "unverified")
            self.assertFalse(provider.is_engine_available())

    def test_silero_does_not_start_duplicate_preload(self):
        provider = Mock()
        provider.is_loaded.return_value = False
        with patch("vocari.ui.silero_tab._torch_available", return_value=True):
            tab = SileroTab(provider)
        tab._threads["ru"] = Mock()
        with patch("vocari.ui.silero_tab.QThread") as thread:
            tab._start_preload("ru")
        thread.assert_not_called()
        tab._threads.clear()
        tab.shutdown()

    def test_tts_tab_has_no_fake_silero_voice_subset_and_restores_piper(self):
        config = AppConfig()
        config.tts.provider = "piper"
        tab = TTSTab(config)
        self.assertEqual(tab.provider_combo.currentData(), "piper")
        self.assertEqual(tab._silero_voices, {"ru": [], "en": []})

    def test_piper_publishes_already_downloaded_voices_on_open(self):
        received = {}
        voices = ["ru_RU-irina-medium", "en_US-lessac-medium"]
        with patch("vocari.ui.piper_tab.PiperTTSProvider.is_engine_available", return_value=True), \
                patch("vocari.ui.piper_tab.PiperTTSProvider.is_voice_available", return_value=False), \
                patch("vocari.ui.piper_tab.PiperTTSProvider.voice_state", return_value="missing"), \
                patch("vocari.ui.piper_tab.PiperTTSProvider.available_voices", return_value=voices):
            tab = PiperTab(lambda lang, found: received.__setitem__(lang, found))
        self.assertEqual(received["ru"], ["ru_RU-irina-medium"])
        self.assertEqual(received["en"], ["en_US-lessac-medium"])
        tab.shutdown()

    def test_piper_cleanup_is_available_without_valid_downloads(self):
        with patch("vocari.ui.piper_tab.PiperTTSProvider.is_engine_available", return_value=False), \
                patch("vocari.ui.piper_tab.PiperTTSProvider.voice_state", return_value="incomplete"), \
                patch("vocari.ui.piper_tab.PiperTTSProvider.available_voices", return_value=[]):
            tab = PiperTab()
        self.assertTrue(tab.clear_button.isEnabled())
        voice_id = next(iter(tab.voice_buttons))
        tab._threads[voice_id] = Mock()
        tab.voice_buttons[voice_id].setEnabled(False)
        tab.voice_status[voice_id].setText("downloading")
        tab._refresh_all_voice_states()
        self.assertFalse(tab.clear_button.isEnabled())
        self.assertFalse(tab.voice_buttons[voice_id].isEnabled())
        self.assertEqual(tab.voice_status[voice_id].text(), "downloading")
        tab._threads.clear()
        tab.shutdown()

    def test_piper_cleanup_removes_engine_and_all_voices(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            runtime_root = base / "runtime_deps"
            engine = runtime_root / "piper_engine"
            voices = runtime_root / "piper_voices"
            engine.mkdir(parents=True)
            voices.mkdir()
            (engine / ".complete").write_text("test", encoding="utf-8")
            (voices / "voice.onnx").write_bytes(b"voice")
            with patch.object(runtime_deps, "RUNTIME_DEPS_DIR", runtime_root), \
                    patch.object(piper_provider, "VOICES_DIR", voices), \
                    patch.object(piper_provider, "app_root", return_value=base):
                PiperTTSProvider().remove_all_downloads()
            self.assertFalse(engine.exists())
            self.assertFalse(voices.exists())

    def test_installer_excludes_and_removes_documentation_banner(self):
        script = Path("installer/vocari.iss").read_text(encoding="utf-8")
        self.assertIn("assets\\branding\\banner_github.png", script)
        self.assertIn("[InstallDelete]", script)


if __name__ == "__main__":
    unittest.main()
