"""Settings -> "Рендер": GPU/CPU render backend toggle + the sway/bounce toggle."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")


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
        sway_row.addWidget(QLabel("Покачивание (ахоге + фон + подпрыг при речи)"))
        sway_row.addStretch()
        self.sway_toggle = ToggleSwitch()
        self.sway_toggle.setChecked(config.render.enable_sway)
        self.sway_toggle.toggled.connect(self._on_sway_toggled)
        sway_row.addWidget(self.sway_toggle)
        layout.addLayout(sway_row)

        sway_note = QLabel(
            "Ахоге покачивается дугой от основания, как настоящая прядь; аватар "
            "всегда слегка покачивается вверх-вниз в простое; во время речи сверху "
            "добавляется подпрыгивание, реагирующее на громкость звука "
            "(громче/резче звук — резче скачок), а не просто качается по таймеру."
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
