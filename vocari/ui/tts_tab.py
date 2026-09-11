"""Settings -> "TTS": which engine to use (edge-tts / Silero), voice per
language, speaking rate/volume, language detection mode, and the shared
text length limit."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.tts.voices import EDGE_EN_VOICES, EDGE_RU_VOICES, SILERO_EN_VOICES, SILERO_RU_VOICES
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")

PROVIDERS = [("edge", "Edge TTS (облако, бесплатно)"), ("silero", "Silero (локально, офлайн)")]


def _voice_pool(provider: str, lang: str) -> list[str]:
    if provider == "silero":
        return SILERO_RU_VOICES if lang == "ru" else SILERO_EN_VOICES
    return EDGE_RU_VOICES if lang == "ru" else EDGE_EN_VOICES


class TTSTab(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.provider_combo = QComboBox()
        for key, title in PROVIDERS:
            self.provider_combo.addItem(title, key)
        self.provider_combo.setCurrentIndex(0 if config.tts.provider == "edge" else 1)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Озвучка (движок):", self.provider_combo)

        self.voice_ru_combo = QComboBox()
        self.voice_ru_combo.setEditable(True)
        self.voice_ru_combo.currentTextChanged.connect(self._on_voice_ru_changed)
        form.addRow("Голос RU:", self.voice_ru_combo)

        self.voice_en_combo = QComboBox()
        self.voice_en_combo.setEditable(True)
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

        self.voices_hint = QLabel("")
        self.voices_hint.setWordWrap(True)
        self.voices_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.voices_hint)

        self.rate_hint = QLabel("Скорость не поддерживается Silero и в этом режиме игнорируется.")
        self.rate_hint.setWordWrap(True)
        self.rate_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.rate_hint)

        random_row = QHBoxLayout()
        random_row.addWidget(QLabel("Случайный голос на каждую фразу"))
        random_row.addStretch()
        self.random_voice_toggle = ToggleSwitch()
        self.random_voice_toggle.setChecked(config.tts.random_voice)
        self.random_voice_toggle.toggled.connect(self._on_random_voice_toggled)
        random_row.addWidget(self.random_voice_toggle)
        layout.addLayout(random_row)

        self.random_hint = QLabel("")
        self.random_hint.setWordWrap(True)
        self.random_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.random_hint)

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

        self._refresh_for_provider()

    def _current_provider(self) -> str:
        return self.provider_combo.currentData()

    def _refresh_for_provider(self) -> None:
        provider = self._current_provider()
        is_silero = provider == "silero"

        ru_pool = _voice_pool(provider, "ru")
        en_pool = _voice_pool(provider, "en")

        self.voice_ru_combo.blockSignals(True)
        self.voice_en_combo.blockSignals(True)
        self.voice_ru_combo.clear()
        self.voice_en_combo.clear()
        self.voice_ru_combo.addItems(ru_pool)
        self.voice_en_combo.addItems(en_pool)
        self.voice_ru_combo.setCurrentText(
            self.config.tts.silero_voice_ru if is_silero else self.config.tts.voice_ru
        )
        self.voice_en_combo.setCurrentText(
            self.config.tts.silero_voice_en if is_silero else self.config.tts.voice_en
        )
        self.voice_ru_combo.blockSignals(False)
        self.voice_en_combo.blockSignals(False)

        self.rate_spin.setEnabled(not is_silero)
        self.rate_hint.setVisible(is_silero)

        if is_silero:
            self.voices_hint.setText(
                "Список — стандартные голоса Silero; полный список появится на "
                "вкладке «Silero» после предзагрузки модели."
            )
        else:
            self.voices_hint.setText(
                "Голос можно ввести вручную — полный список даёт команда "
                "edge-tts --list-voices в терминале (с активным окружением .venv)."
            )

        self._update_random_hint()

    def _update_random_hint(self) -> None:
        provider = self._current_provider()
        ru_pool = _voice_pool(provider, "ru")
        en_pool = _voice_pool(provider, "en")
        self.random_hint.setText(
            "Вместо голосов из полей выше каждый раз выбирается случайный из "
            f"набора выбранной озвучки: RU — {', '.join(ru_pool)}; EN — {', '.join(en_pool)}."
        )

    def _on_provider_changed(self, _index: int) -> None:
        self.config.tts.provider = self._current_provider()
        self.config.save()
        logger.info("TTS-провайдер: %s", self.config.tts.provider)
        self._refresh_for_provider()

    def _on_voice_ru_changed(self, text: str) -> None:
        if self._current_provider() == "silero":
            self.config.tts.silero_voice_ru = text
        else:
            self.config.tts.voice_ru = text
        self.config.save()

    def _on_voice_en_changed(self, text: str) -> None:
        if self._current_provider() == "silero":
            self.config.tts.silero_voice_en = text
        else:
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
