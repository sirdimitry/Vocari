"""Settings -> "Модель": import a model folder, and adjust overlay
position/scale without needing to drag/scroll the transparent window itself."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.paths import app_root
from vocari.rendering.model import AvatarModel
from vocari.rendering.model_import import import_model_from_folder
from vocari.ui.screen_preview import ScreenPreviewWidget
from vocari.ui.widgets import ToggleSwitch

logger = get_logger("settings_window")

MODELS_ROOT = app_root() / "assets" / "models"

POSITION_RANGE = 20000  # generous bound for multi-monitor setups
MIN_SCALE_PERCENT = 10
MAX_SCALE_PERCENT = 500


class ModelTab(QWidget):
    def __init__(
        self,
        config: AppConfig,
        model: AvatarModel,
        on_model_imported: Callable[[Path], None],
        on_position_changed: Callable[[int, int], None],
        on_scale_changed: Callable[[float], None],
        on_entrance_side_toggled: Callable[[bool], None],
        on_exit_speed_changed: Callable[[int], None],
        on_model_selected: Callable[[str], None],
        on_random_model_toggled: Callable[[bool], None],
        on_random_pool_changed: Callable[[list[str]], None],
    ):
        super().__init__()
        self.config = config
        self.on_model_imported = on_model_imported
        self.on_position_changed = on_position_changed
        self.on_scale_changed = on_scale_changed
        self.on_entrance_side_toggled = on_entrance_side_toggled
        self.on_exit_speed_changed = on_exit_speed_changed
        self.on_model_selected = on_model_selected
        self.on_random_model_toggled = on_random_model_toggled
        self.on_random_pool_changed = on_random_pool_changed
        self.pool_checks: dict[str, QCheckBox] = {}

        # Two columns: the screen preview (the thing you actually aim with)
        # on the left, the numbers that describe it on the right, so dragging
        # the box and reading/typing X/Y sit side by side instead of a metre
        # apart down a single scrolling column.
        root = QVBoxLayout(self)
        root.addWidget(self._build_model_group())

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_preview_group(model), 3)
        columns.addWidget(self._build_geometry_group(), 2)
        root.addLayout(columns)

        root.addWidget(self._build_timing_group())
        root.addStretch()

    # -- sections ---------------------------------------------------------

    def _build_model_group(self) -> QGroupBox:
        box = QGroupBox("Модель")
        layout = QVBoxLayout(box)

        model_names = [
            folder.name
            for folder in (sorted(MODELS_ROOT.iterdir()) if MODELS_ROOT.exists() else [])
            if (folder / "model.json").exists()
        ]

        picker = QFormLayout()
        self.model_combo = QComboBox()
        for name in model_names:
            self.model_combo.addItem(name, f"assets/models/{name}")
        index = self.model_combo.findData(self.config.overlay.model_path)
        self.model_combo.setCurrentIndex(max(0, index))
        self.model_combo.currentIndexChanged.connect(self._on_model_selected)
        picker.addRow("Активный аватар:", self.model_combo)
        layout.addLayout(picker)

        self.random_check = QCheckBox("Случайный аватар на каждое сообщение")
        self.random_check.setChecked(self.config.overlay.random_model)
        self.random_check.toggled.connect(self._on_random_toggled)
        layout.addWidget(self.random_check)

        random_hint = QLabel(
            "Когда включено, выбор выше игнорируется: для каждого сообщения "
            "берётся случайный аватар из отмеченных ниже, так что в очереди "
            "одновременно могут стоять разные персонажи."
        )
        random_hint.setWordWrap(True)
        random_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(random_hint)

        pool_row = QHBoxLayout()
        pool_row.addWidget(QLabel("Участвуют в случайном выборе:"))
        pool_row.addStretch()
        for name in model_names:
            check = QCheckBox(name)
            check.setChecked(not self.config.overlay.random_pool or name in self.config.overlay.random_pool)
            check.toggled.connect(self._on_pool_check_toggled)
            self.pool_checks[name] = check
            pool_row.addWidget(check)
        layout.addLayout(pool_row)

        pool_hint = QLabel(
            "Если ничего не отмечено — участвуют все. Список читается моделью "
            "один раз при запуске настроек, так что папку с новой моделью надо "
            "сначала импортировать (или добавить в assets/models вручную) и "
            "переоткрыть настройки, чтобы она здесь появилась."
        )
        pool_hint.setWordWrap(True)
        pool_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(pool_hint)

        self.current_label = QLabel(f"Текущая модель: {self.config.overlay.model_path}")
        layout.addWidget(self.current_label)

        choose_button = QPushButton("Выбрать папку со своей моделью…")
        choose_button.clicked.connect(self._choose_folder)
        layout.addWidget(choose_button)

        hint = QLabel(
            "Укажите папку с PNG-слоями (все на одном холсте одного размера). "
            "Приложение само разберёт слои: файлы со словом \"eye\"/\"глаз\" и "
            "\"mouth\"/\"рот\" распознаются как моргание/речь (по наличию "
            "open/closed в имени), остальное станет статичными слоями."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        return box

    def _build_preview_group(self, model: AvatarModel) -> QGroupBox:
        box = QGroupBox("Превью позиции на экране")
        layout = QVBoxLayout(box)

        self.preview = ScreenPreviewWidget(self.config, model, self._on_preview_dragged)
        self.preview.setMinimumHeight(240)
        layout.addWidget(self.preview, 1)

        preview_hint = QLabel(
            "Чёрный прямоугольник — ваш экран целиком; зелёная рамка — где встанет "
            "аватар, когда говорит. Перетащите рамку мышью, чтобы задать позицию, "
            "не подбирая X/Y на глаз. Жёлтая стрелка показывает, с какой стороны "
            "аватар выезжает и упрыгивает."
        )
        preview_hint.setWordWrap(True)
        preview_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(preview_hint)
        return box

    def _build_geometry_group(self) -> QGroupBox:
        box = QGroupBox("Позиция и масштаб оверлея")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.pos_x_spin = QSpinBox()
        self.pos_x_spin.setRange(-POSITION_RANGE, POSITION_RANGE)
        self.pos_x_spin.setValue(self.config.overlay.pos_x)
        form.addRow("X:", self.pos_x_spin)

        self.pos_y_spin = QSpinBox()
        self.pos_y_spin.setRange(-POSITION_RANGE, POSITION_RANGE)
        self.pos_y_spin.setValue(self.config.overlay.pos_y)
        form.addRow("Y:", self.pos_y_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(MIN_SCALE_PERCENT, MAX_SCALE_PERCENT)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setValue(self.config.overlay.scale * 100)
        form.addRow("Масштаб:", self.scale_spin)
        layout.addLayout(form)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        apply_button = QPushButton("Применить")
        apply_button.clicked.connect(self._apply_geometry)
        apply_row.addWidget(apply_button)
        layout.addLayout(apply_row)

        geometry_hint = QLabel("То же самое можно менять прямо на аватаре: перетаскивание мышью и колесо.")
        geometry_hint.setWordWrap(True)
        geometry_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(geometry_hint)

        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("Выезд справа (вместо слева)"))
        side_row.addStretch()
        self.entrance_side_toggle = ToggleSwitch()
        self.entrance_side_toggle.setChecked(self.config.render.entrance_from_right)
        self.entrance_side_toggle.toggled.connect(self._on_entrance_side_toggled)
        side_row.addWidget(self.entrance_side_toggle)
        layout.addLayout(side_row)

        layout.addStretch()
        return box

    def _build_timing_group(self) -> QGroupBox:
        box = QGroupBox("Тайминги выхода и ухода")
        layout = QVBoxLayout(box)

        timing_form = QFormLayout()
        timing_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.pre_delay_slider, pre_row = self._make_slider(
            1, 50, round(self.config.render.pre_speech_delay_ms / 100), self._on_pre_delay_changed, " с", 10.0
        )
        timing_form.addRow("Пауза перед речью:", pre_row)

        self.post_delay_slider, post_row = self._make_slider(
            1, 50, round(self.config.render.post_speech_hold_ms / 100), self._on_post_delay_changed, " с", 10.0
        )
        timing_form.addRow("Пауза после речи:", post_row)

        self.exit_speed_slider, exit_row = self._make_slider(
            1, 100, self.config.render.exit_speed, self._on_exit_speed_changed, "", 1.0
        )
        timing_form.addRow("Скорость ухода:", exit_row)
        layout.addLayout(timing_form)

        timing_hint = QLabel(
            "Пауза перед речью — сколько аватар стоит на месте, прежде чем начать "
            "говорить (она же прикрывает задержку синтеза: если синтез дольше — "
            "речь начнётся сразу, как будет готова). Скорость ухода: 1 — уезжает "
            "медленно, 100 — исчезает мгновенно."
        )
        timing_hint.setWordWrap(True)
        timing_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(timing_hint)
        return box

    def _make_slider(
        self,
        minimum: int,
        maximum: int,
        value: int,
        on_changed: Callable[[int], None],
        suffix: str,
        divisor: float,
    ) -> tuple[QSlider, QWidget]:
        """Slider + live value readout. `divisor`/`suffix` are display-only —
        the slider itself always works in whole steps (Qt sliders are
        integer-only), e.g. 1..50 tenths of a second shown as "0.1 с".."5.0 с"."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        readout = QLabel()
        readout.setMinimumWidth(48)

        def render_value(raw: int) -> None:
            shown = raw / divisor
            readout.setText(f"{shown:.1f}{suffix}" if divisor != 1.0 else f"{shown:.0f}{suffix}")

        render_value(value)
        slider.valueChanged.connect(render_value)
        slider.valueChanged.connect(on_changed)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider)
        row_layout.addWidget(readout)
        return slider, row

    def _on_pre_delay_changed(self, tenths: int) -> None:
        self.config.render.pre_speech_delay_ms = tenths * 100
        self.config.save()

    def _on_post_delay_changed(self, tenths: int) -> None:
        self.config.render.post_speech_hold_ms = tenths * 100
        self.config.save()

    def _on_exit_speed_changed(self, speed: int) -> None:
        self.config.render.exit_speed = speed
        self.config.save()
        self.on_exit_speed_changed(speed)

    def _apply_geometry(self) -> None:
        x, y = self.pos_x_spin.value(), self.pos_y_spin.value()
        scale = self.scale_spin.value() / 100.0
        self.on_position_changed(x, y)
        self.on_scale_changed(scale)
        self.config.save()
        self.preview.update()
        logger.info("Позиция/масштаб оверлея изменены из настроек: (%d, %d), %.0f%%", x, y, scale * 100)

    def _on_preview_dragged(self, x: int, y: int) -> None:
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.pos_x_spin.setValue(x)
        self.pos_y_spin.setValue(y)
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self.on_position_changed(x, y)

    def _on_entrance_side_toggled(self, checked: bool) -> None:
        self.config.render.entrance_from_right = checked
        self.config.save()
        self.on_entrance_side_toggled(checked)
        self.preview.update()
        logger.info("Выезд аватара: %s", "справа" if checked else "слева")

    def _on_model_selected(self) -> None:
        path = self.model_combo.currentData()
        if not path:
            return
        self.config.overlay.model_path = path
        self.config.save()
        self.current_label.setText(f"Текущая модель: {path}")
        self.on_model_selected(path)

    def _on_random_toggled(self, checked: bool) -> None:
        self.config.overlay.random_model = checked
        self.config.save()
        self.model_combo.setEnabled(not checked)
        self.on_random_model_toggled(checked)

    def _on_pool_check_toggled(self) -> None:
        checked = [name for name, check in self.pool_checks.items() if check.isChecked()]
        self.config.overlay.random_pool = checked
        self.config.save()
        self.on_random_pool_changed(checked)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка с PNG-слоями модели")
        if not folder:
            return

        try:
            result = import_model_from_folder(Path(folder), MODELS_ROOT)
        except ValueError as exc:
            logger.error("Импорт модели из %s не удался: %s", folder, exc)
            self.status_label.setStyleSheet("color:#ff5c5c;")
            self.status_label.setText(f"Ошибка: {exc}")
            return

        self.config.overlay.model_path = f"assets/models/{result.model_name}"
        self.config.save()
        self.current_label.setText(f"Текущая модель: {self.config.overlay.model_path}")

        summary = [
            f"Импортировано: {result.base_layer_count} базовых слоёв; "
            f"обнаружены анимации: {', '.join(result.detected_states) or 'нет'}."
        ]
        summary.extend(result.warnings)
        self.status_label.setStyleSheet("color:#e6c229;" if result.warnings else "color:#2ecc71;")
        self.status_label.setText("\n".join(summary))

        logger.info(
            "Импортирована модель '%s' из %s (%d базовых слоёв, анимации: %s)",
            result.model_name,
            folder,
            result.base_layer_count,
            ", ".join(result.detected_states) or "нет",
        )
        self.on_model_imported(result.target_dir)

    def set_model(self, model: AvatarModel) -> None:
        """Keeps the preview's canvas size in sync after a hot-swapped model
        import (see main.py's on_model_imported)."""
        self.preview.set_model(model)
