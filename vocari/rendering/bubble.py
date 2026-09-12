"""Draws the speech bubble above the speaking avatar: the message text plus
the nickname of whoever sent it.

Everything is drawn in the model's canvas coordinate space (the same space the
avatar PNGs live in), so the bubble scales together with the avatar and the
settings stay meaningful whatever the overlay scale is.

Readability over an arbitrary stream background is the whole point of the
backdrop, so every built-in style pairs a mostly-opaque fill with a contrasting
outline, and the text gets a thin halo on top of that — a bubble that only
worked over dark scenes would be useless over a bright game.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from vocari.config.settings import BubbleConfig

# Style ids, and the human-readable names the settings tab shows.
STYLES: list[tuple[str, str]] = [
    ("cloud", "Облако (классический пузырь)"),
    ("rounded", "Скруглённый прямоугольник"),
    ("ellipse", "Овал"),
    ("glass", "Стекло (полупрозрачная плашка)"),
    ("banner", "Плашка со срезанными углами"),
    ("custom", "Своя картинка (PNG)"),
]

PADDING_X = 44.0
PADDING_Y = 34.0
NICK_GAP = 10.0  # between the nickname line and the message text
TAIL_HEIGHT = 46.0  # the little pointer aimed at the avatar
TAIL_WIDTH = 52.0
MIN_WIDTH = 220.0


# A bubble as wide as the text happens to be would come out as one very long,
# very flat strip. Instead the width is chosen from these candidates (as a
# fraction of the canvas width) — the first one that gets the message down to
# TARGET_LINES or fewer wins, so short messages get a compact bubble and long
# ones wrap into a few comfortable lines.
WIDTH_STEPS = (0.55, 0.75, 1.0, 1.25, 1.6)
TARGET_LINES = 4
MIN_TEXT_SIZE = 14  # never shrink the message below this to make it fit


@dataclass
class BubbleLayout:
    """Everything paint() needs, measured once per frame."""
    width: float
    height: float
    nick_height: float
    text_height: float
    inner_width: float
    text_size: int  # may be smaller than configured, if that's what it took to fit


def _font(family: str, size: int, bold: bool = False, italic: bool = False) -> QFont:
    font = QFont(family, -1)
    font.setPixelSize(max(1, size))
    font.setBold(bold)
    font.setItalic(italic)
    return font


def wrap_flags(metrics: QFontMetricsF, width: float, text: str) -> int:
    """Word wrapping, breaking mid-word only when a single word genuinely
    can't fit. Passing TextWrapAnywhere unconditionally would override word
    boundaries entirely and chop ordinary words in half ("день чуд|есный")."""
    flags = int(Qt.TextFlag.TextWordWrap)
    longest = max((metrics.horizontalAdvance(word) for word in text.split()), default=0.0)
    if longest > width:
        flags |= int(Qt.TextFlag.TextWrapAnywhere)
    return flags


def _wrapped_rect(metrics: QFontMetricsF, width: float, text: str) -> QRectF:
    return metrics.boundingRect(QRectF(0, 0, width, 1e6), wrap_flags(metrics, width, text), text)


def _displayed(text: str, uppercase: bool) -> str:
    """Applies the "ALL CAPS" toggle. Uppercasing changes both which glyphs
    get measured and how wide they are, so this has to run before wrapping
    is calculated (measure()), not just before painting (paint()) — the two
    must agree on the exact string or the wrap/size measure() picked won't
    match what actually gets drawn."""
    return text.upper() if uppercase else text


def measure(config: BubbleConfig, canvas_size: tuple[int, int], nick: str, text: str) -> BubbleLayout:
    """Picks the bubble's size: wide enough to read comfortably, wrapped to a
    few lines rather than one long strip, and never past the configured
    max_width/max_height. If even the widest bubble can't hold the text, the
    message font is stepped down until it fits, so the text always stays
    inside the backdrop instead of spilling over it."""
    nick = _displayed(nick, config.nick_uppercase)
    text = _displayed(text, config.text_uppercase)
    canvas_w, canvas_h = canvas_size
    max_inner = max(80.0, canvas_w * config.max_width_fraction - 2 * PADDING_X)
    max_height = max(120.0, canvas_h * config.max_height_fraction)

    nick_font = _font(config.nick_font, config.nick_size, config.nick_bold, config.nick_italic)
    nick_metrics = QFontMetricsF(nick_font)
    nick_line = nick_metrics.height() if nick else 0.0

    text_size = config.text_size
    while True:
        metrics = QFontMetricsF(_font(config.text_font, text_size))
        line_height = max(1.0, metrics.lineSpacing())

        chosen: tuple[float, QRectF] | None = None
        for fraction in WIDTH_STEPS:
            inner = min(max_inner, max(120.0, canvas_w * fraction - 2 * PADDING_X))
            rect = _wrapped_rect(metrics, inner, text)
            chosen = (inner, rect)
            if round(rect.height() / line_height) <= TARGET_LINES:
                break

        inner_candidate, text_rect = chosen  # type: ignore[misc]
        nick_width = _wrapped_rect(nick_metrics, inner_candidate, nick).width() if nick else 0.0
        inner_width = max(120.0, min(max(text_rect.width(), nick_width), max_inner))
        height = nick_line + (NICK_GAP if nick else 0.0) + text_rect.height() + 2 * PADDING_Y

        if height <= max_height or text_size <= MIN_TEXT_SIZE:
            return BubbleLayout(
                width=inner_width + 2 * PADDING_X,
                height=min(height, max_height),
                nick_height=nick_line,
                text_height=text_rect.height(),
                inner_width=inner_width,
                text_size=text_size,
            )
        text_size = max(MIN_TEXT_SIZE, int(text_size * 0.92))


def _backdrop_path(style: str, rect: QRectF, tail_at: float | None) -> QPainterPath:
    """The bubble outline. `tail_at` is the x of the pointer's tip (None for
    styles that don't have one)."""
    path = QPainterPath()

    if style == "ellipse":
        # An ellipse drawn on the text's bounding box would cut the corners of
        # that text off, since its usable area is much smaller than the box —
        # so it's inflated to wrap the same text comfortably.
        path.addEllipse(
            rect.adjusted(
                -rect.width() * 0.17, -rect.height() * 0.42,
                rect.width() * 0.17, rect.height() * 0.42,
            )
        )
    elif style == "banner":
        cut = min(28.0, rect.height() / 4)
        path.moveTo(rect.left() + cut, rect.top())
        path.lineTo(rect.right() - cut, rect.top())
        path.lineTo(rect.right(), rect.top() + cut)
        path.lineTo(rect.right(), rect.bottom() - cut)
        path.lineTo(rect.right() - cut, rect.bottom())
        path.lineTo(rect.left() + cut, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - cut)
        path.lineTo(rect.left(), rect.top() + cut)
        path.closeSubpath()
    elif style == "cloud":
        # A proper comic-book balloon: a core rounded rect with overlapping
        # lobes all the way around the perimeter, not just along the top edge
        # (bumps on one side only just read as a scalloped box).
        # Lobes need to be small relative to the body and to overlap heavily —
        # large, sparse ones read as a cog or a flower rather than a cloud.
        bump_r = max(10.0, min(rect.height() * 0.26, rect.width() * 0.095))
        core = rect.adjusted(bump_r * 0.62, bump_r * 0.62, -bump_r * 0.62, -bump_r * 0.62)
        path.addRoundedRect(core, bump_r, bump_r)

        def lobes(count: int, at) -> None:
            nonlocal path
            for index in range(count):
                t = index / max(1, count - 1)
                cx, cy = at(t)
                lobe = QPainterPath()
                # Gentle size variation: enough to look hand-drawn, not enough
                # to break the silhouette into separate blobs.
                radius = bump_r * (0.84 + 0.40 * ((index * 3) % 4) / 3)
                lobe.addEllipse(QPointF(cx, cy), radius, radius)
                path = path.united(lobe)

        step = bump_r * 1.28  # overlapping, but still visibly billowy
        across = max(4, int(core.width() / step) + 1)
        down = max(3, int(core.height() / step) + 1)
        lobes(across, lambda t: (core.left() + t * core.width(), core.top()))
        lobes(across, lambda t: (core.left() + t * core.width(), core.bottom()))
        lobes(down, lambda t: (core.left(), core.top() + t * core.height()))
        lobes(down, lambda t: (core.right(), core.top() + t * core.height()))
    else:  # "rounded", "glass", and the fallback for custom art
        radius = min(34.0, rect.height() / 3)
        path.addRoundedRect(rect, radius, radius)

    if tail_at is not None and style != "ellipse":
        tail = QPainterPath()
        tip_x = max(rect.left() + TAIL_WIDTH, min(tail_at, rect.right() - TAIL_WIDTH))
        tail.moveTo(tip_x - TAIL_WIDTH / 2, rect.bottom() - 2)
        tail.lineTo(tip_x + TAIL_WIDTH / 2, rect.bottom() - 2)
        tail.lineTo(tail_at, rect.bottom() + TAIL_HEIGHT)
        tail.closeSubpath()
        path = path.united(tail)

    return path


