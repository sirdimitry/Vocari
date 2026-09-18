"""Settings -> "Silero": preload the local/offline TTS models ahead of time
so the first real message doesn't pay the download+warm-up cost. Loading
and inference run on a background QThread — both are blocking calls.

If torch itself isn't available yet (the packaged build doesn't bundle it —
see vocari/runtime_deps.py), this shows a one-time download button instead
of the per-language preload rows; the app needs a restart afterwards to pick
it up (torch does a lot of native-library loading at process start that
isn't worth trying to redo mid-run for what's a rare, one-off event)."""
from __future__ import annotations

import sys
import threading
from typing import Callable

from PySide6.QtCore import QObject, QProcess, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocari.logging_setup import get_logger
from vocari.runtime_deps import (
    DownloadCancelled,
    TORCH_CPU,
    TORCH_RUNTIME_DOWNLOAD_SUPPORTED,
    download,
    ensure_on_path,
)
from vocari.tts.silero_provider import SileroTTSProvider

logger = get_logger("tts.silero_tab")

LANGUAGES = [("ru", "Русский (v4_ru)"), ("en", "English (v3_en)")]


def _torch_available() -> bool:
    ensure_on_path(TORCH_CPU)
    try:
        import torch  # noqa: F401
    except (ImportError, OSError):
        logger.warning("PyTorch недоступен", exc_info=True)
        return False
    return True


class _PreloadWorker(QObject):
    finished = Signal(str, str, str)  # lang, speaker_count_or_empty, error message ("" on success)

    def __init__(self, provider: SileroTTSProvider, lang: str, *, cached_only: bool = False):
        super().__init__()
        self.provider = provider
        self.lang = lang
        self.cached_only = cached_only
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            if self._cancelled.is_set():
                return
            if self.cached_only:
                self.provider.preload(self.lang, allow_download=False)
            else:
                self.provider.preload(self.lang)
            if self._cancelled.is_set():
                return
            speakers = self.provider.speakers(self.lang)
            self.finished.emit(self.lang, str(len(speakers)), "")
        except Exception as exc:  # noqa: BLE001 - surface any download/load error to the UI
            logger.exception("Не удалось загрузить модель Silero (%s)", self.lang)
            self.finished.emit(self.lang, "", str(exc))


class _TorchDownloadWorker(QObject):
    progress = Signal(int, int)  # downloaded_bytes, total_bytes (0 = unknown)
    finished = Signal(str)  # error message, "" on success

    def __init__(self):
        super().__init__()
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            download(
                TORCH_CPU, lambda done, total: self.progress.emit(done, total),
                is_cancelled=self._cancelled.is_set,
            )
            self.finished.emit("")
        except DownloadCancelled:
            self.finished.emit("Загрузка отменена")
        except Exception as exc:  # noqa: BLE001 - surface any network/disk error to the UI
            logger.exception("Не удалось скачать PyTorch")
            self.finished.emit(str(exc))


