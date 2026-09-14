"""Settings -> "Ники": pin a specific avatar to a specific chat nickname
(unbound/unknown senders keep using random_model as before), and tune each
model's relative odds when random_model picks among several.

Both lists are meant to scale to "many models" without becoming an
unreadable wall: rows are compact, single-line, and this tab already sits
inside SettingsWindow's own scroll area like every other tab."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.paths import app_root

logger = get_logger("settings_window")

MODELS_ROOT = app_root() / "assets" / "models"
NO_BINDING = ""  # sentinel stored in config for "не привязан — участвует как аноним"
WEIGHT_SLIDER_MAX = 300  # % — 3x more likely than a freshly-imported model at its default 100%


def _model_names() -> list[str]:
    if not MODELS_ROOT.exists():
        return []
    return sorted(
        folder.name for folder in MODELS_ROOT.iterdir() if (folder / "model.json").exists()
    )


class BindingsTab(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_bindings_changed: Callable[[dict[str, str]], None],
        on_weights_changed: Callable[[dict[str, float]], None],
    ):
        super().__init__()
        self.config = config
        self.on_bindings_changed = on_bindings_changed
        self.on_weights_changed = on_weights_changed
        self._nick_rows: dict[str, QWidget] = {}  # lowercased nick -> row
        self._weight_rows: dict[str, QWidget] = {}  # model name -> row

        root = QVBoxLayout(self)
        root.addWidget(self._build_bindings_group())
        root.addWidget(self._build_weights_group())
        root.addStretch()

    # -- nick -> model bindings -----------------------------------------------

    def _build_bindings_group(self) -> QGroupBox:
        box = QGroupBox("Привязка аватара к нику")
        layout = QVBoxLayout(box)

        hint = QLabel(
            "Сообщения от привязанного ника всегда выходят этим аватаром — "
            "независимо от того, включён ли \"Случайный аватар\" в настройках "
            "Модели. Непривязанные (анонимные) ники получают обычный случайный "
            "выбор. Список ников пополняется сам по мере того, как люди "
            "пишут !tts в чате Twitch — можно привязать сразу, как только "
            "человек написал хоть раз, прямо во время эфира; либо добавить "
            "ник вручную заранее."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.nicks_container = QVBoxLayout()
        self.nicks_container.setSpacing(2)
        layout.addLayout(self.nicks_container)

        self.no_nicks_label = QLabel("Пока ни один ник не отмечен в чате.")
        self.no_nicks_label.setStyleSheet("color: gray;")
        layout.addWidget(self.no_nicks_label)

        add_row = QHBoxLayout()
        self.manual_nick_edit = QLineEdit()
        self.manual_nick_edit.setPlaceholderText("Ник вручную (необязательно ждать сообщения в чате)")
        add_row.addWidget(self.manual_nick_edit, 1)
        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self._on_add_manual_nick)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)

        for nick in self.config.overlay.known_nicks:
            self._add_nick_row(nick)
        self._update_no_nicks_label()
        return box

    def _update_no_nicks_label(self) -> None:
        self.no_nicks_label.setVisible(not self._nick_rows)

    def _add_nick_row(self, nick: str) -> None:
        key = nick.strip().lower()
        if not key or key in self._nick_rows:
            return

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(nick), 1)

        combo = QComboBox()
        combo.addItem("Случайно (аноним)", NO_BINDING)
        for name in _model_names():
            combo.addItem(name, name)
        current = self.config.overlay.user_model_bindings.get(key, NO_BINDING)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.currentIndexChanged.connect(lambda _i, k=key, c=combo: self._on_binding_changed(k, c.currentData()))
        row_layout.addWidget(combo, 1)

        remove_button = QPushButton("✕")
        remove_button.setFixedWidth(28)
        remove_button.setToolTip("Убрать ник из списка")
        remove_button.clicked.connect(lambda: self._on_remove_nick(key))
        row_layout.addWidget(remove_button)

        self.nicks_container.addWidget(row)
        self._nick_rows[key] = row

    def _on_add_manual_nick(self) -> None:
        nick = self.manual_nick_edit.text().strip()
        if not nick:
            return
        self.manual_nick_edit.clear()
        self.add_known_nick(nick)

    def add_known_nick(self, nick: str) -> None:
        """Called live from main.py whenever chat activity names a nick that
        hasn't been seen before — also used for the manual "add by hand"
        field above, so both paths share one code path and one saved list."""
        key = nick.strip().lower()
        if not key or key in self._nick_rows:
            return
        self.config.overlay.known_nicks.append(nick.strip())
        self.config.save()
        self._add_nick_row(nick.strip())
        self._update_no_nicks_label()

    def _on_remove_nick(self, key: str) -> None:
        row = self._nick_rows.pop(key, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self.config.overlay.known_nicks = [n for n in self.config.overlay.known_nicks if n.strip().lower() != key]
        had_binding = self.config.overlay.user_model_bindings.pop(key, None) is not None
        self.config.save()
        self._update_no_nicks_label()
        if had_binding:
            self.on_bindings_changed(dict(self.config.overlay.user_model_bindings))

    def _on_binding_changed(self, key: str, model_name: str) -> None:
        if model_name:
            self.config.overlay.user_model_bindings[key] = model_name
        else:
            self.config.overlay.user_model_bindings.pop(key, None)
        self.config.save()
        logger.info("Ник '%s' привязан к: %s", key, model_name or "случайно")
        self.on_bindings_changed(dict(self.config.overlay.user_model_bindings))

    # -- per-model random weights ---------------------------------------------

    def _build_weights_group(self) -> QGroupBox:
        box = QGroupBox("Шанс появления в случайном режиме")
        layout = QVBoxLayout(box)

        hint = QLabel(
            "100% — обычная, равная со всеми доля; больше — чаще выпадает, "
            "0% — не участвует в случайном выборе вообще (но всё ещё "
            "доступен для ручной привязки по нику выше). Влияет только на "
            "\"Случайный аватар\" в настройках Модели."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.weights_container = QVBoxLayout()
        self.weights_container.setSpacing(2)
        layout.addLayout(self.weights_container)

        for name in _model_names():
            self._add_weight_row(name)
        return box

    def _add_weight_row(self, name: str) -> None:
        if name in self._weight_rows:
            return
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(name), 1)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, WEIGHT_SLIDER_MAX)
        percent = round(self.config.overlay.model_weights.get(name, 1.0) * 100)
        slider.setValue(max(0, min(WEIGHT_SLIDER_MAX, percent)))
        row_layout.addWidget(slider, 2)

        readout = QLabel(f"{slider.value()}%")
        readout.setMinimumWidth(48)
        row_layout.addWidget(readout)

        def on_slider_changed(value: int, name=name, readout=readout) -> None:
            readout.setText(f"{value}%")
            self._on_weight_changed(name, value / 100.0)

        slider.valueChanged.connect(on_slider_changed)
        self.weights_container.addWidget(row)
        self._weight_rows[name] = row

    def _on_weight_changed(self, name: str, weight: float) -> None:
        if abs(weight - 1.0) < 1e-9:
            self.config.overlay.model_weights.pop(name, None)  # 100% is the implicit default — keep config tidy
        else:
            self.config.overlay.model_weights[name] = weight
        self.config.save()
        self.on_weights_changed(dict(self.config.overlay.model_weights))

    # -- keeping in sync with Settings -> Модель -------------------------------

    def refresh_models(self) -> None:
        """Call after a model is imported, deleted, or renamed (Settings ->
        Модель) so the weight list and every nick's dropdown offer exactly
        the models that actually exist right now — otherwise a deleted
        model would keep showing up here as a selectable, silently-dead
        option (see model_tab.py's delete flow, which prunes config and
        calls this via main.py's on_model_deleted)."""
        current = _model_names()

        for name in list(self._weight_rows):
            if name not in current:
                self._weight_rows.pop(name).deleteLater()
        for name in current:
            self._add_weight_row(name)

        for key, row in self._nick_rows.items():
            combo = row.findChild(QComboBox)
            if combo is None:
                continue
            wanted = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Случайно (аноним)", NO_BINDING)
            for name in current:
                combo.addItem(name, name)
            idx = combo.findData(wanted if wanted in current else NO_BINDING)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)
            if wanted and wanted not in current:
                # The bound model is gone - config already dropped it (see
                # model_tab.py's delete flow); reflect that here too so the
                # dropdown shown to the user matches what config now says.
                self.config.overlay.user_model_bindings.pop(key, None)
