"""Standalone log viewer window: terminal-styled (black background), shows
live app log output next to the avatar overlay, color-coded by level. Can be
scrolled, cleared (view + on-disk file), or closed (hidden — the app keeps
running in the tray, reopen from there)."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QCloseEvent, QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from vocari.logging_setup import log_bridge

MAX_VISIBLE_LINES = 5000

LEVEL_COLORS = {
    "DEBUG": QColor("#9a9a9a"),
    "INFO": QColor("#ffffff"),
    "WARNING": QColor("#e6c229"),
    "ERROR": QColor("#ff5c5c"),
    "CRITICAL": QColor("#ff5c5c"),
}
DEFAULT_COLOR = QColor("#ffffff")
LEVEL_IN_LINE_RE = re.compile(r"\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]")


class LogWindow(QWidget):
    def __init__(self, log_file: Path):
        super().__init__()
        self.log_file = log_file
        self.setWindowTitle("Vocari — лог")
        self.resize(640, 420)
        self.setStyleSheet("background-color:#0c0c0c;")

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(MAX_VISIBLE_LINES)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setStyleSheet(
            "QPlainTextEdit { background-color:#0c0c0c; color:#ffffff; border:1px solid #2a2a2a; }"
        )

        button_style = (
            "QPushButton { background-color:#1e1e1e; color:#dddddd; border:1px solid #333; "
            "padding:4px 12px; } QPushButton:hover { background-color:#2a2a2a; }"
        )
        clear_button = QPushButton("Очистить")
        clear_button.setStyleSheet(button_style)
        clear_button.clicked.connect(self._clear)
        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet(button_style)
        close_button.clicked.connect(self.hide)

        buttons = QHBoxLayout()
        buttons.addWidget(clear_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout.addLayout(buttons)

        log_bridge.message_logged.connect(self._append)
        self._load_existing()

    def _load_existing(self) -> None:
        try:
            existing = self.log_file.read_text(encoding="utf-8")
        except OSError:
            return
        for line in existing.splitlines():
            match = LEVEL_IN_LINE_RE.search(line)
            level = match.group(1) if match else "INFO"
            self._append(level, line)

    def _append(self, level: str, line: str) -> None:
        color = LEVEL_COLORS.get(level, DEFAULT_COLOR)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(color)
        cursor.setCharFormat(char_format)
        cursor.insertText(line + "\n")
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def _clear(self) -> None:
        self.text_edit.clear()
        try:
            self.log_file.write_text("", encoding="utf-8")
        except OSError:
            pass

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Closing via the title bar X should just hide it, same as the
        # "Закрыть" button — the app keeps running in the tray.
        event.ignore()
        self.hide()
