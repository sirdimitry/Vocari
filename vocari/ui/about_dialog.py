"""Tray -> "О программе...": the app icon, name/version, and a credit line —
nothing configurable here, it's a static info popup."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from vocari.__version__ import __version__
from vocari.branding import app_icon

REPO_URL = "https://github.com/sirdimitry/Vocari"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setWindowIcon(app_icon())
        self.setFixedSize(360, 290)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.addStretch()

        icon_label = QLabel()
        icon_label.setPixmap(app_icon().pixmap(96, 96))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(icon_label)

        name_label = QLabel("Vocari")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = name_label.font()
        name_font.setPointSize(name_font.pointSize() + 8)
        name_font.setBold(True)
        name_label.setFont(name_font)
        root.addWidget(name_label)

        version_label = QLabel(f"версия {__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: gray;")
        root.addWidget(version_label)

        credit_label = QLabel("навайбкодил — @sirdimitry")
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(credit_label)

        link_label = QLabel(f'<a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>')
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        root.addWidget(link_label)

        root.addStretch()

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)
        button_row.addStretch()
        root.addLayout(button_row)
