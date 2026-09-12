"""Settings window, opened from the tray icon: Рендер / Модель / TTS / Silero / Twitch / Тест."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.rendering.model import AvatarModel
from vocari.tts.base import TTSProvider
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.tts.tts_queue import TTSQueue
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
        model: AvatarModel,
        on_model_imported: Callable[[Path], None],
        on_sway_toggled: Callable[[bool], None],
        on_always_on_top_toggled: Callable[[bool], None],
        on_position_changed: Callable[[int, int], None],
        on_scale_changed: Callable[[float], None],
        on_entrance_side_toggled: Callable[[bool], None],
        on_exit_speed_changed: Callable[[int], None],
        on_skip_hotkey_changed: Callable[[str], bool],
        tts_providers: dict[str, TTSProvider],
        tts_queue: TTSQueue,
        twitch_bot_controller: TwitchBotController,
    ):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Vocari — настройки (v{__version__})")
        self.resize(500, 600)

        tabs = QTabWidget(self)
        tabs.addTab(
            RenderTab(config, on_sway_toggled, on_always_on_top_toggled, on_skip_hotkey_changed), "Рендер"
        )
        self.model_tab = ModelTab(
            config, model, on_model_imported, on_position_changed, on_scale_changed,
            on_entrance_side_toggled, on_exit_speed_changed, tts_queue,
        )
        tabs.addTab(self.model_tab, "Модель")
        tabs.addTab(TTSTab(config), "TTS")
        silero_provider = tts_providers["silero"]
        assert isinstance(silero_provider, SileroTTSProvider)
        tabs.addTab(SileroTab(silero_provider), "Silero")
        tabs.addTab(TwitchTab(config, twitch_bot_controller), "Twitch")
        tabs.addTab(TestTab(config, tts_queue), "Тест")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
