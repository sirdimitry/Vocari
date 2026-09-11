"""App-wide logging: writes to logs/vocari.log (auto-wiped past 10 MB) and
mirrors every record to a Qt signal so the in-app log window can show it live,
regardless of which thread logged it (asyncio Twitch/TTS threads included).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

MAX_LOG_BYTES = 10 * 1024 * 1024
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"

LOGGER_NAME = "vocari"


class _QtLogBridge(QObject):
    # (levelname, formatted line) so the log window can color-code by level
    # without re-parsing the text.
    message_logged = Signal(str, str)


log_bridge = _QtLogBridge()


class _QtSignalHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_bridge.message_logged.emit(record.levelname, self.format(record))
        except Exception:
            self.handleError(record)


class _SizeLimitedFileHandler(logging.FileHandler):
    """FileHandler that wipes its own file once it grows past MAX_LOG_BYTES,
    instead of growing forever or keeping numbered backups."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            path = Path(self.baseFilename)
            if path.exists() and path.stat().st_size >= MAX_LOG_BYTES:
                self._truncate()
        except OSError:
            pass
        super().emit(record)

    def _truncate(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        Path(self.baseFilename).write_text("", encoding="utf-8")
        self.stream = self._open()


def setup_logging(project_root: Path) -> Path:
    """Configure the "vocari" logger tree. Returns the log file path."""
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "vocari.log"

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = _SizeLimitedFileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    qt_handler = _QtSignalHandler()
    qt_handler.setFormatter(formatter)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(qt_handler)
    logger.propagate = False

    return log_file


def get_logger(module_name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{module_name}")
