"""Entry point: loads config + avatar model and shows the transparent overlay window."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from vocari.__version__ import __version__
from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger, setup_logging
from vocari.rendering.model import load_model
from vocari.rendering.overlay_window import OverlayWindow
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

    log_window = LogWindow(log_file)
    settings_window = SettingsWindow(config, on_model_imported, window.set_sway_enabled)
    tray = TrayController(window, app, log_window, settings_window)  # noqa: F841

    def on_quit() -> None:
        logger.info("Vocari завершает работу")
        window.sync_geometry_to_config()
        config.save()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
