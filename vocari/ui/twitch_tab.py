"""Settings -> "Twitch": chat connection + filter settings. Stage 4 only
stores these and walks the user through getting a token — the bot itself
connects and applies them in Stage 5."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")

TOKEN_GENERATOR_URL = "https://twitchapps.com/tmi/"


class TwitchTab(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        layout = QVBoxLayout(self)

        connect_label = QLabel("Подключение к Twitch")
        connect_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(connect_label)

        steps_label = QLabel(
            "1. Нажмите кнопку ниже — откроется страница входа через Twitch "
            "(это НЕ пароль от аккаунта, а отдельный токен для чат-ботов — "
            "стандартный способ авторизации у Twitch).<br>"
            "2. Войдите под аккаунтом, которым бот будет писать в чат (можно "
            "тем же, что и канал), разрешите доступ.<br>"
            "3. Страница покажет токен вида <b>oauth:abcdefg...</b> — скопируйте "
            "его целиком и вставьте в поле «OAuth-токен» ниже."
        )
        steps_label.setWordWrap(True)
        layout.addWidget(steps_label)

        open_token_page_button = QPushButton("Открыть страницу получения токена")
        open_token_page_button.clicked.connect(self._open_token_page)
        layout.addWidget(open_token_page_button)

        form = QFormLayout()

        self.channel_edit = QLineEdit(config.twitch.channel)
        self.channel_edit.setPlaceholderText("имя_канала")
        form.addRow("Канал:", self.channel_edit)

        token_row = QHBoxLayout()
        self.token_edit = QLineEdit(config.twitch.oauth_token)
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("oauth:...")
        self.show_token_button = QPushButton("Показать")
        self.show_token_button.setCheckable(True)
        self.show_token_button.toggled.connect(self._on_show_token_toggled)
        token_row.addWidget(self.token_edit)
        token_row.addWidget(self.show_token_button)
        form.addRow("OAuth-токен:", token_row)

        self.prefix_edit = QLineEdit(config.twitch.command_prefix)
        form.addRow("Команда-триггер:", self.prefix_edit)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 600)
        self.cooldown_spin.setSuffix(" сек")
        self.cooldown_spin.setValue(config.twitch.cooldown_seconds)
        form.addRow("Кулдаун на пользователя:", self.cooldown_spin)

        layout.addLayout(form)

        self.token_format_hint = QLabel("")
        self.token_format_hint.setWordWrap(True)
        self.token_format_hint.setStyleSheet("color:#e6c229; font-size: 11px;")
        self.token_format_hint.hide()
        layout.addWidget(self.token_format_hint)

        privacy_hint = QLabel(
            "Токен хранится только локально, в config.json на этом компьютере — "
            "этот файл не попадает в git (он в .gitignore). Не публикуйте его нигде."
        )
        privacy_hint.setWordWrap(True)
        privacy_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(privacy_hint)

        stage_hint = QLabel(
            "Само подключение к чату и проверка токена появятся на Этапе 5 — "
            "сейчас вкладка только сохраняет введённые данные."
        )
        stage_hint.setWordWrap(True)
        stage_hint.setStyleSheet("color: gray; font-size: 11px; font-style: italic;")
        layout.addWidget(stage_hint)

        access_label = QLabel("Кому разрешено пользоваться командой")
        access_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(access_label)
        access_hint = QLabel("Если ничего не включено — доступно всем зрителям. Иначе действует ИЛИ (любое совпадение).")
        access_hint.setWordWrap(True)
        access_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(access_hint)

        self.subs_toggle = ToggleSwitch()
        self.subs_toggle.setChecked(config.twitch.subs_only)
        self.vip_toggle = ToggleSwitch()
        self.vip_toggle.setChecked(config.twitch.vip_only)
        self.mods_toggle = ToggleSwitch()
        self.mods_toggle.setChecked(config.twitch.mods_only)

        access_row = QHBoxLayout()
        for label_text, toggle in (
            ("Подписчики", self.subs_toggle),
            ("VIP", self.vip_toggle),
            ("Модераторы", self.mods_toggle),
        ):
            access_row.addWidget(QLabel(label_text))
            access_row.addWidget(toggle)
            access_row.addSpacing(16)
        access_row.addStretch()
        layout.addLayout(access_row)

        blacklist_label = QLabel("Чёрный список слов/фраз (по одному на строку)")
        blacklist_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(blacklist_label)

        self.blacklist_edit = QPlainTextEdit()
        self.blacklist_edit.setPlainText("\n".join(config.twitch.blacklist_words))
        self.blacklist_edit.setMaximumHeight(80)
        layout.addWidget(self.blacklist_edit)

        length_hint = QLabel("Лимит длины сообщения — общий с TTS, см. вкладку «TTS».")
        length_hint.setWordWrap(True)
        length_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(length_hint)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self._save)
        save_row.addWidget(save_button)
        layout.addLayout(save_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _open_token_page(self) -> None:
        logger.info("Открываю страницу получения Twitch-токена в браузере")
        QDesktopServices.openUrl(QUrl(TOKEN_GENERATOR_URL))

    def _on_show_token_toggled(self, checked: bool) -> None:
        self.token_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_token_button.setText("Скрыть" if checked else "Показать")

    def _save(self) -> None:
        token = self.token_edit.text().strip()
        if token and not token.startswith("oauth:"):
            self.token_format_hint.setText(
                "Похоже, в токене нет префикса \"oauth:\" в начале — обычно он "
                "выглядит как oauth:abcdefg... Проверьте, что скопировали токен целиком."
            )
            self.token_format_hint.show()
        else:
            self.token_format_hint.hide()

        self.config.twitch.channel = self.channel_edit.text().strip()
        self.config.twitch.oauth_token = token
        self.config.twitch.command_prefix = self.prefix_edit.text().strip() or "!tts"
        self.config.twitch.cooldown_seconds = self.cooldown_spin.value()
        self.config.twitch.subs_only = self.subs_toggle.isChecked()
        self.config.twitch.vip_only = self.vip_toggle.isChecked()
        self.config.twitch.mods_only = self.mods_toggle.isChecked()
        self.config.twitch.blacklist_words = [
            line.strip() for line in self.blacklist_edit.toPlainText().splitlines() if line.strip()
        ]
        self.config.save()
        logger.info("Настройки Twitch сохранены (канал: %s)", self.config.twitch.channel or "—")
        self.status_label.setStyleSheet("color:#2ecc71;")
        self.status_label.setText("Сохранено.")
