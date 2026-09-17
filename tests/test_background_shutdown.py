import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from vocari import runtime_deps
from vocari.config.settings import AppConfig, TwitchConfig
from vocari.tts.piper_provider import PiperTTSProvider
from vocari.tts.tts_queue import TTSQueue
from vocari.twitch.bot_controller import TwitchBotController
from vocari.ui.piper_tab import PiperTab, _DownloadWorker
from vocari.ui.silero_tab import SileroTab, _PreloadWorker


class CancellableProvider:
    def __init__(self):
        self.started = threading.Event()
        self.cancelled = threading.Event()

    async def synthesize(self, *args, **kwargs):
        self.started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class FakeTwitchSource:
    started = threading.Event()
    stopped = threading.Event()

    def __init__(self, config):
        self.stop_event = asyncio.Event()

    async def start(self, on_message, on_connected):
        self.started.set()
        await self.stop_event.wait()

    async def stop(self):
        self.stopped.set()
        self.stop_event.set()


class BackgroundShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["shutdown-test", "-platform", "offscreen"])

    def pump_until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Timed out waiting for background operation")
            time.sleep(0.001)

    def test_tts_shutdown_cancels_worker_and_releases_qthread(self):
        provider = CancellableProvider()
        instance = SimpleNamespace(id=1, text="test", author="", slot=0, phase="speaking")
        stage = SimpleNamespace(
            instances=[instance], get=lambda iid: instance if iid == 1 else None,
            on_speaker_ready=lambda callback: None, on_slot_freed=lambda callback: None,
        )
        audio = SimpleNamespace(stop=lambda: None)
        queue = TTSQueue(AppConfig(), {"edge": provider}, audio, SimpleNamespace(stage=stage))
        queue.config.bubble.announce_nick = False
        queue._start_synthesis(1)
        self.pump_until(provider.started.is_set)
        queue.shutdown()
        self.assertTrue(provider.cancelled.is_set())
        self.assertFalse(queue._synthesis_jobs)
        self.assertTrue(all(not thread.isRunning() for thread in queue.findChildren(QThread)))
        self.assertFalse(queue.enqueue("after shutdown"))

    def test_download_cancellation_preserves_destination_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "voice.onnx"
            destination.write_bytes(b"existing")
            cancelled = threading.Event()

            class Response:
                headers = {"Content-Length": "100"}
                calls = 0

                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, _size):
                    self.calls += 1
                    if self.calls == 1:
                        cancelled.set()
                        return b"partial"
                    return b""

            with patch.object(runtime_deps.urllib.request, "urlopen", return_value=Response()), \
                    self.assertRaises(runtime_deps.DownloadCancelled):
                runtime_deps.download_raw_file(
                    "https://example.test/voice", destination, lambda *_: None,
                    sha256="0" * 64, is_cancelled=cancelled.is_set,
                )
            self.assertEqual(destination.read_bytes(), b"existing")
            self.assertFalse(destination.with_suffix(".onnx.part").exists())

    def test_twitch_stop_wait_joins_connection_thread(self):
        FakeTwitchSource.started.clear()
        FakeTwitchSource.stopped.clear()
        controller = TwitchBotController(TwitchConfig(channel="test", oauth_token="token"))
        with patch("vocari.twitch.bot_controller.TwitchChatSource", FakeTwitchSource):
            controller.start()
            self.assertTrue(FakeTwitchSource.started.wait(5))
            controller.stop(wait=True)
        self.assertTrue(FakeTwitchSource.stopped.is_set())
        self.assertFalse(controller.is_running())

    def test_piper_tab_cancels_and_joins_download_thread(self):
        started = threading.Event()

        def controlled_download(_progress, is_cancelled):
            started.set()
            while not is_cancelled():
                time.sleep(0.001)
            raise runtime_deps.DownloadCancelled("cancelled")

        with patch.object(PiperTTSProvider, "is_engine_available", return_value=False):
            tab = PiperTab()
        thread = QThread(tab)
        worker = _DownloadWorker("controlled", controlled_download)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        tab._threads["controlled"] = thread
        tab._workers["controlled"] = worker
        thread.start()
        self.assertTrue(started.wait(5))
        tab.shutdown()
        self.assertFalse(thread.isRunning())
        self.assertFalse(tab._threads)
        self.assertFalse(tab._workers)

    def test_silero_tab_waits_for_running_preload(self):
        started = threading.Event()
        release = threading.Event()

        class Provider:
            def is_loaded(self, _lang): return False
            def preload(self, _lang):
                started.set()
                release.wait(5)
            def speakers(self, _lang): return []

        provider = Provider()
        with patch("vocari.ui.silero_tab._torch_available", return_value=True):
            tab = SileroTab(provider)
        thread = QThread(tab)
        worker = _PreloadWorker(provider, "ru")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        tab._threads["ru"] = thread
        tab._workers["ru"] = worker
        thread.start()
        self.assertTrue(started.wait(5))
        threading.Timer(0.05, release.set).start()
        before = time.monotonic()
        tab.shutdown()
        self.assertGreaterEqual(time.monotonic() - before, 0.04)
        self.assertFalse(thread.isRunning())
        self.assertFalse(tab._threads)


if __name__ == "__main__":
    unittest.main()
