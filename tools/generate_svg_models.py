"""Renders the bundled avatar models from the art modules in tools/art/.

Each model module exports:
  LAYERS    filename -> callable returning either a tools.art.svgkit.Layer
            (rasterized through headless Chromium - see orc.py, ranger.py)
            or a QImage already at the shared canvas size (the pixel-art
            route - see coder_pixel.py, tools/art/pixel.py)
  MANIFEST  the model.json payload (canvas is added here, fixed for all models)

Run:  .venv\\Scripts\\python.exe tools\\generate_svg_models.py [name ...]
      (no names = render every registered model)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from tools.art.svgkit import CANVAS, Renderer

OUT_ROOT = Path(__file__).resolve().parent.parent / "assets" / "models"

MODELS: dict[str, str] = {
    "Orc": "tools.art.orc",
    "Ranger": "tools.art.ranger",
    "Coder": "tools.art.coder_pixel",
}


def build(name: str, module_path: str, renderer: Renderer) -> None:
    import importlib

    module = importlib.import_module(module_path)
    folder = OUT_ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    for existing in folder.glob("*.png"):
        existing.unlink()

    for filename, factory in module.LAYERS.items():
        result = factory()
        if isinstance(result, QImage):
            (folder / filename).parent.mkdir(parents=True, exist_ok=True)
            result.save(str(folder / filename))
        else:
            renderer.render(result, folder / filename)

    manifest = dict(module.MANIFEST)
    manifest["canvas"] = [CANVAS, CANVAS]
    (folder / "model.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{name}: {len(module.LAYERS)} layers -> {folder}")


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 - QPixmap/QImage need an app instance
    requested = sys.argv[1:] or list(MODELS.keys())
    renderer = Renderer()
    try:
        for name in requested:
            build(name, MODELS[name], renderer)
    finally:
        renderer.cleanup()


if __name__ == "__main__":
    main()
