"""Small reusable widgets shared across settings screens."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence, QPainter
from PySide6.QtWidgets import QAbstractButton, QPushButton, QWidget

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


# Modifier-only key presses (e.g. just tapping Ctrl by itself) don't count as
# a finished chord — wait for a real key on top of them instead.
_MODIFIER_ONLY_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
}


class HotkeyCaptureButton(QPushButton):
    """A button that, when clicked, listens for the next key chord pressed
    anywhere while it has focus and reports it as a QKeySequence string
    (e.g. "F9", "Ctrl+Alt+S") via on_captured — used to let the user bind
    the global skip hotkey by just pressing it, instead of typing a key name."""

    def __init__(self, initial_sequence: str, on_captured: Callable[[str], None], parent: QWidget | None = None):
        super().__init__(parent)
        self.on_captured = on_captured
        self._listening = False
        self._current_sequence = initial_sequence
        self.set_sequence(initial_sequence)
        self.clicked.connect(self._start_listening)

    def set_sequence(self, sequence_text: str) -> None:
        self._current_sequence = sequence_text
        self.setText(sequence_text if sequence_text else "Не задан — нажмите, чтобы записать")

    def _start_listening(self) -> None:
        self._listening = True
        self.setText("Нажмите любую клавишу…")
        self.grabKeyboard()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._listening:
            super().keyPressEvent(event)
            return
        if event.key() in _MODIFIER_ONLY_KEYS:
            return  # wait for the actual key that comes with this modifier
        if event.key() == Qt.Key.Key_Escape and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            # Escape with no modifier cancels instead of binding itself —
            # it's also how the overlay window hides itself (see keyPressEvent
            # in overlay_window.py), so binding it here would be surprising.
            self._stop_listening()
            self.set_sequence(self._current_sequence)
            return

        combination = QKeySequence(event.keyCombination()).toString()
        self._stop_listening()
        self.set_sequence(combination)
        self.on_captured(combination)

    def _stop_listening(self) -> None:
        self._listening = False
        self.releaseKeyboard()
