"""Settings -> "Рендер": GPU/CPU render backend toggle + the sway/bounce toggle."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.ui.widgets import HotkeyCaptureButton, ToggleSwitch

logger = get_logger("settings_window")


class RenderTab(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_sway_toggled: Callable[[bool], None],
        on_always_on_top_toggled: Callable[[bool], None],
        on_skip_hotkey_changed: Callable[[str], bool],
    ):
        super().__init__()
        self.config = config
        self.on_sway_toggled = on_sway_toggled
        self.on_always_on_top_toggled = on_always_on_top_toggled
        self.on_skip_hotkey_changed = on_skip_hotkey_changed

        root = QVBoxLayout(self)

        window_box = QGroupBox("Окно и захват в OBS")
        layout = QVBoxLayout(window_box)
        root.addWidget(window_box)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Поверх всех окон"))
        top_row.addStretch()
        self.always_on_top_toggle = ToggleSwitch()
        self.always_on_top_toggle.setChecked(config.render.always_on_top)
        self.always_on_top_toggle.toggled.connect(self._on_always_on_top_toggled)
        top_row.addWidget(self.always_on_top_toggle)
        layout.addLayout(top_row)

        obs_note = QLabel(
            "Как захватить в OBS: источник «Захват окна» → окно «Vocari - …» → "
            "в поле «Метод захвата» обязательно выбрать «Windows 10 (1903 и новее)». "
            "Метод BitBlt (и часто «Автоматически») не умеет захватывать окна с "
            "прозрачностью — источник будет пустым."
        )
        obs_note.setWordWrap(True)
        obs_note.setStyleSheet("color: #e6c229; font-size: 11px;")
        layout.addWidget(obs_note)

        top_note = QLabel(
            "Выключите, чтобы можно было открыть игру или другое приложение "
            "поверх аватара на своём экране. OBS Window Capture захватывает "
            "содержимое окна напрямую, а не область экрана — запись не "
            "пострадает, даже если окно перекрыто чем-то другим."
        )
        top_note.setWordWrap(True)
        top_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(top_note)

        anim_box = QGroupBox("Анимация и рендер")
        layout = QVBoxLayout(anim_box)
        root.addWidget(anim_box)

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
            "Ахоге покачивается дугой от основания, как настоящая прядь; уши "
            "поворачиваются от точки крепления с небольшим запаздыванием "
            "(как настоящие, по инерции); аватар всегда слегка покачивается "
            "вверх-вниз в простое; во время речи сверху добавляется "
            "подпрыгивание, реагирующее на громкость звука (громче/резче "
            "звук — резче скачок), а не просто качается по таймеру. Когда на "
            "сцене одновременно несколько копий (очередь из сообщений), "
            "каждая покачивается и моргает в своём собственном ритме, а не "
            "синхронно."
        )
        sway_note.setWordWrap(True)
        sway_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(sway_note)

        hotkey_box = QGroupBox("Хоткей пропуска фразы")
        layout = QVBoxLayout(hotkey_box)
        root.addWidget(hotkey_box)

        hotkey_row = QHBoxLayout()
        self.hotkey_button = HotkeyCaptureButton(config.hotkey.skip_message, self._on_hotkey_captured)
        hotkey_row.addWidget(self.hotkey_button)
        clear_hotkey_button = QPushButton("Очистить")
        clear_hotkey_button.clicked.connect(lambda: self._on_hotkey_captured(""))
        hotkey_row.addWidget(clear_hotkey_button)
        layout.addLayout(hotkey_row)

        self.hotkey_status_label = QLabel("")
        self.hotkey_status_label.setWordWrap(True)
        layout.addWidget(self.hotkey_status_label)

        hotkey_note = QLabel(
            "Работает глобально — даже когда фокус на игре или другом окне, не "
            "только когда открыты настройки Vocari. По нажатию текущая фраза "
            "обрывается на полуслове, аватар зеркалится и упрыгивает — как будто "
            "договорил."
        )
        hotkey_note.setWordWrap(True)
        hotkey_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hotkey_note)

        root.addStretch()

    def _on_gpu_toggled(self, checked: bool) -> None:
        self.config.render.use_gpu = checked
        self.config.save()
        logger.info("Рендер-бэкенд в настройках: %s", "GPU" if checked else "CPU")

    def _on_sway_toggled(self, checked: bool) -> None:
        self.config.render.enable_sway = checked
        self.config.save()
        logger.info("Покачивание: %s", "включено" if checked else "выключено")
        self.on_sway_toggled(checked)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.render.always_on_top = checked
        self.config.save()
        logger.info("Поверх всех окон: %s", "включено" if checked else "выключено")
        self.on_always_on_top_toggled(checked)

    def _on_hotkey_captured(self, sequence_text: str) -> None:
        ok = self.on_skip_hotkey_changed(sequence_text)
        if ok:
            self.hotkey_status_label.setText("")
            self.hotkey_button.set_sequence(sequence_text)
        else:
            self.hotkey_status_label.setStyleSheet("color:#ff5c5c;")
            self.hotkey_status_label.setText(
                f"Не удалось назначить '{sequence_text}' — возможно, занято другим приложением."
            )
            self.hotkey_button.set_sequence(self.config.hotkey.skip_message)
