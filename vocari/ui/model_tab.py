"""Settings -> "Модель": import a model folder, and adjust overlay
position/scale without needing to drag/scroll the transparent window itself."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig, OverlayConfig
from vocari.logging_setup import get_logger
from vocari.paths import app_root
from vocari.rendering.model import AvatarModel
from vocari.rendering.model_import import import_model_from_folder
from vocari.ui.layer_order_dialog import LayerOrderDialog
from vocari.ui.screen_preview import ScreenPreviewWidget
from vocari.ui.widgets import CheckableModelCombo, ToggleSwitch

logger = get_logger("settings_window")

MODELS_ROOT = app_root() / "assets" / "models"

# Shipped with the app itself (repo + installer) — never offered for
# in-app deletion, only folders the user imported themselves are.
BUILTIN_MODEL_NAMES = {"Ariral", "Orc", "Ranger", "Coder"}

POSITION_RANGE = 20000  # generous bound for multi-monitor setups
MIN_SCALE_PERCENT = 10
MAX_SCALE_PERCENT = 500
POOL_GRID_COLUMNS = 4  # wraps instead of one long unreadable row once there are many models


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
        on_model_deleted: Callable[[str], None],
    ):
        super().__init__()
        self.config = config
        self.model = model
        self.on_model_imported = on_model_imported
        self.on_position_changed = on_position_changed
        self.on_scale_changed = on_scale_changed
        self.on_entrance_side_toggled = on_entrance_side_toggled
        self.on_exit_speed_changed = on_exit_speed_changed
        self.on_model_selected = on_model_selected
        self.on_random_model_toggled = on_random_model_toggled
        self.on_random_pool_changed = on_random_pool_changed
        self.on_model_deleted = on_model_deleted

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
        if not self.config.overlay.random_pool_initialized:
            # Migrate the old empty-means-all convention once. Afterwards an
            # empty list is a real, persistent "no models selected" state.
            self.config.overlay.random_pool = list(model_names)
            self.config.overlay.random_pool_initialized = True
            self.config.save()
            self.on_random_pool_changed(list(model_names))

        picker = QFormLayout()
        # One list serves both jobs: picking the single active avatar (click
        # a row) and marking which ones are eligible for random mode (click
        # the checkbox at the row's left edge) — see CheckableModelCombo.
        # A separate checkbox row for the latter would need its own scaling
        # story once someone imports many models; this one already has it.
        self.model_combo = CheckableModelCombo()
        self.model_combo.checked_changed.connect(self._on_pool_check_toggled)
        self.model_combo.delete_requested.connect(self._on_delete_model_requested)
        for name in model_names:
            self.model_combo.add_item(
                name, f"assets/models/{name}",
                name in self.config.overlay.random_pool,
                deletable=name not in BUILTIN_MODEL_NAMES,
            )
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
            "берётся случайный аватар из отмеченных галочкой в списке выше "
            "(галочка слева от названия — она не меняет активный аватар, "
            "только участие в розыгрыше), так что в очереди одновременно "
            "могут стоять разные персонажи. Если ничего не отмечено или у "
            "всех отмеченных моделей шанс равен 0%, используется текущий "
            "активный аватар. Красный крестик справа от своих импортированных "
            "моделей удаляет их (папку с диска) — у встроенных аватаров "
            "крестика нет."
        )
        random_hint.setWordWrap(True)
        random_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(random_hint)

        self.current_label = QLabel(f"Текущая модель: {self.config.overlay.model_path}")
        layout.addWidget(self.current_label)

        buttons_row = QHBoxLayout()
        choose_button = QPushButton("Выбрать папку со своей моделью…")
        choose_button.clicked.connect(self._choose_folder)
        buttons_row.addWidget(choose_button)

        order_button = QPushButton("Порядок слоёв…")
        order_button.clicked.connect(self._open_layer_order_dialog)
        buttons_row.addWidget(order_button)
        layout.addLayout(buttons_row)

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
        self.entrance_side_toggle = ToggleSwitch("Выезд справа")
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
        # Deliberately not disabling model_combo here (unlike a plain
        # picker, it doubles as the random-pool checkboxes — those need to
        # stay clickable exactly when random mode is on).
        self.on_random_model_toggled(checked)

    def _on_pool_check_toggled(self) -> None:
        checked = self.model_combo.checked_names()
        self.config.overlay.random_pool = checked
        self.config.save()
        self.on_random_pool_changed(checked)

    def _on_delete_model_requested(self, name: str, data: str) -> None:
        if name in BUILTIN_MODEL_NAMES:
            return  # the ✕ isn't drawn for these, but guard in case something else fires this
        confirm = QMessageBox.question(
            self,
            "Удалить модель",
            f"Удалить модель «{name}» безвозвратно?\nПапка {data} будет удалена с диска.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        target_dir = app_root() / data
        try:
            shutil.rmtree(target_dir)
        except OSError as exc:
            logger.error("Не удалось удалить папку модели %s: %s", target_dir, exc)
            self.status_label.setStyleSheet("color:#ff5c5c;")
            self.status_label.setText(f"Не удалось удалить: {exc}")
            return

        logger.info("Модель '%s' удалена (%s)", name, target_dir)

        # Qt auto-adjusts currentIndex when the current row is removed, which
        # would fire currentIndexChanged (-> _on_model_selected) with
        # whatever row happens to land there — block that so the fallback
        # below is the only thing driving config.overlay.model_path when the
        # deleted model was the active one.
        was_active = self.config.overlay.model_path == data
        self.model_combo.blockSignals(True)
        self.model_combo.remove_item(name)
        if was_active:
            fallback = OverlayConfig().model_path
            fallback_index = self.model_combo.findData(fallback)
            self.model_combo.setCurrentIndex(max(0, fallback_index))
        self.model_combo.blockSignals(False)

        if was_active:
            fallback = OverlayConfig().model_path
            self.config.overlay.model_path = fallback
            self.current_label.setText(f"Текущая модель: {fallback}")
            self.on_model_selected(fallback)

        # Re-syncs random_pool too: checked_names() no longer includes the
        # removed row, whether or not it happened to be checked.
        self._on_pool_check_toggled()

        # A deleted model can't stay pinned to anyone's random-weight or
        # nick binding either - see bindings_tab.py, which on_model_deleted
        # below refreshes so its own dropdowns/rows stop offering a model
        # that no longer exists.
        self.config.overlay.model_weights.pop(name, None)
        stale_nicks = [nick for nick, bound in self.config.overlay.user_model_bindings.items() if bound == name]
        for nick in stale_nicks:
            del self.config.overlay.user_model_bindings[nick]
        self.config.save()
        self.on_model_deleted(name)

        self.status_label.setStyleSheet("color:#2ecc71;")
        self.status_label.setText(f"Модель «{name}» удалена.")

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка с PNG-слоями модели")
        if not folder:
            return

        try:
            result = import_model_from_folder(Path(folder), MODELS_ROOT)
        except (ValueError, OSError) as exc:
            logger.error("Импорт модели из %s не удался: %s", folder, exc)
            self.status_label.setStyleSheet("color:#ff5c5c;")
            self.status_label.setText(f"Ошибка: {exc}")
            return

        self.config.overlay.model_path = f"assets/models/{result.model_name}"
        self.config.save()
        self.current_label.setText(f"Текущая модель: {self.config.overlay.model_path}")

        # The importer reserves a unique name, including on repeated imports.
        # Make the new model available without reopening settings.
        existing = self.model_combo.findData(self.config.overlay.model_path)
        if existing >= 0:
            self.model_combo.setCurrentIndex(existing)
        else:
            self.model_combo.add_item(result.model_name, self.config.overlay.model_path, True, deletable=True)
            self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

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

    def _open_layer_order_dialog(self) -> None:
        dialog = LayerOrderDialog(self.model, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reuses the same hot-reload path as importing a folder — it
            # already does exactly what's needed here: re-run load_model()
            # on this directory and push the fresh AvatarModel into both the
            # live overlay and this tab (-> set_model() below).
            self.on_model_imported(self.model.directory)
            self.status_label.setStyleSheet("color:#2ecc71;")
            self.status_label.setText(f"Порядок слоёв модели «{self.model.name}» обновлён.")

    def set_model(self, model: AvatarModel) -> None:
        """Keeps the preview's canvas size in sync after a hot-swapped model
        import (see main.py's on_model_imported), and keeps self.model itself
        current so "Порядок слоёв..." always edits whichever model is
        actually active right now."""
        self.model = model
        self.preview.set_model(model)
