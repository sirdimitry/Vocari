"""Settings window, opened from the tray icon: Рендер / Модель / Облачко / TTS / Silero / Twitch."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.rendering.model import AvatarModel
from vocari.tts.base import TTSProvider
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.tts.tts_queue import TTSQueue
from vocari.twitch.bot_controller import TwitchBotController
from vocari.ui.bubble_tab import BubbleTab
from vocari.ui.model_tab import ModelTab
from vocari.ui.render_tab import RenderTab
from vocari.ui.silero_tab import SileroTab
from vocari.ui.tts_tab import TTSTab
from vocari.ui.twitch_tab import TwitchTab

WINDOW_WIDTH = 1000  # roughly double the old 500 — the model tab needs two columns
WINDOW_HEIGHT = 720
CONTENT_MAX_WIDTH = 720  # readable measure for the single-column tabs


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
        on_model_selected: Callable[[str], None],
        on_random_model_toggled: Callable[[bool], None],
        on_random_pool_changed: Callable[[list[str]], None],
        on_skip_hotkey_changed: Callable[[str], bool],
        on_bubble_changed: Callable[[], None],
        tts_providers: dict[str, TTSProvider],
        tts_queue: TTSQueue,
        twitch_bot_controller: TwitchBotController,
    ):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Vocari — настройки (v{__version__})")
        # One fixed window size for every tab (tabs used to resize the window
        # to whatever the current one needed, so switching tabs made it jump
        # around and the tallest ones ran off the screen). Anything that
        # doesn't fit scrolls inside its tab instead — see _wrap().
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 520)

        tabs = QTabWidget(self)
        tabs.setDocumentMode(True)
        tabs.addTab(
            self._wrap(RenderTab(config, on_sway_toggled, on_always_on_top_toggled, on_skip_hotkey_changed)),
            "Рендер",
        )
        self.model_tab = ModelTab(
            config, model, on_model_imported, on_position_changed, on_scale_changed,
            on_entrance_side_toggled, on_exit_speed_changed,
            on_model_selected, on_random_model_toggled, on_random_pool_changed,
        )
        # The model tab lays itself out in two columns, so it gets the full
        # window width; the single-column tabs stay within a readable measure.
        tabs.addTab(self._wrap(self.model_tab, constrain_width=False), "Модель")
        tabs.addTab(
            self._wrap(BubbleTab(config, on_bubble_changed, tts_queue), constrain_width=False),
            "Облачко",
        )
        tabs.addTab(self._wrap(TTSTab(config)), "TTS")
        silero_provider = tts_providers["silero"]
        assert isinstance(silero_provider, SileroTTSProvider)
        tabs.addTab(self._wrap(SileroTab(silero_provider)), "Silero")
        tabs.addTab(self._wrap(TwitchTab(config, twitch_bot_controller)), "Twitch")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(tabs)

    def _wrap(self, tab: QWidget, constrain_width: bool = True) -> QScrollArea:
        """Puts a tab in a scroll area so a tall tab scrolls instead of
        stretching the window. `constrain_width` keeps single-column tabs at a
        comfortable reading measure and centers them, rather than letting
        paragraphs span the full (now much wider) window."""
        content: QWidget = tab
        if constrain_width:
            tab.setMaximumWidth(CONTENT_MAX_WIDTH)
            content = QWidget()
            row = QHBoxLayout(content)
            row.setContentsMargins(0, 0, 0, 0)
            row.addStretch(1)
            row.addWidget(tab, 0)
            row.addStretch(1)

        area = QScrollArea()
        area.setWidget(content)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return area

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
