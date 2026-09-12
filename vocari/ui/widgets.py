"""Small reusable widgets shared across settings screens."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Property, QEvent, QObject, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractButton, QComboBox, QPushButton, QWidget

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


class CheckableModelCombo(QComboBox):
    """A QComboBox whose dropdown items each carry their own checkbox
    alongside the combo's normal single "current item" selection — two
    independent choices sharing one list instead of needing a second list
    (of checkboxes) that has to scale on its own once there are many items.

    Clicking near the left edge of a row (where the checkbox draws) toggles
    that item's checked state and keeps the dropdown open, without changing
    which item is "current". Clicking anywhere else on the row selects it as
    current and closes the dropdown — an ordinary QComboBox click, unaffected
    by the checkbox."""

    checked_changed = Signal()
    _CHECKBOX_ZONE_PX = 26  # left-edge width treated as "the checkbox", by feel rather than exact style metrics

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._store = QStandardItemModel(self)
        self.setModel(self._store)
        self._skip_next_hide = False
        self.view().viewport().installEventFilter(self)

    def add_item(self, name: str, data, checked: bool) -> None:
        item = QStandardItem(name)
        item.setData(data, Qt.ItemDataRole.UserRole)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._store.appendRow(item)

    def checked_names(self) -> list[str]:
        return [
            self._store.item(i).text()
            for i in range(self._store.rowCount())
            if self._store.item(i).checkState() == Qt.CheckState.Checked
        ]

    def set_checked_names(self, names: list[str]) -> None:
        """Checks exactly the given names (by item text); empty means "check
        everything" — matching OverlayConfig.random_pool's own empty-means-
        everyone-eligible convention, so the boxes shown here always agree
        with what the app will actually do."""
        pool = set(names)
        for i in range(self._store.rowCount()):
            item = self._store.item(i)
            checked = not names or item.text() in pool
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def eventFilter(self, obj: QObject, event) -> bool:  # noqa: N802
        if obj is self.view().viewport() and event.type() == QEvent.Type.MouseButtonPress:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                rect = self.view().visualRect(index)
                if event.pos().x() - rect.left() <= self._CHECKBOX_ZONE_PX:
                    item = self._store.itemFromIndex(index)
                    item.setCheckState(
                        Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )
                    self.checked_changed.emit()
                    self._skip_next_hide = True
                    return True  # swallow: no selection change, dropdown stays open
        return super().eventFilter(obj, event)

    def hidePopup(self) -> None:  # noqa: N802
        # A checkbox click above already fully handled itself (and returned
        # True to the event filter, so the view never saw a selectable
        # click) — this guards against any other path still trying to close
        # the popup right after, so checking several items in a row doesn't
        # require reopening the dropdown each time.
        if self._skip_next_hide:
            self._skip_next_hide = False
            return
        super().hidePopup()


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
