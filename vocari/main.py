"""Entry point: loads config + avatar model and shows the transparent overlay window."""
from __future__ import annotations

import signal
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger, setup_logging
from vocari.rendering.model import load_model
from vocari.rendering.overlay_window import OverlayWindow
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.edge_provider import EdgeTTSProvider
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

    tts_provider = EdgeTTSProvider()
    audio_player = AudioPlayer(
        on_mouth_state=lambda is_open: window.set_active_frame("mouth", "open" if is_open else "closed"),
        on_talking=window.set_talking,
        on_audio_level=window.set_bounce_level,
    )

    log_window = LogWindow(log_file)
    settings_window = SettingsWindow(
        config, on_model_imported, window.set_sway_enabled, tts_provider, audio_player
    )
    tray = TrayController(window, app, log_window, settings_window)  # noqa: F841

    def on_quit() -> None:
        logger.info("Vocari завершает работу")
        audio_player.stop()
        window.sync_geometry_to_config()
        config.save()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
