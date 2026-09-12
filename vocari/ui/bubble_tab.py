"""Settings -> "Облачко": how the speech bubble looks, where it sits, and a
test button that puts a real message on stage so it can be judged in place
rather than from a description."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocari.config.settings import AppConfig
from vocari.logging_setup import get_logger
from vocari.rendering.bubble import STYLES
from vocari.tts.poems import random_poem
from vocari.tts.tts_queue import TTSQueue

logger = get_logger("settings_window")

POSITIONS: list[tuple[str, str]] = [
    ("top", "Над головой"),
    ("top-left", "Сверху слева"),
    ("top-right", "Сверху справа"),
    ("left", "Слева от аватара"),
    ("right", "Справа от аватара"),
]

DEFAULT_TEST_NICK = "sirdimitry"


class ColorButton(QPushButton):
    """A button that shows its colour and opens the colour picker (with an
    alpha channel — the bubble fill leans on transparency)."""

    def __init__(self, initial: str, on_changed: Callable[[str], None]):
        super().__init__()
        self.on_changed = on_changed
        self._color = QColor(initial)
        self.setFixedWidth(120)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self) -> None:
        self.setText(self._color.name(QColor.NameFormat.HexArgb))
        text_color = "#000000" if self._color.lightnessF() > 0.5 else "#ffffff"
        self.setStyleSheet(
            f"background-color: {self._color.name()}; color: {text_color}; padding: 4px;"
        )

    def _pick(self) -> None:
        color = QColorDialog.getColor(
            self._color, self, "Цвет", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._color = color
            self._refresh()
            self.on_changed(color.name(QColor.NameFormat.HexArgb))


class BubbleTab(QWidget):
    def __init__(
        self,
        config: AppConfig,
        on_changed: Callable[[], None],
        tts_queue: TTSQueue,
    ):
        super().__init__()
        self.config = config
        self.on_changed = on_changed
        self.tts_queue = tts_queue

        root = QVBoxLayout(self)
        root.addWidget(self._build_test_group())

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_look_group(), 1)
        columns.addWidget(self._build_text_group(), 1)
        root.addLayout(columns)

        root.addWidget(self._build_placement_group())
        root.addStretch()

    # -- sections ---------------------------------------------------------

    def _build_test_group(self) -> QGroupBox:
        box = QGroupBox("Тест сообщения")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        self.test_nick = QLineEdit(DEFAULT_TEST_NICK)
        form.addRow("Ник отправителя:", self.test_nick)
        layout.addLayout(form)

        self.test_text = QPlainTextEdit(random_poem())
        self.test_text.setMaximumHeight(70)
        layout.addWidget(self.test_text)

        row = QHBoxLayout()
        test_button = QPushButton("Тест — выпустить аватара с этим сообщением")
        test_button.clicked.connect(self._on_test_clicked)
        row.addWidget(test_button)
        another = QPushButton("Другой стишок")
        another.clicked.connect(lambda: self.test_text.setPlainText(random_poem()))
        row.addWidget(another)
        layout.addLayout(row)

        self.preview_button = QPushButton("Держать облачко на экране для настройки")
        self.preview_button.setCheckable(True)
        self.preview_button.toggled.connect(self._on_preview_toggled)
        layout.addWidget(self.preview_button)

        # Live-edit the parked preview as the text/nick are typed.
        self.test_text.textChanged.connect(self._refresh_preview_message)
        self.test_nick.textChanged.connect(self._refresh_preview_message)

        hint = QLabel(
            "«Тест» — полный цикл как при обычном сообщении: приедет, поднимется "
            "облачко, прозвучит озвучка, облачко пропадёт и только потом аватар "
            "уедет.\n"
            "«Держать на экране» — аватар выезжает и остаётся с облачком, пока "
            "кнопка нажата: меняйте форму, цвета, прозрачность, шрифты — всё видно "
            "сразу, без озвучки."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        return box

    def _build_look_group(self) -> QGroupBox:
        box = QGroupBox("Вид подложки")
        layout = QVBoxLayout(box)

        enabled_row = QHBoxLayout()
        self.enabled_check = QCheckBox("Показывать облачко с текстом")
        self.enabled_check.setChecked(self.config.bubble.enabled)
        self.enabled_check.toggled.connect(self._on_enabled_toggled)
        enabled_row.addWidget(self.enabled_check)
        layout.addLayout(enabled_row)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.style_combo = QComboBox()
        for style_id, title in STYLES:
            self.style_combo.addItem(title, style_id)
        index = self.style_combo.findData(self.config.bubble.style)
        self.style_combo.setCurrentIndex(max(0, index))
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        form.addRow("Форма:", self.style_combo)

        self.custom_row = QHBoxLayout()
        self.custom_label = QLineEdit(self.config.bubble.custom_image)
        self.custom_label.setReadOnly(True)
        self.custom_label.setPlaceholderText("PNG не выбран")
        choose = QPushButton("Выбрать…")
        choose.clicked.connect(self._choose_custom_image)
        self.custom_row.addWidget(self.custom_label)
        self.custom_row.addWidget(choose)
        custom_widget = QWidget()
        custom_widget.setLayout(self.custom_row)
        form.addRow("Своя картинка:", custom_widget)

        self.fill_button = ColorButton(self.config.bubble.background_color, self._on_fill_changed)
        form.addRow("Цвет подложки:", self.fill_button)

        self.border_button = ColorButton(self.config.bubble.border_color, self._on_border_changed)
        form.addRow("Цвет обводки:", self.border_button)

        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(self.config.bubble.opacity)
        self.opacity_readout = QLabel(f"{self.config.bubble.opacity} %")
        self.opacity_readout.setMinimumWidth(44)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)
        opacity_row.addWidget(self.opacity_readout)
        opacity_widget = QWidget()
        opacity_widget.setLayout(opacity_row)
        form.addRow("Непрозрачность:", opacity_widget)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 2.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(self.config.bubble.scale)
        self.scale_spin.valueChanged.connect(self._on_scale_changed)
        form.addRow("Размер:", self.scale_spin)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(self.config.bubble.appear_speed)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        form.addRow("Скорость появления:", self.speed_slider)
        layout.addLayout(form)

        hint = QLabel(
            "Пять встроенных форм: «Облако» — классический пузырь с бугорками и "
            "хвостиком к аватару; «Скруглённый прямоугольник» — самый нейтральный, "
            "лучше всего для длинных сообщений; «Овал» — мягкий, без хвостика; "
            "«Стекло» — полупрозрачная плашка с тонкой рамкой, почти не закрывает "
            "фон; «Плашка со срезанными углами» — строгий вариант. Своя картинка "
            "растягивается по краям (9-slice): углы остаются как есть, тянется "
            "только середина, так что PNG лучше делать с запасом по краям.\n"
            "Размер облачка подстраивается под текст автоматически, но не "
            "больше ~1.6 ширины аватара — длинный текст переносится по словам."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch()
        self._sync_custom_row()
        return box

    def _build_text_group(self) -> QGroupBox:
        box = QGroupBox("Текст и ник")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.text_font = QFontComboBox()
        self.text_font.setCurrentFont(self.config.bubble.text_font)
        self.text_font.currentFontChanged.connect(
            lambda f: self._set("text_font", f.family())
        )
        form.addRow("Шрифт сообщения:", self.text_font)

        self.text_size = QSpinBox()
        self.text_size.setRange(10, 200)
        self.text_size.setValue(self.config.bubble.text_size)
        self.text_size.valueChanged.connect(lambda v: self._set("text_size", v))
        form.addRow("Размер сообщения:", self.text_size)

        self.text_color = ColorButton(
            self.config.bubble.text_color, lambda c: self._set("text_color", c)
        )
        form.addRow("Цвет сообщения:", self.text_color)

        self.nick_font = QFontComboBox()
        self.nick_font.setCurrentFont(self.config.bubble.nick_font)
        self.nick_font.currentFontChanged.connect(
            lambda f: self._set("nick_font", f.family())
        )
        form.addRow("Шрифт ника:", self.nick_font)

        self.nick_size = QSpinBox()
        self.nick_size.setRange(10, 200)
        self.nick_size.setValue(self.config.bubble.nick_size)
        self.nick_size.valueChanged.connect(lambda v: self._set("nick_size", v))
        form.addRow("Размер ника:", self.nick_size)

        self.nick_color = ColorButton(
            self.config.bubble.nick_color, lambda c: self._set("nick_color", c)
        )
        form.addRow("Цвет ника:", self.nick_color)

        style_row = QHBoxLayout()
        self.nick_bold = QCheckBox("Жирный")
        self.nick_bold.setChecked(self.config.bubble.nick_bold)
        self.nick_bold.toggled.connect(lambda v: self._set("nick_bold", v))
        self.nick_italic = QCheckBox("Курсив")
        self.nick_italic.setChecked(self.config.bubble.nick_italic)
        self.nick_italic.toggled.connect(lambda v: self._set("nick_italic", v))
        style_row.addWidget(self.nick_bold)
        style_row.addWidget(self.nick_italic)
        style_row.addStretch()
        style_widget = QWidget()
        style_widget.setLayout(style_row)
        form.addRow("Начертание ника:", style_widget)
        layout.addLayout(form)

        hint = QLabel(
            "Размеры заданы в пикселях холста модели, а не экрана — поэтому текст "
            "масштабируется вместе с аватаром и не приходится подбирать его заново "
            "после изменения масштаба оверлея. У текста есть тонкая контурная "
            "подсветка, чтобы он читался даже поверх пёстрого фона."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch()
        return box

    def _build_placement_group(self) -> QGroupBox:
        box = QGroupBox("Положение")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.position_combo = QComboBox()
        for position_id, title in POSITIONS:
            self.position_combo.addItem(title, position_id)
        index = self.position_combo.findData(self.config.bubble.position)
        self.position_combo.setCurrentIndex(max(0, index))
        self.position_combo.currentIndexChanged.connect(
            lambda: self._set("position", self.position_combo.currentData())
        )
        form.addRow("Относительно аватара:", self.position_combo)

        offset_row = QHBoxLayout()
        self.offset_x = QSpinBox()
        self.offset_x.setRange(-2000, 2000)
        self.offset_x.setValue(self.config.bubble.offset_x)
        self.offset_x.valueChanged.connect(lambda v: self._set("offset_x", v))
        self.offset_y = QSpinBox()
        self.offset_y.setRange(-2000, 2000)
        self.offset_y.setValue(self.config.bubble.offset_y)
        self.offset_y.valueChanged.connect(lambda v: self._set("offset_y", v))
        offset_row.addWidget(QLabel("X:"))
        offset_row.addWidget(self.offset_x)
        offset_row.addWidget(QLabel("Y:"))
        offset_row.addWidget(self.offset_y)
        offset_row.addStretch()
        offset_widget = QWidget()
        offset_widget.setLayout(offset_row)
        form.addRow("Сдвиг:", offset_widget)
        layout.addLayout(form)

        hint = QLabel(
            "Облачко привязано к аватару, а не к экрану, поэтому оно едет вместе с "
            "ним и одинаково работает для любой позиции оверлея. Место на экране "
            "задаётся позицией самого аватара (вкладка «Модель» — превью и X/Y), "
            "а «Сдвиг» здесь двигает облачко относительно головы в пикселях холста."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        return box

    # -- handlers ---------------------------------------------------------

    def _set(self, field: str, value) -> None:
        setattr(self.config.bubble, field, value)
        self.config.save()
        self.on_changed()

    def _on_enabled_toggled(self, checked: bool) -> None:
        self._set("enabled", checked)
        logger.info("Облачко с текстом: %s", "включено" if checked else "выключено")

    def _on_style_changed(self) -> None:
        self._set("style", self.style_combo.currentData())
        self._sync_custom_row()

    def _on_fill_changed(self, color: str) -> None:
        self._set("background_color", color)

    def _on_border_changed(self, color: str) -> None:
        self._set("border_color", color)

    def _on_scale_changed(self, value: float) -> None:
        self._set("scale", value)

    def _on_speed_changed(self, value: int) -> None:
        self._set("appear_speed", value)

    def _on_opacity_changed(self, value: int) -> None:
        self.opacity_readout.setText(f"{value} %")
        self._set("opacity", value)

    def _on_preview_toggled(self, checked: bool) -> None:
        if checked:
            self.tts_queue.show_bubble_preview(self._current_message())
            self.preview_button.setText("Убрать облачко с экрана")
        else:
            self.tts_queue.hide_bubble_preview()
            self.preview_button.setText("Держать облачко на экране для настройки")

    def _refresh_preview_message(self) -> None:
        if self.preview_button.isChecked():
            self.tts_queue.update_bubble_preview(self._current_message())

    def _current_message(self) -> tuple[str, str]:
        text = self.test_text.toPlainText().strip() or random_poem()
        return text, self.test_nick.text().strip()

    def _sync_custom_row(self) -> None:
        is_custom = self.config.bubble.style == "custom"
        self.custom_label.setEnabled(is_custom)

    def _choose_custom_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Картинка подложки", "", "Изображения (*.png *.webp *.jpg)"
        )
        if not path:
            return
        self.custom_label.setText(path)
        self._set("custom_image", path)
        logger.info("Облачко: выбрана своя картинка подложки")

    def _on_test_clicked(self) -> None:
        text = self.test_text.toPlainText().strip() or random_poem()
        nick = self.test_nick.text().strip()
        self.tts_queue.enqueue(text, nick)
        logger.info("Тест облачка: '%s' от '%s'", text, nick or "—")
