"""Settings -> "Silero": preload the local/offline TTS models ahead of time
so the first real message doesn't pay the download+warm-up cost. Loading
and inference run on a background QThread — both are blocking calls."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vocari.logging_setup import get_logger
from vocari.tts.silero_provider import SileroTTSProvider

logger = get_logger("tts.silero_tab")

LANGUAGES = [("ru", "Русский (v4_ru)"), ("en", "English (v3_en)")]


class _PreloadWorker(QObject):
    finished = Signal(str, str, str)  # lang, speaker_count_or_empty, error message ("" on success)

    def __init__(self, provider: SileroTTSProvider, lang: str):
        super().__init__()
        self.provider = provider
        self.lang = lang

    def run(self) -> None:
        try:
            self.provider.preload(self.lang)
            speakers = self.provider.speakers(self.lang)
            self.finished.emit(self.lang, str(len(speakers)), "")
        except Exception as exc:  # noqa: BLE001 - surface any download/load error to the UI
            logger.exception("Не удалось загрузить модель Silero (%s)", self.lang)
            self.finished.emit(self.lang, "", str(exc))


class SileroTab(QWidget):
    def __init__(self, provider: SileroTTSProvider):
        super().__init__()
        self.provider = provider
        self._threads: dict[str, QThread] = {}
        self._workers: dict[str, _PreloadWorker] = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Silero — бесплатный офлайн-синтез речи: модель скачивается один раз "
            "(десятки МБ) и дальше работает на процессоре без интернета и без "
            "видеокарты. Первое сообщение после запуска приложения без предзагрузки "
            "будет с задержкой (скачивание + разогрев модели) — нажмите кнопку ниже "
            "заранее, чтобы озвучка сразу была быстрой."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.status_labels: dict[str, QLabel] = {}
        self.preload_buttons: dict[str, QPushButton] = {}

        for lang, title in LANGUAGES:
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            row.addStretch()

            status_label = QLabel("не загружена")
            status_label.setStyleSheet("color: gray;")
            self.status_labels[lang] = status_label
            row.addWidget(status_label)

            button = QPushButton("Предзагрузить")
            button.clicked.connect(lambda _checked, lang=lang: self._start_preload(lang))
            self.preload_buttons[lang] = button
            row.addWidget(button)

            layout.addLayout(row)

        compat_note = QLabel(
            "Работает строго на CPU — одинаково на любом железе (Intel/AMD, "
            "с видеокартой NVIDIA/AMD или вовсе без неё). Это осознанный выбор "
            "ради совместимости, а не ограничение производительности: Silero и "
            "так спроектирован быстро работать без GPU."
        )
        compat_note.setWordWrap(True)
        compat_note.setStyleSheet("color: gray; font-size: 11px; margin-top: 8px;")
        layout.addWidget(compat_note)

        layout.addStretch()

    def _start_preload(self, lang: str) -> None:
        if self.provider.is_loaded(lang):
            return
        self.preload_buttons[lang].setEnabled(False)
        self.status_labels[lang].setStyleSheet("color: gray;")
        self.status_labels[lang].setText("загрузка…")
        logger.info("Запущена предзагрузка модели Silero (%s)", lang)

        thread = QThread(self)
        worker = _PreloadWorker(self.provider, lang)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_preload_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads[lang] = thread
        self._workers[lang] = worker
        thread.start()

    def _on_preload_finished(self, lang: str, speaker_count: str, error: str) -> None:
        if error:
            self.status_labels[lang].setStyleSheet("color:#ff5c5c;")
            self.status_labels[lang].setText(f"ошибка: {error}")
            self.preload_buttons[lang].setEnabled(True)
            return
        self.status_labels[lang].setStyleSheet("color:#2ecc71;")
        self.status_labels[lang].setText(f"готова ({speaker_count} голосов)")
        self.preload_buttons[lang].setEnabled(False)
        self.preload_buttons[lang].setText("Загружена")
