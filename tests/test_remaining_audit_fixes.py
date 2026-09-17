import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vocari.config.settings import AppConfig, BubbleConfig, OverlayConfig, RenderConfig
from vocari.rendering.model import AvatarModel
from vocari.rendering.overlay_window import OverlayWindow
from vocari.tts.silero_provider import recommended_torch_threads
from vocari.ui.bindings_tab import BindingsTab, MAX_KNOWN_NICKS
from vocari.ui.model_tab import ModelTab
from vocari.ui.widgets import CheckableModelCombo, ToggleSwitch


def model(name: str) -> AvatarModel:
    return AvatarModel(name, (100, 100), [], {}, directory=None)


class RemainingAuditFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(
            ["audit-fixes-test", "-platform", "offscreen"]
        )

    def test_hidden_nick_discovery_is_bounded_and_debounced(self):
        config = AppConfig()
        config.save = Mock()
        with patch("vocari.ui.bindings_tab._model_names", return_value=[]):
            tab = BindingsTab(config, Mock(), Mock())
        self.addCleanup(tab.close)

        for index in range(MAX_KNOWN_NICKS + 25):
            tab.observe_nick(f"viewer{index}")

        self.assertEqual(len(config.overlay.known_nicks), MAX_KNOWN_NICKS)
        self.assertEqual(len(tab._nick_rows), 0)
        self.assertEqual(config.save.call_count, 0)
        self.assertTrue(tab._nick_save_timer.isActive())
        QTest.qWait(1100)
        self.assertEqual(config.save.call_count, 1)

    def test_nick_limit_preserves_explicit_bindings(self):
        config = AppConfig()
        config.overlay.known_nicks = [f"viewer{i}" for i in range(MAX_KNOWN_NICKS)]
        config.overlay.user_model_bindings = {"viewer0": "A"}
        config.save = Mock()
        with patch("vocari.ui.bindings_tab._model_names", return_value=["A"]):
            tab = BindingsTab(config, Mock(), Mock())
        self.addCleanup(tab.close)

        tab.observe_nick("new-viewer")
        self.assertIn("viewer0", [nick.lower() for nick in config.overlay.known_nicks])
        self.assertIn("new-viewer", config.overlay.known_nicks)
        self.assertEqual(len(config.overlay.known_nicks), MAX_KNOWN_NICKS)

    def test_empty_pool_and_zero_weights_use_active_model(self):
        window = OverlayWindow(
            model("A"), OverlayConfig(scale=1.0), RenderConfig(), BubbleConfig(enabled=False)
        )
        self.addCleanup(window.close)
        window.set_available_models([model("A"), model("B"), model("C")])
        window.set_random_model(True)

        window.set_random_pool([])
        self.assertEqual(window._pick_model_name(""), "A")

        window.set_random_pool(["B", "C"])
        window.set_model_weights({"B": 0.0, "C": 0.0})
        self.assertEqual(window._pick_model_name(""), "A")

    def test_empty_checked_names_remains_empty(self):
        combo = CheckableModelCombo()
        self.addCleanup(combo.close)
        combo.add_item("A", "a", True)
        combo.add_item("B", "b", True)
        combo.set_checked_names([])
        self.assertEqual(combo.checked_names(), [])

    def test_old_random_pool_is_migrated_once_and_explicit_empty_persists(self):
        config = AppConfig()
        config.save = Mock()
        pool_changed = Mock()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("A", "B"):
                folder = root / name
                folder.mkdir()
                (folder / "model.json").write_text("{}", encoding="utf-8")
            with patch("vocari.ui.model_tab.MODELS_ROOT", root):
                tab = ModelTab(
                    config, model("A"), Mock(), Mock(), Mock(), Mock(), Mock(),
                    Mock(), Mock(), pool_changed, Mock(),
                )
                self.addCleanup(tab.close)
                self.assertEqual(config.overlay.random_pool, ["A", "B"])
                self.assertTrue(config.overlay.random_pool_initialized)

                tab.model_combo.set_checked_names([])
                tab._on_pool_check_toggled()
                self.assertEqual(config.overlay.random_pool, [])

                second = ModelTab(
                    config, model("A"), Mock(), Mock(), Mock(), Mock(), Mock(),
                    Mock(), Mock(), pool_changed, Mock(),
                )
                self.addCleanup(second.close)
                self.assertEqual(second.model_combo.checked_names(), [])

    def test_silero_thread_budget_leaves_capacity_for_streaming(self):
        self.assertEqual(recommended_torch_threads(1), 1)
        self.assertEqual(recommended_torch_threads(2), 1)
        self.assertEqual(recommended_torch_threads(8), 4)
        self.assertEqual(recommended_torch_threads(64), 4)

    def test_toggle_has_accessible_name_and_keyboard_controls(self):
        toggle = ToggleSwitch("Тестовый переключатель")
        self.addCleanup(toggle.close)
        self.assertEqual(toggle.accessibleName(), "Тестовый переключатель")
        self.assertEqual(toggle.focusPolicy(), Qt.FocusPolicy.StrongFocus)

        QTest.keyClick(toggle, Qt.Key.Key_Return)
        self.assertTrue(toggle.isChecked())
        QTest.keyClick(toggle, Qt.Key.Key_Space)
        self.assertFalse(toggle.isChecked())


if __name__ == "__main__":
    unittest.main()
