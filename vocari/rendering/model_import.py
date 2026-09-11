"""Auto-import an avatar model from an arbitrary folder of PNG layers.

Point this at a folder and it scans filenames for keywords to guess eyes/mouth
open/closed pairs automatically; every other PNG becomes a static base layer.
This is deliberately simpler than a full manual-mapping wizard: if a model's
state pair can't be confidently detected, its files fall back to being static
layers (with a warning) rather than risk pairing the wrong files together.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QImageReader

STATE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "eyes": ("eye", "глаз"),
    "mouth": ("mouth", "рот"),
}
OPEN_KEYWORDS = ("open", "откр")
CLOSED_KEYWORDS = ("closed", "close", "закр")


@dataclass
class ImportResult:
    model_name: str
    target_dir: Path
    base_layer_count: int
    detected_states: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    text = text.lower()
    return any(keyword in text for keyword in keywords)


def _read_size(path: Path) -> tuple[int, int]:
    reader = QImageReader(str(path))
    size = reader.size()
    if not size.isValid():
        raise ValueError(f"Не удалось прочитать изображение: {path.name}")
    return size.width(), size.height()


def import_model_from_folder(source_dir: Path, models_root: Path) -> ImportResult:
    source_dir = Path(source_dir)
    png_files = sorted(p.name for p in source_dir.glob("*.png"))
    if not png_files:
        raise ValueError("В выбранной папке нет PNG-файлов")

    warnings: list[str] = []

    grouped: dict[str, list[str]] = {key: [] for key in STATE_KEYWORDS}
    static_files: list[str] = []
    for filename in png_files:
        matched_key = next(
            (key for key, keywords in STATE_KEYWORDS.items() if _contains_any(filename, keywords)),
            None,
        )
        (grouped[matched_key] if matched_key else static_files).append(filename)

    states: dict[str, dict[str, str]] = {}
    for key, files in grouped.items():
        if not files:
            continue
        open_files = [f for f in files if _contains_any(f, OPEN_KEYWORDS)]
        closed_files = [f for f in files if _contains_any(f, CLOSED_KEYWORDS)]
        if len(open_files) == 1 and len(closed_files) == 1:
            states[key] = {"open": open_files[0], "closed": closed_files[0]}
        else:
            warnings.append(
                f"Не удалось однозначно определить open/closed для группы "
                f"'{key}' ({len(files)} подходящих файлов) — добавлены как статичные слои."
            )
            static_files.extend(files)

    base_layers = [f for f in png_files if f in static_files]

    # Canvas size + a sanity check that every layer shares it (the app alpha-
    # blends layers with no per-layer offset, so a mismatched layer would
    # visibly not line up).
    sizes = {filename: _read_size(source_dir / filename) for filename in png_files}
    canvas_size = sizes[png_files[0]]
    mismatched = [name for name, size in sizes.items() if size != canvas_size]
    if mismatched:
        warnings.append(
            f"Размер холста у {len(mismatched)} слоёв отличается от {canvas_size[0]}x{canvas_size[1]} "
            f"— они могут не совпасть по позиции: {', '.join(mismatched[:5])}"
            + ("…" if len(mismatched) > 5 else "")
        )

    manifest_states: dict[str, dict] = {}
    for key, frames in states.items():
        order = sum(1 for f in base_layers if f < frames["open"])
        manifest_states[key] = {"order": order, **frames}

    model_name = source_dir.name
    target_dir = models_root / model_name
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in png_files:
        shutil.copy2(source_dir / filename, target_dir / filename)

    manifest = {
        "name": model_name,
        "canvas": list(canvas_size),
        "base_layers": base_layers,
        "states": manifest_states,
    }
    (target_dir / "model.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return ImportResult(
        model_name=model_name,
        target_dir=target_dir,
        base_layer_count=len(base_layers),
        detected_states=list(states.keys()),
        warnings=warnings,
    )
