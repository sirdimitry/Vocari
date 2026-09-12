"""Pixel-art authoring toolkit: a small, hard-edged grid canvas upscaled with
nearest-neighbor to the model's shared 1280x1280 canvas, instead of the SVG
route the other three avatars use (see tools/art/svgkit.py). Used for the
Coder avatar, which is meant to closely match a specific reference photo -
a low-res grid authored by hand-placed rectangles/runs is a more direct way
to hit a particular likeness than parametric shapes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

CANVAS = 1280


class PixelCanvas:
    """A GRID x GRID image, drawn with antialiasing off so every edge lands on
    a whole pixel, then scaled up by nearest-neighbor (export()) so those
    pixels stay crisp blocks instead of blurring into gradients."""

    def __init__(self, grid: int):
        self.grid = grid
        self.image = QImage(grid, grid, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.transparent)
        self.painter = QPainter(self.image)
        self.painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.painter.setPen(Qt.PenStyle.NoPen)

    def px(self, x: int, y: int, color: str, alpha: float = 1.0) -> None:
        """Sets one grid cell."""
        c = QColor(color)
        if alpha < 1.0:
            c.setAlphaF(alpha)
        self.painter.fillRect(x, y, 1, 1, c)

    def rect(self, x: int, y: int, w: int, h: int, color: str, alpha: float = 1.0) -> None:
        c = QColor(color)
        if alpha < 1.0:
            c.setAlphaF(alpha)
        self.painter.fillRect(x, y, w, h, c)

    def row(self, y: int, x0: int, x1: int, color: str, alpha: float = 1.0) -> None:
        """Fills grid cells x0..x1 inclusive on row y - the main building
        block for hand-authoring a silhouette scanline by scanline."""
        self.rect(x0, y, x1 - x0 + 1, 1, color, alpha)

    def col(self, x: int, y0: int, y1: int, color: str, alpha: float = 1.0) -> None:
        self.rect(x, y0, 1, y1 - y0 + 1, color, alpha)

    def hspan(self, y: int, spans: list[tuple[int, int, str]], alpha: float = 1.0) -> None:
        """Several colored runs on one row: [(x0, x1, color), ...]."""
        for x0, x1, color in spans:
            self.row(y, x0, x1, color, alpha)

    def mirror_onto(self, other: "PixelCanvas", axis_x: int) -> None:
        """Copies this canvas onto `other`, mirrored left-right about column
        axis_x (used so a hand-authored left ear/eye can be reused as the
        right one without redrawing it)."""
        src = self.image
        for y in range(self.grid):
            for x in range(self.grid):
                color = src.pixelColor(x, y)
                if color.alpha() == 0:
                    continue
                mx = 2 * axis_x - x
                if 0 <= mx < other.grid:
                    other.image.setPixelColor(mx, y, color)

    def paste(self, other: "PixelCanvas", dx: int = 0, dy: int = 0) -> None:
        self.painter.drawImage(dx, dy, other.image)

    def finish(self) -> None:
        self.painter.end()

    def export(self) -> QImage:
        """Upscales to the model's shared canvas size with nearest-neighbor
        (FastTransformation), so pixels stay hard blocks, not smoothed."""
        if self.painter.isActive():
            self.painter.end()
        scale = CANVAS // self.grid
        assert scale * self.grid == CANVAS, "grid must evenly divide the shared canvas size"
        return self.image.scaled(
            CANVAS, CANVAS,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