def paint(
    painter: QPainter,
    config: BubbleConfig,
    layout: BubbleLayout,
    origin: QPointF,
    nick: str,
    text: str,
    tail_at: float | None,
    custom_pixmap: QPixmap | None = None,
) -> None:
    """Draws the bubble with its top-left at `origin` (canvas coordinates)."""
    nick = _displayed(nick, config.nick_uppercase)
    text = _displayed(text, config.text_uppercase)
    rect = QRectF(origin.x(), origin.y(), layout.width, layout.height)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if config.style == "custom" and custom_pixmap is not None and not custom_pixmap.isNull():
        # Stretched as a 9-slice so the corners of someone's own artwork keep
        # their shape however much the text grows.
        painter.save()
        painter.setOpacity(painter.opacity() * max(0, min(100, config.opacity)) / 100.0)
        _draw_nine_slice(painter, custom_pixmap, rect)
        painter.restore()
    else:
        fill = QColor(config.background_color)
        border = QColor(config.border_color)
        path = _backdrop_path(config.style, rect, tail_at)

        if config.style == "glass":
            fill.setAlpha(max(60, min(fill.alpha(), 190)))

        # The opacity dial scales the backdrop only — the text keeps its own
        # alpha so turning the bubble see-through never costs readability.
        factor = max(0, min(100, config.opacity)) / 100.0
        fill.setAlpha(round(fill.alpha() * factor))
        border.setAlpha(round(border.alpha() * factor))
        painter.setPen(QPen(border, 3 if config.style == "glass" else 4))
        painter.setBrush(QBrush(fill))
        painter.drawPath(path)

    # -- text ---------------------------------------------------------------
    inner = QRectF(
        rect.left() + PADDING_X,
        rect.top() + PADDING_Y,
        layout.inner_width,
        rect.height() - 2 * PADDING_Y,
    )

    # The nickname + message block is centred as a whole inside the backdrop,
    # which is what keeps it looking right in shapes whose usable area isn't a
    # rectangle (the ellipse especially).
    block_height = layout.nick_height + (NICK_GAP if nick else 0.0) + layout.text_height
    y = inner.top() + max(0.0, (inner.height() - block_height) / 2)

    if nick:
        nick_font = _font(config.nick_font, config.nick_size, config.nick_bold, config.nick_italic)
        nick_rect = QRectF(inner.left(), y, inner.width(), layout.nick_height)
        _draw_text(
            painter, nick_rect, nick_font, QColor(config.nick_color), nick,
            QColor(config.nick_stroke_color), config.nick_stroke_width,
        )
        y += layout.nick_height + NICK_GAP

    text_rect = QRectF(inner.left(), y, inner.width(), layout.text_height)
    _draw_text(
        painter, text_rect, _font(config.text_font, layout.text_size), QColor(config.text_color), text,
        QColor(config.text_stroke_color), config.text_stroke_width,
    )

    painter.restore()


