import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from vocari.config.settings import BubbleConfig, OverlayConfig, RenderConfig
from vocari.rendering.model import AvatarModel
from vocari.rendering.overlay_window import MAX_CACHED_MODEL_PACKS, ModelPack, OverlayWindow


def model(name: str) -> AvatarModel:
    return AvatarModel(name, (100, 100), [], {}, directory=None)


def pack(value: AvatarModel):
    return SimpleNamespace(
        model=value, pixmaps={}, z_order=[], sway_phase={}, sway_pivot={},
        sway_spec={}, bounce_pivot={}, effect_spec={}, effect_origin={},
    )


class ModelPackCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["model-cache-test", "-platform", "offscreen"])

    def make_window(self, names=("A", "B", "C", "D", "E")):
        models = [model(name) for name in names]
        built = []

        def build(value):
            built.append(value.name)
            return pack(value)

        patcher = patch.object(ModelPack, "build", side_effect=build)
        patcher.start()
        self.addCleanup(patcher.stop)
        window = OverlayWindow(models[0], OverlayConfig(scale=1.0), RenderConfig(), BubbleConfig(enabled=False))
        self.addCleanup(window.close)
        window._anim_timer.stop()
        window.set_available_models(models)
        return window, built

    def test_registering_manifests_decodes_only_active_model(self):
        window, built = self.make_window()
        self.assertEqual(built, ["A"])
        self.assertEqual(set(window._models), {"A", "B", "C", "D", "E"})
        self.assertEqual(set(window._packs), {"A"})

    def test_first_appearance_loads_once_and_binding_uses_unloaded_model(self):
        window, built = self.make_window()
        window.set_user_model_bindings({"viewer": "B"})
        instance = window.add_speaker("hello", "Viewer")
        self.assertEqual(instance.model_name, "B")
        self.assertEqual(built, ["A", "B"])
        window._pack_for(instance)
        self.assertEqual(built, ["A", "B"])

    def test_lru_evicts_only_models_that_are_not_active_or_visible(self):
        window, built = self.make_window()
        visible = window.add_speaker("hello", "")
        visible.model_name = "B"
        window._ensure_pack("B")
        window._ensure_pack("C")
        window._ensure_pack("D")
        window._evict_unused_packs()
        self.assertLessEqual(len(window._packs), max(MAX_CACHED_MODEL_PACKS, 2))
        self.assertIn("A", window._packs)  # active model
        self.assertIn("B", window._packs)  # visible model
        self.assertIn("D", window._packs)  # most recently used inactive model
        self.assertNotIn("C", window._packs)

        window.stage.instances.clear()
        window._ensure_pack("E")
        window._evict_unused_packs()
        self.assertEqual(len(window._packs), MAX_CACHED_MODEL_PACKS)
        self.assertIn("A", window._packs)
        self.assertIn("E", window._packs)

    def test_deleted_model_cannot_be_selected_again(self):
        window, _built = self.make_window()
        window.set_user_model_bindings({"viewer": "B"})
        window.remove_available_model("B")
        self.assertEqual(window._pick_model_name("viewer"), "A")
        self.assertNotIn("B", window._models)

    def test_deleted_visible_model_keeps_pack_only_until_instance_leaves(self):
        window, _built = self.make_window()
        window.set_user_model_bindings({"viewer": "B"})
        instance = window.add_speaker("hello", "viewer")
        old_pack = window._packs["B"]
        window.remove_available_model("B")
        self.assertIs(window._pack_for(instance), old_pack)
        window._evict_unused_packs()
        self.assertIn("B", window._packs)
        window.stage.instances.clear()
        window._evict_unused_packs()
        self.assertNotIn("B", window._packs)


if __name__ == "__main__":
    unittest.main()
