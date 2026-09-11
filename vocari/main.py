"""Entry point: loads config + avatar model and shows the transparent overlay window."""
from __future__ import annotations

import signal
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from vocari.__version__ import __version__
from vocari.chat.base import ChatMessage
from vocari.chat.filters import CooldownTracker, extract_command_text, find_blacklisted_word, has_access
from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger, setup_logging
from vocari.rendering.model import load_model
from vocari.rendering.overlay_window import OverlayWindow
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.edge_provider import EdgeTTSProvider
from vocari.tts.service import enforce_length_limit
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.tts.tts_queue import TTSQueue
from vocari.twitch.bot_controller import TwitchBotController
from vocari.ui.log_window import LogWindow
from vocari.ui.settings_window import SettingsWindow
from vocari.ui.tray_icon import TrayController

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = get_logger("main")


def main() -> None:
    log_file = setup_logging(PROJECT_ROOT)

    app = QApplication(sys.argv)
    # The overlay window is frameless; hiding it must not quit the app — only
    # the tray icon's "Выход" should.
    app.setQuitOnLastWindowClosed(False)

    # Ctrl+C in a terminal otherwise raises KeyboardInterrupt inside whatever
    # Qt callback happens to be running (paintEvent, a timer tick, ...),
    # which can leave things like an in-progress QPainter half-finished.
    # Route it through a clean app.quit() instead.
    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    logger.info("Vocari v%s запускается", __version__)

    config = AppConfig.load()
    model_dir = PROJECT_ROOT / config.overlay.model_path
    logger.info("Загрузка модели из %s", model_dir)
    model = load_model(model_dir)
    logger.info(
        "Модель '%s' загружена: %d базовых слоёв, состояния: %s",
        model.name,
        len(model.base_layers),
        ", ".join(model.states.keys()) or "нет",
    )

    window = OverlayWindow(model, config.overlay, config.render)
    window.show()

    def on_model_imported(model_dir: Path) -> None:
        try:
            new_model = load_model(model_dir)
        except Exception:
            logger.exception("Не удалось загрузить импортированную модель из %s", model_dir)
            return
        window.set_model(new_model)
        logger.info("Оверлей обновлён: модель '%s'", new_model.name)

    tts_providers = {"edge": EdgeTTSProvider(), "silero": SileroTTSProvider()}
    audio_player = AudioPlayer(
        on_mouth_state=lambda is_open: window.set_active_frame("mouth", "open" if is_open else "closed"),
        on_talking=window.set_talking,
        on_audio_level=window.set_bounce_level,
    )

    tts_queue = TTSQueue(config, tts_providers, audio_player)

    twitch_bot = TwitchBotController(config.twitch)
    cooldown_tracker = CooldownTracker()

    def on_chat_message(message: ChatMessage) -> None:
        command_text = extract_command_text(message.text, config.twitch.command_prefix)
        if not command_text:
            return
        if not has_access(message, config.twitch):
            logger.info("Twitch: %s — нет доступа к команде (фильтр подписки/VIP/модератора)", message.display_name)
            return
        if not cooldown_tracker.check_and_record(message.username, config.twitch.cooldown_seconds):
            logger.info("Twitch: %s — кулдаун", message.display_name)
            return
        blocked_word = find_blacklisted_word(command_text, config.twitch.blacklist_words)
        if blocked_word:
            logger.info("Twitch: %s — заблокировано слово '%s'", message.display_name, blocked_word)
            return
        text, truncated = enforce_length_limit(command_text, config.tts)
        logger.info(
            "Twitch !tts от %s: '%s'%s", message.display_name, text, " (обрезано)" if truncated else ""
        )
        tts_queue.enqueue(text)

    twitch_bot.message_received.connect(on_chat_message)

    log_window = LogWindow(log_file)
    settings_window = SettingsWindow(
        config,
        on_model_imported,
        window.set_sway_enabled,
        window.set_position,
        window.set_scale,
        tts_providers,
        audio_player,
        twitch_bot,
    )
    tray = TrayController(window, app, log_window, settings_window)  # noqa: F841

    def on_quit() -> None:
        logger.info("Vocari завершает работу")
        twitch_bot.stop()
        audio_player.stop()
        window.sync_geometry_to_config()
        config.save()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
