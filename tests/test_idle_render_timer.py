import unittest

from PySide6.QtWidgets import QApplication

from vocari.config.settings import BubbleConfig, OverlayConfig, RenderConfig
from vocari.rendering.model import AvatarModel
from vocari.rendering.overlay_window import OverlayWindow


class IdleRenderTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(
            ["idle-render-test", "-platform", "offscreen"]
        )

    def setUp(self):
        model = AvatarModel("Test", (100, 100), [], {}, directory=None)
        self.window = OverlayWindow(
            model,
            OverlayConfig(scale=1.0),
            RenderConfig(),
            BubbleConfig(enabled=False),
        )

    def tearDown(self):
        self.window.close()

    def finish_all_exits(self):
        for _ in range(1000):
            self.window._on_animation_tick()
            if not self.window.stage.instances:
                break
        self.assertFalse(self.window.stage.instances)

    def test_timer_stays_off_while_stage_is_empty(self):
        self.assertFalse(self.window._anim_timer.isActive())
        clock = self.window._clock_s
        self.window._on_animation_tick()
        self.assertFalse(self.window._anim_timer.isActive())
        self.assertEqual(self.window._clock_s, clock)

    def test_speaker_starts_timer_and_last_exit_stops_it(self):
        instance = self.window.add_speaker("hello", "viewer")
        self.assertIsNotNone(instance)
        self.assertTrue(self.window._anim_timer.isActive())

        self.window.retire_speaker(instance.id)
        self.finish_all_exits()
        self.assertFalse(self.window._anim_timer.isActive())

        self.assertIsNotNone(self.window.add_speaker("again", "viewer"))
        self.assertTrue(self.window._anim_timer.isActive())

    def test_preview_starts_timer_and_stops_after_hiding(self):
        self.window.show_bubble_preview("preview", "viewer")
        self.assertTrue(self.window._anim_timer.isActive())

        self.window.hide_bubble_preview()
        self.finish_all_exits()
        self.assertFalse(self.window._anim_timer.isActive())


if __name__ == "__main__":
    unittest.main()
