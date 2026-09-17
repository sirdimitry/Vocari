import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QImage

from vocari.rendering.model_import import import_model_from_folder


class ModelImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.models = self.root / "models"
        self.source = self.root / "incoming" / "Avatar"
        self.source.mkdir(parents=True)
        image = QImage(8, 8, QImage.Format.Format_ARGB32)
        image.fill(0xFF123456)
        self.assertTrue(image.save(str(self.source / "body.png")))

    def snapshot(self, folder):
        return {p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()}

    def test_repeated_import_preserves_original_and_uses_unique_names(self):
        first = import_model_from_folder(self.source, self.models)
        # Represent the user's custom manifest and layer order, which must
        # survive another import from a different model with the same name.
        (first.target_dir / "model.json").write_text('{"custom": true}', encoding="utf-8")
        original = self.snapshot(first.target_dir)
        source = self.snapshot(self.source)
        second = import_model_from_folder(self.source, self.models)
        third = import_model_from_folder(self.source, self.models)
        self.assertEqual(first.model_name, "Avatar")
        self.assertEqual(second.model_name, "Avatar (2)")
        self.assertEqual(third.model_name, "Avatar (3)")
        self.assertTrue(second.warnings)
        self.assertEqual(self.snapshot(first.target_dir), original)
        self.assertEqual(self.snapshot(self.source), source)
        data = json.loads((second.target_dir / "model.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], second.model_name)
        self.assertEqual(data["base_layers"], ["body.png"])

    def test_import_from_installed_folder_does_not_overwrite_itself(self):
        first = import_model_from_folder(self.source, self.models)
        original = self.snapshot(first.target_dir)
        second = import_model_from_folder(first.target_dir, self.models)
        self.assertEqual(second.model_name, "Avatar (2)")
        self.assertEqual(self.snapshot(first.target_dir), original)

    def test_existing_file_is_also_a_name_collision(self):
        self.models.mkdir()
        occupied = self.models / "Avatar"
        occupied.write_bytes(b"keep")
        result = import_model_from_folder(self.source, self.models)
        self.assertEqual(result.model_name, "Avatar (2)")
        self.assertEqual(occupied.read_bytes(), b"keep")

    def test_failed_copy_removes_partial_import_and_preserves_existing_model(self):
        first = import_model_from_folder(self.source, self.models)
        original = self.snapshot(self.models)

        def fail_copy(source, destination):
            destination.write_bytes(b"partial")
            raise OSError("Simulated disk failure")

        with patch("vocari.rendering.model_import.shutil.copy2", side_effect=fail_copy):
            with self.assertRaises(OSError):
                import_model_from_folder(self.source, self.models)
        self.assertEqual(self.snapshot(self.models), original)
        self.assertEqual(list(self.models.iterdir()), [first.target_dir])


if __name__ == "__main__":
    unittest.main()
