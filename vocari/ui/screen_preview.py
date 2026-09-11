"""Settings -> "Модель": a scaled-down mock of the user's actual screen,
showing where the avatar's speaking box will land and which side the queue
enters/exits from — drag the box to reposition instead of guessing raw pixel
coordinates in the X/Y spin boxes."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QApplication, QWidget

from vocari.config.settings import AppConfig
from vocari.rendering.model import AvatarModel

PREVIEW_HEIGHT = 160
BOX_COLOR = QColor("#2ecc71")
BOX_FILL = QColor(46, 204, 113, 70)
ARROW_COLOR = QColor("#e6c229")


class ScreenPreviewWidget(QWidget):
    def __init__(self, config: AppConfig, model: AvatarModel, on_position_changed: Callable[[int, int], None]):
        super().__init__()
        self.config = config
        self.model = model
        self.on_position_changed = on_position_changed
        self.setMinimumHeight(PREVIEW_HEIGHT)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_offset: QPointF | None = None

        screen = QApplication.primaryScreen()
        self.screen_size = screen.availableGeometry().size() if screen is not None else QSize(1920, 1080)

    def set_model(self, model: AvatarModel) -> None:
        """Called after a model import (see ModelTab), so the box reflects
        the new model's canvas size instead of the one it was built with."""
        self.model = model
        self.update()

    # -- geometry: screen pixels <-> widget-local preview pixels ----------

    def _preview_rect(self) -> QRectF:
        """The black-screen mock itself, letterboxed to the real screen's
        aspect ratio inside this widget's current size."""
        margin = 4
        available_w = max(1, self.width() - 2 * margin)
        available_h = max(1, self.height() - 2 * margin)
        screen_aspect = self.screen_size.width() / max(1, self.screen_size.height())
        if available_w / available_h > screen_aspect:
            height = available_h
            width = height * screen_aspect
        else:
            width = available_w
            height = width / screen_aspect
        x = (self.width() - width) / 2
        y = (self.height() - height) / 2
        return QRectF(x, y, width, height)

    def _preview_scale(self, preview_rect: QRectF) -> float:
        return preview_rect.width() / max(1, self.screen_size.width())

    def _box_rect(self, preview_rect: QRectF) -> QRectF:
        k = self._preview_scale(preview_rect)
        canvas_w, canvas_h = self.model.canvas_size
        box_w = canvas_w * self.config.overlay.scale * k
        box_h = canvas_h * self.config.overlay.scale * k
        box_x = preview_rect.left() + self.config.overlay.pos_x * k
        box_y = preview_rect.top() + self.config.overlay.pos_y * k
        return QRectF(box_x, box_y, box_w, box_h)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            preview_rect = self._preview_rect()

            painter.fillRect(preview_rect, QColor("black"))
            painter.setPen(QPen(QColor("#555"), 1))
            painter.drawRect(preview_rect)

            box_rect = self._box_rect(preview_rect)
            painter.setPen(QPen(BOX_COLOR, 2))
            painter.setBrush(QBrush(BOX_FILL))
            painter.drawRect(box_rect)

            # Small arrow at the box's entrance/exit side, so the toggle
            # right next to this preview has an immediate visual anchor.
            from_right = self.config.render.entrance_from_right
            arrow_y = box_rect.center().y()
            painter.setPen(QPen(ARROW_COLOR, 3))
            if from_right:
                x0, x1 = box_rect.right(), min(preview_rect.right(), box_rect.right() + 24)
            else:
                x0, x1 = box_rect.left(), max(preview_rect.left(), box_rect.left() - 24)
            painter.drawLine(QPointF(x0, arrow_y), QPointF(x1, arrow_y))
        finally:
            painter.end()

    # -- drag to reposition ---------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        box_rect = self._box_rect(self._preview_rect())
        if box_rect.contains(event.position()):
            self._drag_offset = event.position() - box_rect.topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is None:
            return
        preview_rect = self._preview_rect()
        k = self._preview_scale(preview_rect)
        if k <= 0:
            return
        top_left = event.position() - self._drag_offset
        screen_x = round((top_left.x() - preview_rect.left()) / k)
        screen_y = round((top_left.y() - preview_rect.top()) / k)
        self.config.overlay.pos_x = screen_x
        self.config.overlay.pos_y = screen_y
        self.on_position_changed(screen_x, screen_y)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()
