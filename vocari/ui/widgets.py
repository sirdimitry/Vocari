"""Small reusable widgets shared across settings screens."""
from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget

_OFF_COLOR = QColor("#b7b7c0")
_ON_COLOR = QColor("#6c5ce7")


class ToggleSwitch(QAbstractButton):
    """A small animated on/off toggle switch (the "тумблер" for settings)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

        self._knob_position = 0.0
        self._animation = QPropertyAnimation(self, b"knob_position", self)
        self._animation.setDuration(120)
        self.toggled.connect(self._animate_to)

    def _animate_to(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def _get_knob_position(self) -> float:
        return self._knob_position

    def _set_knob_position(self, value: float) -> None:
        self._knob_position = value
        self.update()

    knob_position = Property(float, _get_knob_position, _set_knob_position)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        mix = self._knob_position
        track_color = QColor(
            round(_OFF_COLOR.red() + (_ON_COLOR.red() - _OFF_COLOR.red()) * mix),
            round(_OFF_COLOR.green() + (_ON_COLOR.green() - _OFF_COLOR.green()) * mix),
            round(_OFF_COLOR.blue() + (_ON_COLOR.blue() - _OFF_COLOR.blue()) * mix),
        )
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), self.height() / 2, self.height() / 2)

        knob_diameter = self.height() - 4
        knob_x = 2 + mix * (self.width() - knob_diameter - 4)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(knob_x, 2, knob_diameter, knob_diameter))