def _draw_text(painter: QPainter, rect: QRectF, font: QFont, color: QColor, text: str,
                stroke_color: QColor, stroke_width: int) -> None:
    """Centred, word-wrapped text with a configurable outline behind the
    fill, so it stays legible even if the fill colour happens to match the
    stream behind it. The outline is approximated by stamping the text at
    every offset on/inside a stroke_width-radius disc rather than an actual
    stroked path — cheap, and QPainter has no built-in text outline."""
    painter.setFont(font)
    flags = (
        wrap_flags(QFontMetricsF(font), rect.width(), text)
        | int(Qt.AlignmentFlag.AlignHCenter)
        | int(Qt.AlignmentFlag.AlignVCenter)
    )

    if stroke_width > 0 and stroke_color.alpha() > 0:
        painter.setPen(stroke_color)
        r = stroke_width
        r2 = r * r
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy > r2:
                    continue
                painter.drawText(rect.translated(dx, dy), flags, text)

    painter.setPen(color)
    painter.drawText(rect, flags, text)


def _draw_nine_slice(painter: QPainter, pixmap: QPixmap, rect: QRectF) -> None:
    """Stretches only the middle of `pixmap`, keeping its corners intact."""
    source_w, source_h = pixmap.width(), pixmap.height()
    cut_x = min(source_w // 3, 64)
    cut_y = min(source_h // 3, 64)
    if cut_x <= 0 or cut_y <= 0:
        painter.drawPixmap(rect, pixmap, QRectF(pixmap.rect()))
        return

    xs_src = [0, cut_x, source_w - cut_x, source_w]
    ys_src = [0, cut_y, source_h - cut_y, source_h]
    xs_dst = [rect.left(), rect.left() + cut_x, rect.right() - cut_x, rect.right()]
    ys_dst = [rect.top(), rect.top() + cut_y, rect.bottom() - cut_y, rect.bottom()]

    for col in range(3):
        for row in range(3):
            source = QRectF(
                xs_src[col], ys_src[row], xs_src[col + 1] - xs_src[col], ys_src[row + 1] - ys_src[row]
            )
            target = QRectF(
                xs_dst[col], ys_dst[row], xs_dst[col + 1] - xs_dst[col], ys_dst[row + 1] - ys_dst[row]
            )
            if target.width() > 0 and target.height() > 0:
                painter.drawPixmap(target, pixmap, source)
