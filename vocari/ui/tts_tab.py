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

PROVIDERS = [
    ("edge", "Edge TTS (облако, бесплатно)"),
    ("silero", "Silero (локально, офлайн)"),
    ("piper", "Piper (локально, офлайн, быстрее Silero)"),
]

_HINT_POOL_LIMIT = 8  # names shown inline before falling back to "N голосов"


def _format_pool(pool: list[str]) -> str:
    if len(pool) <= _HINT_POOL_LIMIT:
        return ", ".join(pool)
    return f"{', '.join(pool[:_HINT_POOL_LIMIT])} и ещё {len(pool) - _HINT_POOL_LIMIT}"


class TTSTab(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        # Filled in with the real speaker list once Silero actually loads a
        # model (see set_silero_voices(), called from Settings -> Silero
        # after a successful preload) - until then this stays the small
        # static sample from vocari/tts/voices.py, since the model hasn't
        # loaded yet and there's nothing truer to show.
        self._silero_voices: dict[str, list[str]] = {
            "ru": list(SILERO_RU_VOICES),
            "en": list(SILERO_EN_VOICES),
        }
        # Same idea as _silero_voices, but Piper starts genuinely empty -
        # nothing's downloaded until the user does so from Settings -> Piper
        # (see set_piper_voices()), unlike Silero/edge which always have at
        # least a small static sample to show.
        self._piper_voices: dict[str, list[str]] = {"ru": [], "en": []}

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

        self.max_backlog_spin = QSpinBox()
        self.max_backlog_spin.setRange(1, 1000)
        self.max_backlog_spin.setKeyboardTracking(False)
        self.max_backlog_spin.setValue(config.tts.max_backlog_messages)
        self.max_backlog_spin.valueChanged.connect(self._on_max_backlog_changed)
        form.addRow("Сообщений в резервной очереди:", self.max_backlog_spin)

        queue_hint = QLabel(
            "Сколько сообщений могут ждать одновременно сверх 7 мест на сцене. "
            "Общее число сообщений за стрим не ограничено. При заполнении новые "
            "сообщения отклоняются; ожидающие более 2 минут пропускаются перед синтезом. "
            "Изменение действует сразу. При уменьшении лимита уже принятые сообщения остаются в очереди."
        )
        queue_hint.setWordWrap(True)
        queue_hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(queue_hint)

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
        self.random_voice_toggle = ToggleSwitch("Случайный голос")
        self.random_voice_toggle.setChecked(config.tts.random_voice)
        self.random_voice_toggle.toggled.connect(self._on_random_voice_toggled)
        random_row.addWidget(self.random_voice_toggle)
        layout.addLayout(random_row)

        self.random_hint = QLabel("")
        self.random_hint.setWordWrap(True)
        self.random_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.random_hint)

        auto_row = QFormLayout()
        self.auto_detect_toggle = ToggleSwitch("Автоопределение языка")
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

    def _voice_pool(self, provider: str, lang: str) -> list[str]:
        if provider == "silero":
            return self._silero_voices[lang]
        if provider == "piper":
            return self._piper_voices[lang]
        return EDGE_RU_VOICES if lang == "ru" else EDGE_EN_VOICES

    def set_silero_voices(self, lang: str, voices: list[str]) -> None:
        """Called from Settings -> Silero once a model actually finishes
        loading, with its real speaker list (e.g. all 119 v3_en speakers,
        not the 5-item static sample from vocari/tts/voices.py this tab
        starts with) - refreshes the dropdown live if Silero/this language
        happens to be showing right now."""
        self._silero_voices[lang] = voices
        if self._current_provider() == "silero":
            self._refresh_for_provider()

    def set_piper_voices(self, lang: str, voices: list[str]) -> None:
        """Called from Settings -> Piper after a voice download finishes,
        with every downloaded voice for that language - refreshes the
        dropdown live if Piper/this language happens to be showing."""
        self._piper_voices[lang] = voices
        if self._current_provider() == "piper":
            self._refresh_for_provider()

    def _current_voice(self, provider: str, lang: str) -> str:
        if provider == "silero":
            return self.config.tts.silero_voice_ru if lang == "ru" else self.config.tts.silero_voice_en
        if provider == "piper":
            return self.config.tts.piper_voice_ru if lang == "ru" else self.config.tts.piper_voice_en
        return self.config.tts.voice_ru if lang == "ru" else self.config.tts.voice_en

    def _refresh_for_provider(self) -> None:
        provider = self._current_provider()
        is_offline = provider in ("silero", "piper")

        ru_pool = self._voice_pool(provider, "ru")
        en_pool = self._voice_pool(provider, "en")

        self.voice_ru_combo.blockSignals(True)
        self.voice_en_combo.blockSignals(True)
        self.voice_ru_combo.clear()
        self.voice_en_combo.clear()
        self.voice_ru_combo.addItems(ru_pool)
        self.voice_en_combo.addItems(en_pool)
        self.voice_ru_combo.setCurrentText(self._current_voice(provider, "ru"))
        self.voice_en_combo.setCurrentText(self._current_voice(provider, "en"))
        self.voice_ru_combo.blockSignals(False)
        self.voice_en_combo.blockSignals(False)

        self.rate_spin.setEnabled(not is_offline)
        self.rate_hint.setVisible(is_offline)

        if provider == "silero":
            loaded = len(ru_pool) > len(SILERO_RU_VOICES) or len(en_pool) > len(SILERO_EN_VOICES)
            self.voices_hint.setText(
                f"Полный список голосов Silero ({len(ru_pool)} RU, {len(en_pool)} EN)."
                if loaded
                else "Список — небольшой стандартный набор; полный (119 EN, 6 RU) появится "
                "здесь сам после предзагрузки модели на вкладке «Silero»."
            )
        elif provider == "piper":
            self.voices_hint.setText(
                f"Скачано: {len(ru_pool)} RU, {len(en_pool)} EN."
                if ru_pool or en_pool
                else "Пока ни один голос не скачан — откройте вкладку «Piper», чтобы выбрать и скачать."
            )
        else:
            self.voices_hint.setText(
                "Голос можно ввести вручную — полный список даёт команда "
                "edge-tts --list-voices в терминале (с активным окружением .venv)."
            )

        self._update_random_hint()

    def _update_random_hint(self) -> None:
        provider = self._current_provider()
        ru_pool = self._voice_pool(provider, "ru")
        en_pool = self._voice_pool(provider, "en")
        self.random_hint.setText(
            "Вместо голосов из полей выше каждый раз выбирается случайный из "
            f"набора выбранной озвучки: RU — {_format_pool(ru_pool)}; EN — {_format_pool(en_pool)}."
        )

    def _on_provider_changed(self, _index: int) -> None:
        self.config.tts.provider = self._current_provider()
        self.config.save()
        logger.info("TTS-провайдер: %s", self.config.tts.provider)
        self._refresh_for_provider()

    def _on_voice_ru_changed(self, text: str) -> None:
        provider = self._current_provider()
        if provider == "silero":
            self.config.tts.silero_voice_ru = text
        elif provider == "piper":
            self.config.tts.piper_voice_ru = text
        else:
            self.config.tts.voice_ru = text
        self.config.save()

    def _on_voice_en_changed(self, text: str) -> None:
        provider = self._current_provider()
        if provider == "silero":
            self.config.tts.silero_voice_en = text
        elif provider == "piper":
            self.config.tts.piper_voice_en = text
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

    def _on_max_backlog_changed(self, value: int) -> None:
        self.config.tts.max_backlog_messages = value
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
