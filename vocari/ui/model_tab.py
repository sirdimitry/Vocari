"""Settings -> "Модель": import a model folder, and adjust overlay
position/scale without needing to drag/scroll the transparent window itself."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.rendering.model_import import import_model_from_folder

logger = get_logger("settings_window")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_ROOT = PROJECT_ROOT / "assets" / "models"

POSITION_RANGE = 20000  # generous bound for multi-monitor setups
MIN_SCALE_PERCENT = 10
MAX_SCALE_PERCENT = 500


class ModelTab(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_model_imported: Callable[[Path], None],
        on_position_changed: Callable[[int, int], None],
        on_scale_changed: Callable[[float], None],
    ):
        super().__init__()
        self.config = config
        self.on_model_imported = on_model_imported
        self.on_position_changed = on_position_changed
        self.on_scale_changed = on_scale_changed

        layout = QVBoxLayout(self)

        self.current_label = QLabel(f"Текущая модель: {config.overlay.model_path}")
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

        geometry_label = QLabel("Позиция и масштаб оверлея")
        geometry_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(geometry_label)

        geometry_hint = QLabel("То же самое можно менять прямо на аватаре: перетаскивание мышью и колесо.")
        geometry_hint.setWordWrap(True)
        geometry_hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(geometry_hint)

        form = QFormLayout()
        self.pos_x_spin = QSpinBox()
        self.pos_x_spin.setRange(-POSITION_RANGE, POSITION_RANGE)
        self.pos_x_spin.setValue(config.overlay.pos_x)
        form.addRow("X:", self.pos_x_spin)

        self.pos_y_spin = QSpinBox()
        self.pos_y_spin.setRange(-POSITION_RANGE, POSITION_RANGE)
        self.pos_y_spin.setValue(config.overlay.pos_y)
        form.addRow("Y:", self.pos_y_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(MIN_SCALE_PERCENT, MAX_SCALE_PERCENT)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setValue(config.overlay.scale * 100)
        form.addRow("Масштаб:", self.scale_spin)
        layout.addLayout(form)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        apply_button = QPushButton("Применить")
        apply_button.clicked.connect(self._apply_geometry)
        apply_row.addWidget(apply_button)
        layout.addLayout(apply_row)

        layout.addStretch()

    def _apply_geometry(self) -> None:
        x, y = self.pos_x_spin.value(), self.pos_y_spin.value()
        scale = self.scale_spin.value() / 100.0
        self.on_position_changed(x, y)
        self.on_scale_changed(scale)
        self.config.save()
        logger.info("Позиция/масштаб оверлея изменены из настроек: (%d, %d), %.0f%%", x, y, scale * 100)

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
