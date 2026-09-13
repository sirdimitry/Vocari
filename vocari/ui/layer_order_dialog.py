"""Settings -> Модель -> "Порядок слоёв...": a drag-to-reorder editor for a
model's z-order, with a large black-background preview that spotlights
whichever layer is selected in the list.

Only base_layers order and each state group's "order" index are touched on
save — every other manifest field (sway_layers, effect_layers,
bounce_react_layers, gaze_layer, canvas, name...) is read and re-written
byte-for-byte from the existing model.json, since reordering z-order has
nothing to do with those (they reference layers by filename, not position).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocari.rendering.model import AvatarModel

_STATE_LABELS = {
    "eyes": "\U0001F441 Глаза (откр./закр.)",
    "mouth": "\U0001F444 Рот (откр./закр.)",
}
_LEADING_NUMBER = re.compile(r"^(\d+)")
_GLOW_COLOR = QColor(94, 230, 255, 255)  # bright cyan — pops against any art/skin colour on black
_DIM_OPACITY = 0.4  # everything but the selected layer, once something is selected


def _leading_number(filename: str) -> int:
    match = _LEADING_NUMBER.match(filename)
    return int(match.group(1)) if match else 9999  # unnumbered files sort last, not first


def _state_label(key: str) -> str:
    return _STATE_LABELS.get(key, f"Состояние: {key}")


def _colorize_silhouette(pixmap: QPixmap, color: QColor) -> QPixmap:
    """The layer's own alpha shape, filled flat with `color` — used to fake a
    glow/outline by stamping this a few pixels off-center in a ring, rather
    than computing a real per-pixel edge (much cheaper, and this only needs
    to run once per selection change, not every frame)."""
    silhouette = QPixmap(pixmap.size())
    silhouette.fill(Qt.GlobalColor.transparent)
    painter = QPainter(silhouette)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(silhouette.rect(), color)
    painter.end()
    return silhouette


class _LayerStackPreview(QWidget):
    """The whole avatar on a black background, scaled to fit and centered.
    When a layer is selected, every other layer dims and the selected one
    gets a soft cyan glow ring traced around its silhouette."""

    def __init__(self, canvas_size: tuple[int, int], parent: QWidget | None = None):
        super().__init__(parent)
        self.canvas_w, self.canvas_h = canvas_size
        self._stack: list[tuple[str, str, QPixmap | None]] = []
        self._selected_key: tuple[str, str] | None = None
        self._glow_cache: dict[int, QPixmap] = {}
        self.setMinimumSize(360, 360)

    def set_stack(self, stack: list[tuple[str, str, QPixmap | None]], selected_key: tuple[str, str] | None) -> None:
        self._stack = stack
        self._selected_key = selected_key
        self._glow_cache.clear()
        self.update()

    def set_selected(self, selected_key: tuple[str, str] | None) -> None:
        self._selected_key = selected_key
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        if not self._stack or not self.canvas_w or not self.canvas_h:
            painter.end()
            return

        scale = min(self.width() / self.canvas_w, self.height() / self.canvas_h)
        draw_w, draw_h = self.canvas_w * scale, self.canvas_h * scale
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate((self.width() - draw_w) / 2, (self.height() - draw_h) / 2)
        painter.scale(scale, scale)

        has_selection = self._selected_key is not None
        for kind, ref, pixmap in self._stack:
            if pixmap is None or pixmap.isNull():
                continue
            if has_selection and (kind, ref) == self._selected_key:
                self._draw_glow(painter, pixmap)
                painter.setOpacity(1.0)
                painter.drawPixmap(0, 0, pixmap)
            else:
                painter.setOpacity(_DIM_OPACITY if has_selection else 1.0)
                painter.drawPixmap(0, 0, pixmap)
        painter.setOpacity(1.0)
        painter.end()

    def _draw_glow(self, painter: QPainter, pixmap: QPixmap) -> None:
        cache_key = id(pixmap)
        silhouette = self._glow_cache.get(cache_key)
        if silhouette is None:
            silhouette = _colorize_silhouette(pixmap, _GLOW_COLOR)
            self._glow_cache[cache_key] = silhouette
        # Two rings (a wide soft one, a tight bright one) read as a glow
        # without needing an actual blur pass.
        for radius, opacity, steps in ((14, 0.22, 14), (7, 0.45, 12)):
            for i in range(steps):
                angle = 2 * math.pi * i / steps
                dx, dy = radius * math.cos(angle), radius * math.sin(angle)
                painter.setOpacity(opacity)
                painter.drawPixmap(round(dx), round(dy), silhouette)


class LayerOrderDialog(QDialog):
    def __init__(self, model: AvatarModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.directory = model.directory
        self.setWindowTitle(f"Порядок слоёв — {model.name}")
        self.resize(1150, 780)

        self._initial_rows = model.build_z_order()
        self._pixmaps = self._load_pixmaps()

        root = QHBoxLayout(self)
        self.preview = _LayerStackPreview(model.canvas_size)
        root.addWidget(self.preview, 3)

        right = QVBoxLayout()
        hint = QLabel(
            "Слои снизу вверх — как в самом низу стопки, так и на сцене "
            "рисуется первым. Перетащите строку мышью, чтобы изменить "
            "порядок; выбранный слой подсвечивается на превью слева."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        right.addWidget(hint)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setMinimumWidth(300)
        right.addWidget(self.list_widget, 1)

        sort_row = QHBoxLayout()
        reset_btn = QPushButton("Как было")
        reset_btn.clicked.connect(self._reset_order)
        sort_row.addWidget(reset_btn)
        number_btn = QPushButton("По номерам")
        number_btn.clicked.connect(self._sort_by_number)
        sort_row.addWidget(number_btn)
        right.addLayout(sort_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

        root.addLayout(right, 2)

        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.model().rowsMoved.connect(self._on_rows_changed)

        self._populate(self._initial_rows)

    # -- data ---------------------------------------------------------------

    def _load_pixmaps(self) -> dict[tuple[str, str], QPixmap]:
        pixmaps: dict[tuple[str, str], QPixmap] = {}
        for kind, ref in self._initial_rows:
            if kind == "layer":
                pixmaps[(kind, ref)] = QPixmap(str(self.model.layer_path(ref)))
            else:
                frame_file = next(iter(self.model.states[ref].frames.values()))
                pixmaps[(kind, ref)] = QPixmap(str(self.model.layer_path(frame_file)))
        return pixmaps

    def _label_for(self, kind: str, ref: str) -> str:
        return Path(ref).stem if kind == "layer" else _state_label(ref)

    def _current_rows(self) -> list[tuple[str, str]]:
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]

    # -- list <-> preview sync ------------------------------------------------

    def _populate(self, rows: list[tuple[str, str]]) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for kind, ref in rows:
            item = QListWidgetItem(self._label_for(kind, ref))
            item.setData(Qt.ItemDataRole.UserRole, (kind, ref))
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._relabel()
        self._refresh_preview()

    def _relabel(self) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            kind, ref = item.data(Qt.ItemDataRole.UserRole)
            item.setText(f"{i + 1}. {self._label_for(kind, ref)}")

    def _refresh_preview(self) -> None:
        rows = self._current_rows()
        stack = [(kind, ref, self._pixmaps.get((kind, ref))) for kind, ref in rows]
        row = self.list_widget.currentRow()
        selected = rows[row] if 0 <= row < len(rows) else None
        self.preview.set_stack(stack, selected)

    def _on_selection_changed(self, row: int) -> None:
        rows = self._current_rows()
        self.preview.set_selected(rows[row] if 0 <= row < len(rows) else None)

    def _on_rows_changed(self, *_args) -> None:
        self._relabel()
        self._refresh_preview()

    # -- actions --------------------------------------------------------------

    def _reset_order(self) -> None:
        self._populate(self._initial_rows)

    def _sort_by_number(self) -> None:
        def key(row: tuple[str, str]) -> int:
            kind, ref = row
            if kind == "layer":
                return _leading_number(ref)
            frame_file = next(iter(self.model.states[ref].frames.values()))
            return _leading_number(frame_file)

        self._populate(sorted(self._current_rows(), key=key))

    def _save(self) -> None:
        rows = self._current_rows()
        manifest_path = self.directory / "model.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw["base_layers"] = [ref for kind, ref in rows if kind == "layer"]

        count = 0
        for kind, ref in rows:
            if kind == "layer":
                count += 1
            elif ref in raw.get("states", {}):
                raw["states"][ref]["order"] = count

        manifest_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        self.accept()
