"""Settings → "Тест": speak arbitrary text without needing the Twitch chat
connected — goes through the same TTSQueue (and stage jump-in/out) as real
chat messages, so this is also how you preview that animation."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.tts.service import enforce_length_limit
from vocari.tts.tts_queue import TTSQueue

logger = get_logger("tts.test_tab")


class TestTab(QWidget):
    def __init__(self, config: AppConfig, tts_queue: TTSQueue):
        super().__init__()
        self.config = config
        self.tts_queue = tts_queue

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Введите текст и нажмите «Озвучить», чтобы проверить TTS без чата:"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Привет, чат!")
        self.text_edit.setMaximumHeight(80)
        layout.addWidget(self.text_edit)

        self.speak_button = QPushButton("Озвучить")
        self.speak_button.clicked.connect(self._on_speak_clicked)
        layout.addWidget(self.speak_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        hint = QLabel(
            "Идёт через ту же очередь, что и сообщения из Twitch-чата — "
            "аватар выедет, скажет фразу и уедет обратно, как и в чате."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()

    def _on_speak_clicked(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return

        text, truncated = enforce_length_limit(text, self.config.tts)
        self.status_label.setStyleSheet("color:#2ecc71;")
        message = "Добавлено в очередь."
        if truncated:
            message += f" Текст обрезан до {self.config.tts.max_chars} символов."
        self.status_label.setText(message)
        logger.info("Тест TTS: '%s'", text)

        self.tts_queue.enqueue(text)