class SileroTab(QWidget):
    def __init__(self, provider: SileroTTSProvider, on_voices_loaded: Callable[[str, list[str]], None] | None = None):
        super().__init__()
        self.provider = provider
        self.on_voices_loaded = on_voices_loaded
        self._threads: dict[str, QThread] = {}
        self._workers: dict[str, _PreloadWorker] = {}
        self._torch_thread: QThread | None = None
        self._torch_worker: _TorchDownloadWorker | None = None
        self._shutting_down = False

        self.layout_ = QVBoxLayout(self)

        if _torch_available():
            self._build_preload_ui()
        elif not TORCH_RUNTIME_DOWNLOAD_SUPPORTED:
            self._build_linux_info_ui()
        else:
            self._build_torch_download_ui()

        if not hasattr(self, "preload_buttons"):
            # Model files persist independently of the optional PyTorch runtime.
            for lang, title in LANGUAGES:
                cached = self.provider.has_cached_model(lang)
                state = "скачана; для проверки и запуска нужен PyTorch" if cached else "не скачана"
                label = QLabel(f"{title}: {state}")
                label.setWordWrap(True)
                self.layout_.insertWidget(self.layout_.count() - 1, label)

    def _build_linux_info_ui(self) -> None:
        note = QLabel(
            "Автоматическая загрузка PyTorch сейчас доступна только в Windows. "
            "В сборке для EndeavourOS используйте Edge TTS или Piper. При запуске "
            "Vocari из исходников Silero появится автоматически, если установить "
            "PyTorch в то же Python-окружение до запуска приложения."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        self.layout_.addWidget(note)
        self.layout_.addStretch()

    # -- normal mode: torch already available --------------------------------

    def _build_preload_ui(self) -> None:
        intro = QLabel(
            "Silero — бесплатный офлайн-синтез речи: модель скачивается один раз "
            "(десятки МБ) и дальше работает на процессоре без интернета и без "
            "видеокарты. При каждом запуске все скачанные языковые модели "
            "автоматически проверяются и загружаются в память с диска. "
            "Повторное скачивание для исправных моделей не требуется."
        )
        intro.setWordWrap(True)
        self.layout_.addWidget(intro)

        self.status_labels: dict[str, QLabel] = {}
        self.preload_buttons: dict[str, QPushButton] = {}

        for lang, title in LANGUAGES:
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            row.addStretch()

            cached = getattr(self.provider, "has_cached_model", lambda _lang: False)(lang)
            status_label = QLabel("скачана — ожидает проверки" if cached else "не скачана")
            status_label.setStyleSheet("color: gray;")
            self.status_labels[lang] = status_label
            row.addWidget(status_label)

            button = QPushButton("Проверить и загрузить" if cached else "Скачать и загрузить")
            button.clicked.connect(lambda _checked, lang=lang: self._start_preload(lang))
            self.preload_buttons[lang] = button
            row.addWidget(button)

            self.layout_.addLayout(row)

        compat_note = QLabel(
            "Работает строго на CPU — одинаково на любом железе (Intel/AMD, "
            "с видеокартой NVIDIA/AMD или вовсе без неё). Это осознанный выбор "
            "ради совместимости, а не ограничение производительности: Silero и "
            "так спроектирован быстро работать без GPU."
        )
        compat_note.setWordWrap(True)
        compat_note.setStyleSheet("color: gray; font-size: 11px; margin-top: 8px;")
        self.layout_.addWidget(compat_note)

        self.clear_button = QPushButton("Удалить скачанные модели Silero")
        self.clear_button.clicked.connect(self._clear_downloaded_models)
        self.layout_.addWidget(self.clear_button)

        self.layout_.addStretch()
        # Cached files survive restart/update while provider memory does not.
        # Verify and load every detected language in the background, then
        # publish each model's complete speaker list to the TTS tab.
        QTimer.singleShot(0, self._auto_load_cached_models)

    def _auto_load_cached_models(self) -> None:
        if self._shutting_down:
            return
        has_cached_model = getattr(self.provider, "has_cached_model", None)
        if has_cached_model is None:
            return
        for lang, _title in LANGUAGES:
            if self.provider.is_loaded(lang) or has_cached_model(lang):
                self.status_labels[lang].setText("найдена, проверка…")
                self._start_preload(lang, cached_only=True)

    def _clear_downloaded_models(self) -> None:
        if self._threads:
            return
        answer = QMessageBox.question(
            self,
            "Очистить модели Silero",
            "Удалить все скачанные языковые модели Silero? При следующей загрузке они будут скачаны заново.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            for lang, _title in LANGUAGES:
                self.provider.remove_cached_model(lang)
                self.status_labels[lang].setStyleSheet("color: gray;")
                self.status_labels[lang].setText("не скачана")
                self.preload_buttons[lang].setText("Скачать и загрузить")
                self.preload_buttons[lang].setEnabled(True)
                if self.on_voices_loaded:
                    self.on_voices_loaded(lang, [])
        except OSError as exc:
            QMessageBox.warning(self, "Не удалось очистить Silero", str(exc))

    def _start_preload(self, lang: str, *, cached_only: bool = False) -> None:
        if self._shutting_down or lang in self._threads:
            return
        if self.provider.is_loaded(lang):
            self._on_preload_finished(lang, str(len(self.provider.speakers(lang))), "")
            return
        self.preload_buttons[lang].setEnabled(False)
        self.clear_button.setEnabled(False)
        self.status_labels[lang].setStyleSheet("color: gray;")
        self.status_labels[lang].setText(
            "скачана — проверка и загрузка с диска…" if cached_only else "загрузка…"
        )
        logger.info("Запущена предзагрузка модели Silero (%s)", lang)

        thread = QThread(self)
        worker = _PreloadWorker(self.provider, lang, cached_only=cached_only)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_preload_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._threads[lang] = thread
        self._workers[lang] = worker
        thread.start()

    def _on_preload_finished(self, lang: str, speaker_count: str, error: str) -> None:
        if self._shutting_down:
            return
        if error:
            self.status_labels[lang].setStyleSheet("color:#ff5c5c;")
            self.status_labels[lang].setText(f"ошибка: {error}")
            self.preload_buttons[lang].setEnabled(True)
            self.preload_buttons[lang].setText("Скачать заново")
            return
        self.status_labels[lang].setStyleSheet("color:#2ecc71;")
        self.status_labels[lang].setText(f"скачана и готова ({speaker_count} голосов)")
        self.preload_buttons[lang].setEnabled(False)
        self.preload_buttons[lang].setText("Загружена")
        if self.on_voices_loaded:
            # self.provider already has this language's model loaded at
            # this point (that's what just finished) - speakers() returns
            # its real list straight from the model, e.g. all 119 v3_en
            # names instead of the small static sample the TTS tab starts
            # with (see vocari/tts/voices.py).
            self.on_voices_loaded(lang, self.provider.speakers(lang))

    # -- first-run mode: torch needs downloading -----------------------------

    def _build_torch_download_ui(self) -> None:
        intro = QLabel(
            f"Офлайн-голоса Silero используют PyTorch — он не входит в "
            f"установщик (чтобы не раздувать его для всех, даже тех, кто "
            f"голосами Silero не пользуется), а скачивается один раз отдельно, "
            f"~{TORCH_CPU.approx_size_mb} МБ. После скачивания понадобится "
            f"перезапустить Vocari — дальше всё работает полностью офлайн, "
            f"без интернета и без повторных запросов."
        )
        intro.setWordWrap(True)
        self.layout_.addWidget(intro)

        self.download_status = QLabel("")
        self.download_status.setWordWrap(True)
        self.layout_.addWidget(self.download_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        self.layout_.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        self.download_button = QPushButton(f"Скачать офлайн-голоса (~{TORCH_CPU.approx_size_mb} МБ)")
        self.download_button.clicked.connect(self._start_torch_download)
        button_row.addWidget(self.download_button)

        self.restart_button = QPushButton("Перезапустить Vocari")
        self.restart_button.clicked.connect(self._restart_app)
        self.restart_button.hide()
        button_row.addWidget(self.restart_button)
        button_row.addStretch()
        self.layout_.addLayout(button_row)

        self.layout_.addStretch()

    def _start_torch_download(self) -> None:
        self.download_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate until the first progress signal names a total
        self.progress_bar.show()
        self.download_status.setStyleSheet("color: gray;")
        self.download_status.setText("Скачивание…")
        logger.info("Запущено скачивание PyTorch для офлайн-голосов Silero")

        thread = QThread(self)
        worker = _TorchDownloadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_torch_progress)
        worker.finished.connect(self._on_torch_download_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_torch_thread_finished)
        self._torch_thread = thread
        self._torch_worker = worker
        thread.start()

    def _on_torch_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(downloaded)
            self.download_status.setText(f"Скачано {downloaded // (1024 * 1024)} / {total // (1024 * 1024)} МБ")
        else:
            self.download_status.setText(f"Скачано {downloaded // (1024 * 1024)} МБ")

    def _on_torch_download_finished(self, error: str) -> None:
        if self._shutting_down:
            return
        if error:
            self.progress_bar.hide()
            self.download_status.setStyleSheet("color:#ff5c5c;")
            self.download_status.setText(f"Ошибка загрузки: {error}")
            self.download_button.setEnabled(True)
            return
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.download_status.setStyleSheet("color:#2ecc71;")
        self.download_status.setText("Готово! Перезапустите Vocari, чтобы включить офлайн-голоса.")
        self.download_button.hide()
        self.restart_button.show()
        logger.info("PyTorch для офлайн-голосов Silero скачан")

    def _restart_app(self) -> None:
        # Without this, a second click before the process actually exits
        # (quit() asks Qt to shut down, it doesn't happen instantly) starts
        # a second detached process on top of the first one - exactly the
        # "two Vocari icons in the tray" a user hit.
        self.restart_button.setEnabled(False)
        logger.info("Перезапуск Vocari для включения офлайн-голосов")
        started = QProcess.startDetached(sys.executable, sys.argv[1:])
        if not started:
            logger.error("Не удалось запустить новый процесс Vocari при перезапуске")
            self.restart_button.setEnabled(True)
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self.sender()
        for lang, candidate in list(self._threads.items()):
            if candidate is thread:
                self._threads.pop(lang, None)
                self._workers.pop(lang, None)
                break
        if hasattr(self, "clear_button"):
            self.clear_button.setEnabled(not self._threads)

    @Slot()
    def _on_torch_thread_finished(self) -> None:
        self._torch_thread = None
        self._torch_worker = None

    def shutdown(self) -> None:
        self._shutting_down = True
        jobs = [(self._threads[key], worker) for key, worker in list(self._workers.items()) if key in self._threads]
        if self._torch_thread is not None and self._torch_worker is not None:
            jobs.append((self._torch_thread, self._torch_worker))
        for thread, worker in jobs:
            worker.cancel()
            thread.requestInterruption()
            thread.quit()
        for thread, _worker in jobs:
            if thread.isRunning():
                thread.wait()
        self._threads.clear()
        self._workers.clear()
        self._torch_thread = None
        self._torch_worker = None
