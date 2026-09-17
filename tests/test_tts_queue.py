import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QThread

from vocari.config.settings import AppConfig
from vocari.tts.base import SynthesisResult
from vocari.tts.tts_queue import TTSQueue
from vocari.rendering.stage import Stage


class ControlledProvider:
    def __init__(self, fail_old):
        self.started = {text: threading.Event() for text in ("old", "new")}
        self.release = {text: threading.Event() for text in ("old", "new")}
        self.fail_old = fail_old

    async def synthesize(self, text, voice, lang, **kwargs):
        self.started[text].set()
        if not self.release[text].wait(5):
            raise TimeoutError("Test did not release synthesis")
        if text == "old" and self.fail_old:
            raise RuntimeError("Expected old synthesis failure")
        return SynthesisResult(text.encode())


class TTSQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def pump_until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Timed out waiting for Qt worker")
            time.sleep(0.001)

    def check_skipped_result(self, fail_old=False, old_finishes_first=False):
        provider = ControlledProvider(fail_old)
        instances = {
            iid: SimpleNamespace(id=iid, text=text, author="", slot=0, phase="speaking")
            for iid, text in ((1, "old"), (2, "new"))
        }
        instances[2].slot = 2
        stage = SimpleNamespace(
            instances=list(instances.values()), get=instances.get,
            on_speaker_ready=lambda callback: None, on_slot_freed=lambda callback: None,
        )
        retired = []

        def retire(iid):
            retired.append(iid)
            instances[iid].phase = "exiting"
            instances[iid].slot = -1

        window = SimpleNamespace(stage=stage, retire_speaker=retire)
        config = AppConfig()
        config.bubble.announce_nick = False
        config.render.pre_speech_delay_ms = 0
        queue = TTSQueue(config, {"edge": provider}, SimpleNamespace(stop=lambda: None), window)
        played = []
        queue._start_playback = lambda iid, audio: played.append((iid, audio, QThread.currentThread()))
        try:
            queue._start_synthesis(1)
            self.pump_until(provider.started["old"].is_set)
            queue.skip_current()
            instances[2].slot = 0
            queue._start_synthesis(2)
            self.pump_until(provider.started["new"].is_set)
            first, second = ("old", "new") if old_finishes_first else ("new", "old")
            provider.release[first].set()
            self.pump_until(lambda: len(queue._synthesis_jobs) == 1)
            provider.release[second].set()
            self.pump_until(lambda: not queue._synthesis_jobs and bool(played))
            self.assertEqual(played, [(2, b"new", self.app.thread())])
            self.assertEqual(retired, [1])
        finally:
            for gate in provider.release.values():
                gate.set()
            self.pump_until(lambda: not queue._synthesis_jobs)
            queue._cancel_deferred()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertFalse(queue.findChildren(QThread))

    def test_skipped_audio_finishes_after_new_audio(self):
        self.check_skipped_result()

    def test_skipped_audio_finishes_before_new_audio(self):
        self.check_skipped_result(old_finishes_first=True)

    def test_skipped_error_does_not_retire_new_speaker(self):
        self.check_skipped_result(fail_old=True)

    def make_bounded_queue(self):
        stage = Stage(canvas_width=100)
        window = SimpleNamespace(
            stage=stage, add_speaker=stage.add, retire_speaker=stage.retire,
            has_bubble_preview=lambda: False,
        )
        queue = TTSQueue(AppConfig(), {}, None, window)
        queue._start_synthesis = Mock()
        return queue, stage

    @patch("vocari.tts.tts_queue.time.monotonic", return_value=100.0)
    def test_overflow_preserves_accepted_messages_and_order(self, clock):
        queue, stage = self.make_bounded_queue()
        queue.config.tts.max_backlog_messages = 2
        for i in range(9):
            self.assertTrue(queue.enqueue(str(i)))
        with self.assertLogs("vocari.tts.queue", level="WARNING"):
            self.assertFalse(queue.enqueue("overflow"))
        self.assertEqual([i.text for i in stage.instances], list(map(str, range(7))))
        self.assertEqual([item[0] for item in queue._backlog], ["7", "8"])
        stage.retire(stage.instances[0].id)
        self.assertEqual(stage.instances[-1].text, "7")
        self.assertTrue(queue.enqueue("9"))
        self.assertEqual([item[0] for item in queue._backlog], ["8", "9"])

    @patch("vocari.tts.tts_queue.time.monotonic", return_value=100.0)
    def test_live_limit_changes_preserve_existing_reserve(self, clock):
        queue, stage = self.make_bounded_queue()
        queue.config.tts.max_backlog_messages = 1
        for i in range(8):
            self.assertTrue(queue.enqueue(str(i)))
        with self.assertLogs("vocari.tts.queue", level="WARNING"):
            self.assertFalse(queue.enqueue("rejected"))
        queue.config.tts.max_backlog_messages = 100
        for i in range(8, 107):
            self.assertTrue(queue.enqueue(str(i)))
        queue.config.tts.max_backlog_messages = 1
        with self.assertLogs("vocari.tts.queue", level="WARNING"):
            self.assertFalse(queue.enqueue("rejected again"))
        self.assertEqual([item[0] for item in queue._backlog], list(map(str, range(7, 107))))

    @patch("vocari.tts.tts_queue.time.monotonic", return_value=100.0)
    def test_expired_reserve_is_discarded_before_new_admission(self, clock):
        queue, stage = self.make_bounded_queue()
        for i in range(9):
            queue.enqueue(str(i))
        clock.return_value = 220.0
        with self.assertLogs("vocari.tts.queue", level="WARNING"):
            self.assertTrue(queue.enqueue("fresh"))
        self.assertEqual([item[0] for item in queue._backlog], ["fresh"])
        stage.retire(stage.instances[0].id)
        self.assertEqual(stage.instances[-1].text, "fresh")

    @patch("vocari.tts.tts_queue.time.monotonic", return_value=100.0)
    def test_deadline_survives_move_to_stage_and_prevents_stale_synthesis(self, clock):
        queue, stage = self.make_bounded_queue()
        for i in range(8):
            queue.enqueue(str(i))
        clock.return_value = 219.0
        stage.retire(stage.instances[0].id)
        moved = stage.instances[-1]
        self.assertEqual(moved.text, "7")
        self.assertEqual(moved.queue_deadline, 220.0)
        # Drive real stage promotions/animations; expired speakers must leave
        # rather than synthesizing, including those already visible at admission.
        clock.return_value = 220.0
        with self.assertLogs("vocari.tts.queue", level="WARNING"):
            for _ in range(2000):
                stage.tick()
                if not stage.instances:
                    break
        self.assertFalse(stage.instances)
        queue._start_synthesis.assert_not_called()
        self.assertTrue(queue.enqueue("fresh"))
        for _ in range(200):
            stage.tick()
        queue._start_synthesis.assert_called_once_with(stage.instances[0].id)


if __name__ == "__main__":
    unittest.main()
