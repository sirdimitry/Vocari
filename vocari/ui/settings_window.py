"""Settings window, opened from the tray icon. Stage 4 will add the full
TTS/Twitch/Тест sections here as further tabs."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.rendering.model_import import import_model_from_folder
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.ui.test_tab import TestTab
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_ROOT = PROJECT_ROOT / "assets" / "models"


class RenderTab(QWidget):
    def __init__(self, config: AppConfig, on_sway_toggled: Callable[[bool], None]):
        super().__init__()
        self.config = config
        self.on_sway_toggled = on_sway_toggled

        layout = QVBoxLayout(self)

        gpu_row = QHBoxLayout()
        gpu_row.addWidget(QLabel("Использовать GPU (RTX) вместо CPU"))
        gpu_row.addStretch()
        self.gpu_toggle = ToggleSwitch()
        self.gpu_toggle.setChecked(config.render.use_gpu)
        self.gpu_toggle.toggled.connect(self._on_gpu_toggled)
        gpu_row.addWidget(self.gpu_toggle)
        layout.addLayout(gpu_row)

        gpu_note = QLabel(
            "Пока переключатель только сохраняет выбор в config.json — сам "
            "GPU-рендер (OpenGL) будет включён отдельным обновлением конвейера "
            "рендеринга, чтобы не сломать прозрачность окна."
        )
        gpu_note.setWordWrap(True)
        gpu_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(gpu_note)

        sway_row = QHBoxLayout()
        sway_row.addWidget(QLabel("Покачивание (ахоге + лёгкий подпрыг при речи)"))
        sway_row.addStretch()
        self.sway_toggle = ToggleSwitch()
        self.sway_toggle.setChecked(config.render.enable_sway)
        self.sway_toggle.toggled.connect(self._on_sway_toggled)
        sway_row.addWidget(self.sway_toggle)
        layout.addLayout(sway_row)

        sway_note = QLabel(
            "Подпрыгивание тела сработает, когда на Этапе 3 подключится TTS — "
            "пока эффективно только покачивание ахоге."
        )
        sway_note.setWordWrap(True)
        sway_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(sway_note)

        layout.addStretch()

    def _on_gpu_toggled(self, checked: bool) -> None:
        self.config.render.use_gpu = checked
        self.config.save()
        logger.info("Рендер-бэкенд в настройках: %s", "GPU" if checked else "CPU")

    def _on_sway_toggled(self, checked: bool) -> None:
        self.config.render.enable_sway = checked
        self.config.save()
        logger.info("Покачивание: %s", "включено" if checked else "выключено")
        self.on_sway_toggled(checked)


class ModelTab(QWidget):
    def __init__(self, config: AppConfig, on_model_imported: Callable[[Path], None]):
        super().__init__()
        self.config = config
        self.on_model_imported = on_model_imported

        layout = QVBoxLayout(self)

        self.current_label = QLabel(f"Текущая модель: {config.overlay.model_path}")
        layout.addWidget(self.current_label)

        choose_button = QPushButton("Выбрать папку со своей моделью…")
        choose_button.clicked.connect(self._choose_folder)
        layout.addWidget(choose_button)

        hint = QLabel(
            "Укажите папку с PNG-слоями (все на одном холсте одного размера). "
            "Приложение само разберёт слои: файлы со словом \"eye\"/\"глаз\" и "
            "\"mouth\"/\"рот\" распознаются как моргание/речь (по наличию "
            "open/closed в имени), остальное станет статичными слоями."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка с PNG-слоями модели")
        if not folder:
            return

        try:
            result = import_model_from_folder(Path(folder), MODELS_ROOT)
        except ValueError as exc:
            logger.error("Импорт модели из %s не удался: %s", folder, exc)
            self.status_label.setStyleSheet("color:#ff5c5c;")
            self.status_label.setText(f"Ошибка: {exc}")
            return

        self.config.overlay.model_path = f"assets/models/{result.model_name}"
        self.config.save()
        self.current_label.setText(f"Текущая модель: {self.config.overlay.model_path}")

        summary = [
            f"Импортировано: {result.base_layer_count} базовых слоёв; "
            f"обнаружены анимации: {', '.join(result.detected_states) or 'нет'}."
        ]
        summary.extend(result.warnings)
        self.status_label.setStyleSheet("color:#e6c229;" if result.warnings else "color:#2ecc71;")
        self.status_label.setText("\n".join(summary))

        logger.info(
            "Импортирована модель '%s' из %s (%d базовых слоёв, анимации: %s)",
            result.model_name,
            folder,
            result.base_layer_count,
            ", ".join(result.detected_states) or "нет",
        )
        self.on_model_imported(result.target_dir)


class SettingsWindow(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_model_imported: Callable[[Path], None],
        on_sway_toggled: Callable[[bool], None],
        tts_provider: TTSProvider,
        audio_player: AudioPlayer,
    ):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Vocari — настройки (v{__version__})")
        self.resize(460, 320)

        tabs = QTabWidget(self)
        tabs.addTab(RenderTab(config, on_sway_toggled), "Рендер")
        tabs.addTab(ModelTab(config, on_model_imported), "Модель")
        tabs.addTab(TestTab(config, tts_provider, audio_player), "Тест")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
