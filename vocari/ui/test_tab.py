"""Settings → "Тест": speak arbitrary text without needing the Twitch chat
connected — the manual TTS check required by Stage 3."""
from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.tts.registry import get_active_provider
from vocari.tts.service import enforce_length_limit, pick_voice
from vocari.tts.synthesis_worker import SynthesisWorker

logger = get_logger("tts.test_tab")


class TestTab(QWidget):
    def __init__(self, config: AppConfig, providers: dict[str, TTSProvider], audio_player: AudioPlayer):
        super().__init__()
        self.config = config
        self.providers = providers
        self.audio_player = audio_player
        self._thread: QThread | None = None
        self._worker: SynthesisWorker | None = None

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
        layout.addStretch()

    def _on_speak_clicked(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return

        text, truncated = enforce_length_limit(text, self.config.tts)
        voice, lang = pick_voice(text, self.config.tts)
        rate = f"{self.config.tts.rate_percent:+d}%"
        provider = get_active_provider(self.config.tts, self.providers)

        self.speak_button.setEnabled(False)
        self.status_label.setStyleSheet("color: gray;")
        message = f"Синтез… ({self.config.tts.provider}, голос {voice})"
        if truncated:
            message += f" — текст обрезан до {self.config.tts.max_chars} символов"
        self.status_label.setText(message)
        logger.info("Тест TTS: '%s' provider=%s voice=%s lang=%s", text, self.config.tts.provider, voice, lang)

        self._thread = QThread(self)
        self._worker = SynthesisWorker(provider, text, voice, lang, rate)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_synthesis_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_synthesis_finished(self, audio: bytes, error: str) -> None:
        self.speak_button.setEnabled(True)
        if error:
            logger.error("Синтез TTS не удался: %s", error)
            self.status_label.setStyleSheet("color:#ff5c5c;")
            self.status_label.setText(f"Ошибка: {error}")
            return

        logger.info("TTS: синтез готов (%d байт), запускаю воспроизведение", len(audio))
        self.status_label.setStyleSheet("color:#2ecc71;")
        self.status_label.setText("Воспроизведение…")

        volume_gain = max(0.0, 1.0 + self.config.tts.volume_percent / 100.0)
        self.audio_player.play(audio, volume_gain, self._on_playback_finished)

    def _on_playback_finished(self) -> None:
        self.status_label.setText("Готово.")
