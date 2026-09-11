"""System tray icon: the overlay window is frameless (required for a clean OBS
Window Capture — a title bar/border would get captured along with the avatar),
so all window management (show/hide, quit) goes through the tray instead of
standard Windows chrome.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from vocari.__version__ import __version__
from vocari.logging_setup import get_logger
from vocari.rendering.overlay_window import OverlayWindow
from vocari.ui.log_window import LogWindow
from vocari.ui.settings_window import SettingsWindow

logger = get_logger("tray")


class TrayController:
    def __init__(
        self,
        window: OverlayWindow,
        app: QApplication,
        log_window: LogWindow,
        settings_window: SettingsWindow,
    ):
        self.window = window
        self.app = app
        self.log_window = log_window
        self.settings_window = settings_window

        self.tray = QSystemTrayIcon(_build_icon())
        self.tray.setToolTip(f"Vocari v{__version__}")

        menu = QMenu()
        self.toggle_action = menu.addAction("Скрыть аватар")
        self.toggle_action.triggered.connect(self._toggle_visibility)

        settings_action = menu.addAction("Настройки…")
        settings_action.triggered.connect(self._show_settings)

        log_action = menu.addAction("Лог…")
        log_action.triggered.connect(self._show_log)

        menu.addSeparator()
        exit_action = menu.addAction("Выход")
        exit_action.triggered.connect(app.quit)

        menu.aboutToShow.connect(self._sync_toggle_text)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _sync_toggle_text(self) -> None:
        self.toggle_action.setText("Скрыть аватар" if self.window.isVisible() else "Показать аватар")

    def _toggle_visibility(self) -> None:
        visible = not self.window.isVisible()
        self.window.setVisible(visible)
        logger.info("Аватар %s", "показан" if visible else "скрыт")

    def _show_log(self) -> None:
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def _show_settings(self) -> None:
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visibility()


def _build_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#6c5ce7"))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)

    painter.setPen(QColor("white"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(30)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "V")
    painter.end()

    return QIcon(pixmap)
