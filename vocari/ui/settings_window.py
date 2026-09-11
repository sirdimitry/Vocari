"""Settings window, opened from the tray icon: Рендер / Модель / TTS / Silero / Twitch / Тест."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.base import TTSProvider
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.twitch.bot_controller import TwitchBotController
from vocari.ui.model_tab import ModelTab
from vocari.ui.render_tab import RenderTab
from vocari.ui.silero_tab import SileroTab
from vocari.ui.test_tab import TestTab
from vocari.ui.tts_tab import TTSTab
from vocari.ui.twitch_tab import TwitchTab


class SettingsWindow(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_model_imported: Callable[[Path], None],
        on_sway_toggled: Callable[[bool], None],
        on_position_changed: Callable[[int, int], None],
        on_scale_changed: Callable[[float], None],
        tts_providers: dict[str, TTSProvider],
        audio_player: AudioPlayer,
        twitch_bot_controller: TwitchBotController,
    ):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Vocari — настройки (v{__version__})")
        self.resize(500, 600)

        tabs = QTabWidget(self)
        tabs.addTab(RenderTab(config, on_sway_toggled), "Рендер")
        tabs.addTab(
            ModelTab(config, on_model_imported, on_position_changed, on_scale_changed), "Модель"
        )
        tabs.addTab(TTSTab(config), "TTS")
        silero_provider = tts_providers["silero"]
        assert isinstance(silero_provider, SileroTTSProvider)
        tabs.addTab(SileroTab(silero_provider), "Silero")
        tabs.addTab(TwitchTab(config, twitch_bot_controller), "Twitch")
        tabs.addTab(TestTab(config, tts_providers, audio_player), "Тест")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
