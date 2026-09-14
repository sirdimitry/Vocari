"""Settings -> "Piper": download the Piper engine once, then download
individual voices as needed. Loading/inference run on background QThreads —
mirrors silero_tab.py's shape (engine-then-per-item downloads), but Piper
needs no torch-style "restart the app" step: the engine is a plain
subprocess Vocari launches fresh on every synthesize() call, not something
loaded once into this process's own memory."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from vocari.logging_setup import get_logger
from vocari.runtime_deps import PIPER_ENGINE, download as download_engine, is_downloaded as is_engine_downloaded
from vocari.tts.piper_provider import PiperTTSProvider, download_voice
from vocari.tts.piper_voices import PIPER_VOICES, PiperVoice

logger = get_logger("tts.piper_tab")


class _DownloadWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str)  # error message, "" on success

    def __init__(self, run_download):
        super().__init__()
        self._run_download = run_download

    def run(self) -> None:
        try:
            self._run_download(lambda done, total: self.progress.emit(done, total))
            self.finished.emit("")
        except Exception as exc:  # noqa: BLE001 - surface any network/disk error to the UI
            logger.exception("Не удалось скачать (Piper)")
            self.finished.emit(str(exc))


class PiperTab(QWidget):
    def __init__(self, on_voices_loaded=None):
        super().__init__()
        self.provider = PiperTTSProvider()
        self.on_voices_loaded = on_voices_loaded
        self._threads: dict[str, QThread] = {}
        self._workers: dict[str, _DownloadWorker] = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Piper — ещё один бесплатный офлайн-синтез речи, лёгкий и быстрый "
            "(без PyTorch, работает на CPU заметно быстрее Silero). Сначала "
            "скачайте сам движок (один раз), затем — нужные голоса по "
            "отдельности."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # A single grid (not per-row QHBoxLayout) so Qt sizes each column to
        # its widest cell across every row - labels/voice names vary a lot in
        # length ("Ирина" vs "Lessac"), and separate per-row layouts left the
        # status/button columns misaligned between rows.
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)  # the gap between label and status/button grows, not the label itself
        layout.addLayout(grid)
        row_index = 0

        grid.addWidget(QLabel(f"Движок Piper (~{PIPER_ENGINE.approx_size_mb} МБ)"), row_index, 0)
        self.engine_status = QLabel("")
        grid.addWidget(self.engine_status, row_index, 2)
        self.engine_button = QPushButton()
        self.engine_button.clicked.connect(self._start_engine_download)
        grid.addWidget(self.engine_button, row_index, 3)
        row_index += 1

        self.engine_progress = QProgressBar()
        self.engine_progress.setRange(0, 100)
        self.engine_progress.hide()
        grid.addWidget(self.engine_progress, row_index, 0, 1, 4)
        row_index += 1

        grid.addWidget(QLabel("Голоса:"), row_index, 0)
        row_index += 1

        self.voice_status: dict[str, QLabel] = {}
        self.voice_buttons: dict[str, QPushButton] = {}
        self.voice_progress: dict[str, QProgressBar] = {}

        for voice in PIPER_VOICES:
            grid.addWidget(QLabel(f"{voice.label} (~{voice.approx_size_mb} МБ)"), row_index, 0)
            status = QLabel("")
            self.voice_status[voice.voice_id] = status
            grid.addWidget(status, row_index, 2)
            button = QPushButton()
            button.clicked.connect(lambda _checked, v=voice: self._start_voice_download(v))
            self.voice_buttons[voice.voice_id] = button
            grid.addWidget(button, row_index, 3)
            row_index += 1

            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.hide()
            self.voice_progress[voice.voice_id] = progress
            grid.addWidget(progress, row_index, 0, 1, 4)
            row_index += 1

        layout.addStretch()
        self._refresh_engine_state()
        self._refresh_all_voice_states()

    # -- engine ---------------------------------------------------------------

    def _refresh_engine_state(self) -> None:
        available = self.provider.is_engine_available()
        self.engine_status.setStyleSheet("color:#2ecc71;" if available else "color: gray;")
        self.engine_status.setText("готов" if available else "не скачан")
        self.engine_button.setText("Скачан" if available else "Скачать движок Piper")
        self.engine_button.setEnabled(not available)
        for voice in PIPER_VOICES:
            self.voice_buttons[voice.voice_id].setEnabled(available and not self.provider.is_voice_available(voice.voice_id))

    def _start_engine_download(self) -> None:
        self.engine_button.setEnabled(False)
        self.engine_progress.setRange(0, 0)
        self.engine_progress.show()
        self.engine_status.setStyleSheet("color: gray;")
        self.engine_status.setText("скачивание…")
        logger.info("Запущено скачивание движка Piper")

        thread = QThread(self)
        worker = _DownloadWorker(lambda on_progress: download_engine(PIPER_ENGINE, on_progress))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_engine_progress)
        worker.finished.connect(self._on_engine_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads["engine"] = thread
        self._workers["engine"] = worker
        thread.start()

    def _on_engine_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.engine_progress.setRange(0, total)
            self.engine_progress.setValue(downloaded)
        self.engine_status.setText(f"скачано {downloaded // (1024 * 1024)} МБ")

    def _on_engine_finished(self, error: str) -> None:
        self.engine_progress.hide()
        if error:
            self.engine_status.setStyleSheet("color:#ff5c5c;")
            self.engine_status.setText(f"ошибка: {error}")
            self.engine_button.setEnabled(True)
            return
        logger.info("Движок Piper скачан")
        self._refresh_engine_state()

    # -- voices ---------------------------------------------------------------

    def _refresh_all_voice_states(self) -> None:
        for voice in PIPER_VOICES:
            self._refresh_voice_state(voice)

    def _refresh_voice_state(self, voice: PiperVoice) -> None:
        available = self.provider.is_voice_available(voice.voice_id)
        status = self.voice_status[voice.voice_id]
        button = self.voice_buttons[voice.voice_id]
        status.setStyleSheet("color:#2ecc71;" if available else "color: gray;")
        status.setText("готов" if available else "не скачан")
        button.setText("Скачан" if available else "Скачать")
        button.setEnabled(self.provider.is_engine_available() and not available)

    def _start_voice_download(self, voice: PiperVoice) -> None:
        key = voice.voice_id
        self.voice_buttons[key].setEnabled(False)
        progress = self.voice_progress[key]
        progress.setRange(0, 0)
        progress.show()
        status = self.voice_status[key]
        status.setStyleSheet("color: gray;")
        status.setText("скачивание…")
        logger.info("Запущено скачивание голоса Piper '%s'", key)

        thread = QThread(self)
        worker = _DownloadWorker(lambda on_progress, v=voice: download_voice(v, on_progress))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda d, t, k=key: self._on_voice_progress(k, d, t))
        worker.finished.connect(lambda err, v=voice: self._on_voice_finished(v, err))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads[key] = thread
        self._workers[key] = worker
        thread.start()

    def _on_voice_progress(self, key: str, downloaded: int, total: int) -> None:
        progress = self.voice_progress[key]
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(downloaded)
        self.voice_status[key].setText(f"скачано {downloaded // (1024 * 1024)} МБ")

    def _on_voice_finished(self, voice: PiperVoice, error: str) -> None:
        key = voice.voice_id
        self.voice_progress[key].hide()
        if error:
            self.voice_status[key].setStyleSheet("color:#ff5c5c;")
            self.voice_status[key].setText(f"ошибка: {error}")
            self.voice_buttons[key].setEnabled(True)
            return
        logger.info("Голос Piper '%s' скачан", key)
        self._refresh_voice_state(voice)
        if self.on_voices_loaded:
            # Voice ids are "<lang>_<REGION>-..." (e.g. "ru_RU-irina-medium")
            # - same prefix convention tts_queue.py's _voice_pool() uses to
            # bucket a provider's downloaded voices by language.
            matching = [v for v in self.provider.available_voices() if v.startswith(f"{voice.lang}_")]
            self.on_voices_loaded(voice.lang, matching)
