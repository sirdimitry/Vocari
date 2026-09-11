"""Settings -> "TTS": voice per language, speaking rate/volume, language
detection mode, and the shared text length limit."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.tts.voices import EN_VOICES, RU_VOICES
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")


class TTSTab(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.voice_ru_combo = QComboBox()
        self.voice_ru_combo.setEditable(True)
        self.voice_ru_combo.addItems(RU_VOICES)
        self.voice_ru_combo.setCurrentText(config.tts.voice_ru)
        self.voice_ru_combo.currentTextChanged.connect(self._on_voice_ru_changed)
        form.addRow("Голос RU:", self.voice_ru_combo)

        self.voice_en_combo = QComboBox()
        self.voice_en_combo.setEditable(True)
        self.voice_en_combo.addItems(EN_VOICES)
        self.voice_en_combo.setCurrentText(config.tts.voice_en)
        self.voice_en_combo.currentTextChanged.connect(self._on_voice_en_changed)
        form.addRow("Голос EN:", self.voice_en_combo)

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(-50, 100)
        self.rate_spin.setSuffix(" %")
        self.rate_spin.setValue(config.tts.rate_percent)
        self.rate_spin.valueChanged.connect(self._on_rate_changed)
        form.addRow("Скорость речи:", self.rate_spin)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(-50, 50)
        self.volume_spin.setSuffix(" %")
        self.volume_spin.setValue(config.tts.volume_percent)
        self.volume_spin.valueChanged.connect(self._on_volume_changed)
        form.addRow("Громкость:", self.volume_spin)

        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(20, 1000)
        self.max_chars_spin.setValue(config.tts.max_chars)
        self.max_chars_spin.valueChanged.connect(self._on_max_chars_changed)
        form.addRow("Лимит длины текста:", self.max_chars_spin)

        layout.addLayout(form)

        voices_hint = QLabel(
            "Голос можно ввести вручную — полный список даёт команда "
            "edge-tts --list-voices в терминале (с активным окружением .venv)."
        )
        voices_hint.setWordWrap(True)
        voices_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(voices_hint)

        random_row = QHBoxLayout()
        random_row.addWidget(QLabel("Случайный голос на каждую фразу"))
        random_row.addStretch()
        self.random_voice_toggle = ToggleSwitch()
        self.random_voice_toggle.setChecked(config.tts.random_voice)
        self.random_voice_toggle.toggled.connect(self._on_random_voice_toggled)
        random_row.addWidget(self.random_voice_toggle)
        layout.addLayout(random_row)

        random_hint = QLabel(
            "Вместо голосов из полей выше каждый раз выбирается случайный из "
            f"набора: RU — {', '.join(RU_VOICES)}; EN — {', '.join(EN_VOICES)}."
        )
        random_hint.setWordWrap(True)
        random_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(random_hint)

        self.voice_ru_combo.setEnabled(not config.tts.random_voice)
        self.voice_en_combo.setEnabled(not config.tts.random_voice)

        auto_row = QFormLayout()
        self.auto_detect_toggle = ToggleSwitch()
        self.auto_detect_toggle.setChecked(config.tts.auto_detect_language)
        self.auto_detect_toggle.toggled.connect(self._on_auto_detect_toggled)
        auto_row.addRow("Автоопределение языка:", self.auto_detect_toggle)

        self.manual_lang_combo = QComboBox()
        self.manual_lang_combo.addItem("Русский", "ru")
        self.manual_lang_combo.addItem("English", "en")
        self.manual_lang_combo.setCurrentIndex(0 if config.tts.manual_lang == "ru" else 1)
        self.manual_lang_combo.currentIndexChanged.connect(self._on_manual_lang_changed)
        self.manual_lang_combo.setEnabled(not config.tts.auto_detect_language)
        auto_row.addRow("Язык вручную:", self.manual_lang_combo)
        layout.addLayout(auto_row)

        auto_hint = QLabel(
            "Автоопределение выбирает RU/EN по преобладающим буквам в тексте "
            "(кириллица/латиница). Выключите, если хотите всегда фиксированный язык."
        )
        auto_hint.setWordWrap(True)
        auto_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(auto_hint)

        layout.addStretch()

    def _on_voice_ru_changed(self, text: str) -> None:
        self.config.tts.voice_ru = text
        self.config.save()

    def _on_voice_en_changed(self, text: str) -> None:
        self.config.tts.voice_en = text
        self.config.save()

    def _on_rate_changed(self, value: int) -> None:
        self.config.tts.rate_percent = value
        self.config.save()

    def _on_volume_changed(self, value: int) -> None:
        self.config.tts.volume_percent = value
        self.config.save()

    def _on_max_chars_changed(self, value: int) -> None:
        self.config.tts.max_chars = value
        self.config.save()

    def _on_auto_detect_toggled(self, checked: bool) -> None:
        self.config.tts.auto_detect_language = checked
        self.manual_lang_combo.setEnabled(not checked)
        self.config.save()
        logger.info("Автоопределение языка TTS: %s", "включено" if checked else "выключено")

    def _on_manual_lang_changed(self, index: int) -> None:
        self.config.tts.manual_lang = self.manual_lang_combo.itemData(index)
        self.config.save()

    def _on_random_voice_toggled(self, checked: bool) -> None:
        self.config.tts.random_voice = checked
        self.voice_ru_combo.setEnabled(not checked)
        self.voice_en_combo.setEnabled(not checked)
        self.config.save()
        logger.info("Случайный голос: %s", "включено" if checked else "выключено")
