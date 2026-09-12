"""Draws the bundled avatar models as layered PNGs.

Every model follows the same contract as the hand-drawn Ariral one (see
rendering/model.py): one shared 1280x1280 canvas, one PNG per layer, plus
open/closed variants for the eyes and mouth. Keeping the canvas identical
across models matters — the stage positions every avatar from the same
canvas size, so a model with a different one would sit at a different height.

Run:  .venv\\Scripts\\python.exe tools\\generate_models.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

CANVAS = 1280
OUT_ROOT = Path(__file__).resolve().parent.parent / "assets" / "models"

INK = QColor("#22201f")  # shared outline colour; flat art with a dark keyline


def new_layer() -> QImage:
    image = QImage(CANVAS, CANVAS, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    return image


def painter_for(image: QImage) -> QPainter:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return painter


def pen(width: float = 7.0, color: QColor | None = None) -> QPen:
    p = QPen(color or INK, width)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    return p


def shade(base: QColor, rect: QRectF, lighten: int = 28, darken: int = 26) -> QBrush:
    """Soft top-lit gradient so flat shapes still read as volumes."""
    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, base.lighter(100 + lighten))
    gradient.setColorAt(0.55, base)
    gradient.setColorAt(1.0, base.darker(100 + darken))
    return QBrush(gradient)


def save(image: QImage, folder: Path, name: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    image.save(str(folder / name))
    return name


def write_manifest(folder: Path, name: str, base_layers: list[str], states: dict,
                   sway: list[str], bounce: list[str]) -> None:
    manifest = {
        "name": name,
        "canvas": [CANVAS, CANVAS],
        "base_layers": base_layers,
        "states": states,
        "sway_layers": sway,
        "bounce_react_layers": bounce,
    }
    (folder / "model.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------- helpers --

def draw_torso(painter: QPainter, shirt: QColor, collar: QColor, neck: QColor) -> None:
    """Shoulders/chest wedge shared by all three models. Deliberately narrow
    and low: these are bust-style avatars, and a wide torso starting high up
    makes the head — which is what actually emotes — read as tiny."""
    painter.setPen(pen(8))
    painter.setBrush(QBrush(neck))
    painter.drawRoundedRect(QRectF(578, 700, 124, 170), 42, 42)

    body = QPainterPath()
    body.moveTo(640, 830)
    body.cubicTo(470, 862, 396, 966, 372, 1280)
    body.lineTo(908, 1280)
    body.cubicTo(884, 966, 810, 862, 640, 830)
    painter.setBrush(shade(shirt, QRectF(372, 830, 536, 450)))
    painter.drawPath(body)

    lapel = QPainterPath()
    lapel.moveTo(640, 836)
    lapel.lineTo(566, 902)
    lapel.lineTo(640, 1064)
    lapel.lineTo(714, 902)
    lapel.closeSubpath()
    painter.setBrush(QBrush(collar))
    painter.drawPath(lapel)


def blink_lids(painter: QPainter, skin: QColor, centers: list[QPointF], w: float, h: float) -> None:
    """Closed eyes: a skin-toned lid with a lash line under it."""
    painter.setPen(pen(7))
    painter.setBrush(QBrush(skin))
    for c in centers:
        painter.drawEllipse(c, w, h)
    painter.setPen(pen(9))
    for c in centers:
        painter.drawLine(QPointF(c.x() - w, c.y()), QPointF(c.x() + w, c.y()))


# ------------------------------------------------------------------- orc ---

def build_orc(folder: Path) -> None:
    skin = QColor("#7cb342")
    skin_dark = QColor("#4e7d22")
    shirt = QColor("#6d4c33")
    layers: list[str] = []

    # 01 back hair / topknot
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    p.setBrush(QBrush(QColor("#2b2118")))
    p.drawEllipse(QPointF(640, 240), 132, 96)
    p.drawRoundedRect(QRectF(598, 116, 84, 150), 38, 38)
    p.end()
    layers.append(save(img, folder, "01Back.png"))

    # 02 body
    img = new_layer()
    p = painter_for(img)
    draw_torso(p, shirt, QColor("#55402c"), skin_dark)
    # shoulder straps
    p.setBrush(QBrush(QColor("#8d6742")))
    p.drawRoundedRect(QRectF(360, 900, 560, 60), 26, 26)
    p.end()
    layers.append(save(img, folder, "02Body.png"))

    # 03/12 ears (bounce-react)
    for name, sign in (("03Ear_Right.png", -1), ("12Ear_Left.png", 1)):
        img = new_layer()
        p = painter_for(img)
        p.setPen(pen(8))
        p.setBrush(QBrush(skin))
        ear = QPainterPath()
        base_x = 640 + sign * 268
        ear.moveTo(base_x, 400)
        ear.cubicTo(base_x + sign * 170, 286, base_x + sign * 196, 470, base_x + sign * 74, 556)
        ear.cubicTo(base_x + sign * 36, 574, base_x - sign * 6, 500, base_x, 400)
        p.drawPath(ear)
        p.end()
        layers.append(save(img, folder, name))

    # 05 head with a heavy jaw
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    head = QPainterPath()
    head.moveTo(372, 430)
    head.cubicTo(372, 196, 908, 196, 908, 430)
    head.cubicTo(932, 640, 830, 790, 640, 800)   # heavy, wide jaw
    head.cubicTo(450, 790, 348, 640, 372, 430)
    p.setBrush(shade(skin, QRectF(372, 196, 536, 604)))
    p.drawPath(head)
    # brow ridge
    p.setBrush(QBrush(skin.darker(115)))
    p.setPen(Qt.PenStyle.NoPen)
    ridge = QPainterPath()
    ridge.moveTo(396, 424)
    ridge.cubicTo(490, 344, 790, 344, 884, 424)
    ridge.cubicTo(790, 392, 490, 392, 396, 424)
    p.drawPath(ridge)
    # snout
    p.setPen(pen(7))
    p.setBrush(QBrush(skin.darker(108)))
    snout = QPainterPath()
    snout.moveTo(640, 470)
    snout.cubicTo(560, 548, 566, 606, 640, 612)
    snout.cubicTo(714, 606, 720, 548, 640, 470)
    p.drawPath(snout)
    p.setPen(pen(6, skin.darker(140)))
    for sign in (-1, 1):
        p.drawEllipse(QPointF(640 + sign * 28, 578), 13, 10)
    # warts
    p.setPen(pen(5))
    p.setBrush(QBrush(skin.darker(125)))
    for cx, cy, r in ((470, 552, 22), (436, 632, 15), (830, 588, 19), (768, 268, 14), (520, 700, 13)):
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.end()
    layers.append(save(img, folder, "05Head.png"))

    # 08 angry brows
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(16, QColor("#2b2118")))
    p.drawLine(QPointF(452, 372), QPointF(594, 436))
    p.drawLine(QPointF(828, 372), QPointF(686, 436))
    p.end()
    layers.append(save(img, folder, "08Brows.png"))

    # 06/07 eyes
    centers = [QPointF(528, 478), QPointF(752, 478)]
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7))
    p.setBrush(QBrush(QColor("#fff4c8")))
    for c in centers:
        p.drawEllipse(c, 70, 52)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#c0392b")))
    for c in centers:
        p.drawEllipse(c.x() - 12 if c.x() < 640 else c.x() + 12, c.y() - 2, 34, 34)
    p.setBrush(QBrush(INK))
    for c in centers:
        p.drawEllipse(c.x() - 4 if c.x() < 640 else c.x() + 4, c.y() + 4, 15, 15)
    p.end()
    layers.append(save(img, folder, "06Eyes_Open.png"))

    img = new_layer()
    p = painter_for(img)
    blink_lids(p, skin, centers, 70, 52)
    p.end()
    layers.append(save(img, folder, "07Eyes_Closed.png"))

    # 09/10 mouth with tusks
    def tusks(p: QPainter) -> None:
        p.setPen(pen(7))
        p.setBrush(QBrush(QColor("#f7f3e3")))
        for sign in (-1, 1):
            tusk = QPolygonF([
                QPointF(640 + sign * 86, 700),
                QPointF(640 + sign * 132, 710),
                QPointF(640 + sign * 104, 576),
            ])
            p.drawPolygon(tusk)

    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    p.setBrush(QBrush(QColor("#5a1f22")))
    mouth = QPainterPath()
    mouth.moveTo(506, 660)
    mouth.cubicTo(640, 770, 640, 770, 774, 660)
    mouth.cubicTo(706, 630, 574, 630, 506, 660)
    p.drawPath(mouth)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#e88a8a")))
    p.drawEllipse(QPointF(640, 722), 58, 24)
    tusks(p)
    p.end()
    layers.append(save(img, folder, "09Mouth_Open.png"))

    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(9))
    p.setBrush(Qt.BrushStyle.NoBrush)
    grin = QPainterPath()
    grin.moveTo(516, 656)
    grin.cubicTo(640, 700, 640, 700, 764, 656)
    p.drawPath(grin)
    tusks(p)
    p.end()
    layers.append(save(img, folder, "10Mouth_Closed.png"))

    # 16 drool (sways)
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(6, QColor("#8fd4e8")))
    p.setBrush(QBrush(QColor("#cfefff")))
    drip = QPainterPath()
    drip.moveTo(742, 706)
    drip.cubicTo(760, 764, 756, 818, 742, 854)
    drip.cubicTo(728, 818, 724, 764, 742, 706)
    p.drawPath(drip)
    p.drawEllipse(QPointF(742, 880), 18, 23)
    p.end()
    layers.append(save(img, folder, "16Drool.png"))

    write_manifest(
        folder, "Orc",
        ["01Back.png", "02Body.png", "03Ear_Right.png", "12Ear_Left.png", "05Head.png",
         "08Brows.png", "16Drool.png"],
        {
            "eyes": {"order": 5, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
            "mouth": {"order": 6, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
        },
        ["16Drool.png"],
        ["03Ear_Right.png", "12Ear_Left.png"],
    )


# --------------------------------------------------------------- ranger ----

def build_ranger(folder: Path) -> None:
    """An original hero-shooter style fighter: helmet, glowing visor, armour.
    Deliberately not any specific published character — same genre language,
    own design."""
    armour = QColor("#3c4a63")
    accent = QColor("#ff8a3d")
    skin = QColor("#f0c9a4")
    layers: list[str] = []

    # 01 backpack / thrusters
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    p.setBrush(QBrush(armour.darker(125)))
    p.drawRoundedRect(QRectF(410, 862, 460, 260), 56, 56)
    p.setBrush(QBrush(accent))
    p.drawEllipse(QPointF(440, 980), 30, 30)
    p.drawEllipse(QPointF(840, 980), 30, 30)
    p.end()
    layers.append(save(img, folder, "01Pack.png"))

    # 02 body
    img = new_layer()
    p = painter_for(img)
    draw_torso(p, armour, accent.darker(115), skin.darker(112))
    p.setPen(pen(7))
    p.setBrush(QBrush(armour.lighter(118)))
    p.drawRoundedRect(QRectF(516, 954, 248, 104), 30, 30)
    p.setBrush(QBrush(accent))
    p.drawEllipse(QPointF(640, 1006), 30, 30)
    p.end()
    layers.append(save(img, folder, "02Body.png"))

    # 03/12 shoulder pads (bounce-react)
    for name, sign in (("03Pad_Right.png", -1), ("12Pad_Left.png", 1)):
        img = new_layer()
        p = painter_for(img)
        p.setPen(pen(8))
        p.setBrush(shade(armour.lighter(112), QRectF(300, 820, 300, 200)))
        cx = 640 + sign * 272
        p.drawRoundedRect(QRectF(cx - 92, 906, 184, 140), 52, 52)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(QRectF(cx - 58, 936, 116, 22), 11, 11)
        p.end()
        layers.append(save(img, folder, name))

    # 05 head + helmet
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    p.setBrush(shade(skin, QRectF(400, 214, 480, 578)))
    face = QPainterPath()
    face.moveTo(400, 452)
    face.cubicTo(400, 214, 880, 214, 880, 452)
    face.cubicTo(892, 654, 800, 780, 640, 792)
    face.cubicTo(480, 780, 388, 654, 400, 452)
    p.drawPath(face)
    # helmet shell
    p.setBrush(shade(armour, QRectF(376, 196, 528, 300)))
    helmet = QPainterPath()
    helmet.moveTo(386, 486)
    helmet.cubicTo(376, 196, 904, 196, 894, 486)
    helmet.lineTo(836, 486)
    helmet.cubicTo(844, 296, 436, 296, 444, 486)
    helmet.closeSubpath()
    p.drawPath(helmet)
    p.setBrush(QBrush(accent))
    p.drawRoundedRect(QRectF(608, 200, 64, 130), 26, 26)
    p.end()
    layers.append(save(img, folder, "05Head.png"))

    # 08 visor frame
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(8))
    p.setBrush(QBrush(armour.darker(115)))
    p.drawRoundedRect(QRectF(432, 436, 416, 104), 46, 46)
    p.end()
    layers.append(save(img, folder, "08Visor.png"))

    # 06/07 "eyes" = the glowing visor band
    img = new_layer()
    p = painter_for(img)
    glow = QRadialGradient(QPointF(640, 488), 220)
    glow.setColorAt(0.0, QColor("#8ff4ff"))
    glow.setColorAt(0.6, QColor("#37c8f0"))
    glow.setColorAt(1.0, QColor("#1d7fa8"))
    p.setPen(pen(5, QColor("#0f5f80")))
    p.setBrush(QBrush(glow))
    p.drawRoundedRect(QRectF(452, 452, 376, 72), 34, 34)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255, 150)))
    p.drawRoundedRect(QRectF(486, 464, 130, 18), 9, 9)
    p.end()
    layers.append(save(img, folder, "06Eyes_Open.png"))

    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(5, QColor("#0f5f80")))
    p.setBrush(QBrush(QColor("#1b4759")))
    p.drawRoundedRect(QRectF(452, 478, 376, 22), 11, 11)
    p.end()
    layers.append(save(img, folder, "07Eyes_Closed.png"))

    # 09/10 mouth (breather grille)
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7))
    p.setBrush(QBrush(QColor("#2f3a4d")))
    p.drawRoundedRect(QRectF(542, 622, 196, 118), 38, 38)
    p.setPen(pen(6, QColor("#8ea3c4")))
    for y in (658, 686, 714):
        p.drawLine(QPointF(566, y), QPointF(714, y))
    p.end()
    layers.append(save(img, folder, "09Mouth_Open.png"))

    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7))
    p.setBrush(QBrush(QColor("#2f3a4d")))
    p.drawRoundedRect(QRectF(542, 648, 196, 68), 30, 30)
    p.setPen(pen(6, QColor("#8ea3c4")))
    p.drawLine(QPointF(566, 682), QPointF(714, 682))
    p.end()
    layers.append(save(img, folder, "10Mouth_Closed.png"))

    # 16 antenna (sways)
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(9, armour.darker(120)))
    antenna = QPainterPath()
    antenna.moveTo(834, 300)
    antenna.cubicTo(898, 214, 916, 146, 900, 96)
    p.drawPath(antenna)
    p.setPen(pen(5, accent.darker(120)))
    p.setBrush(QBrush(accent))
    p.drawEllipse(QPointF(900, 88), 22, 22)
    p.end()
    layers.append(save(img, folder, "16Antenna.png"))

    write_manifest(
        folder, "Ranger",
        ["01Pack.png", "02Body.png", "03Pad_Right.png", "12Pad_Left.png", "05Head.png",
         "08Visor.png", "16Antenna.png"],
        {
            "eyes": {"order": 6, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
            "mouth": {"order": 6, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
        },
        ["16Antenna.png"],
        ["03Pad_Right.png", "12Pad_Left.png"],
    )


# ------------------------------------------------------------ programmer ---

def build_coder(folder: Path) -> None:
    """The least cartoonish of the three — closer-to-life proportions, smaller
    eyes, muted palette. Styled from the reference the user supplied: dark
    blond hair swept back, a long pointed goatee joined to a moustache,
    grey-blue eyes, denim jacket over a dark tee."""
    skin = QColor("#e3b088")
    hair = QColor("#b09268")       # dark blond
    hair_dark = QColor("#8a7150")
    denim = QColor("#5b7ea6")
    tee = QColor("#2b2b31")
    layers: list[str] = []

    # 01 hair behind (volume at the back/sides)
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7, hair_dark.darker(120)))
    p.setBrush(QBrush(hair_dark))
    p.drawEllipse(QPointF(640, 448), 268, 282)
    p.end()
    layers.append(save(img, folder, "01HairBehind.png"))

    # 02 denim jacket over a dark tee
    img = new_layer()
    p = painter_for(img)
    draw_torso(p, tee, tee.darker(112), skin.darker(110))
    p.setPen(pen(8))
    p.setBrush(shade(denim, QRectF(300, 760, 680, 520), 22, 24))
    for sign in (-1, 1):
        panel = QPainterPath()
        panel.moveTo(640 + sign * 70, 790)
        panel.cubicTo(640 + sign * 250, 800, 640 + sign * 330, 900, 640 + sign * 350, 1280)
        panel.lineTo(640 + sign * 70, 1280)
        panel.closeSubpath()
        p.drawPath(panel)
    # collar
    p.setBrush(QBrush(denim.lighter(115)))
    for sign in (-1, 1):
        collar = QPainterPath()
        collar.moveTo(640 + sign * 66, 782)
        collar.lineTo(640 + sign * 232, 812)
        collar.lineTo(640 + sign * 150, 906)
        collar.closeSubpath()
        p.drawPath(collar)
    # stitching
    p.setPen(pen(4, QColor("#e8dcc0")))
    for sign in (-1, 1):
        p.drawLine(QPointF(640 + sign * 96, 900), QPointF(640 + sign * 120, 1270))
    p.end()
    layers.append(save(img, folder, "02Body.png"))

    # 03/12 ears (bounce-react)
    for name, sign in (("03Ear_Right.png", -1), ("12Ear_Left.png", 1)):
        img = new_layer()
        p = painter_for(img)
        p.setPen(pen(7))
        p.setBrush(QBrush(skin.darker(107)))
        p.drawEllipse(QPointF(640 + sign * 274, 534), 34, 52)
        p.end()
        layers.append(save(img, folder, name))

    # 05 head — broader jaw, fuller cheeks than the other two
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7))
    p.setBrush(shade(skin, QRectF(414, 232, 452, 574), 16, 20))
    face = QPainterPath()
    face.moveTo(414, 460)
    face.cubicTo(414, 232, 866, 232, 866, 460)
    face.cubicTo(874, 648, 776, 788, 640, 806)
    face.cubicTo(504, 788, 406, 648, 414, 460)
    p.drawPath(face)
    # nose
    p.setPen(pen(6, skin.darker(126)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    nose = QPainterPath()
    nose.moveTo(642, 486)
    nose.cubicTo(620, 566, 610, 592, 652, 598)
    p.drawPath(nose)
    # smile lines / cheeks
    p.setPen(pen(5, skin.darker(118)))
    for sign in (-1, 1):
        crease = QPainterPath()
        crease.moveTo(640 + sign * 112, 572)
        crease.cubicTo(640 + sign * 136, 624, 640 + sign * 122, 658, 640 + sign * 100, 672)
        p.drawPath(crease)
    p.end()
    layers.append(save(img, folder, "05Head.png"))

    # 08 swept-back hair + brows
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7, hair_dark))
    p.setBrush(shade(hair, QRectF(392, 234, 496, 250), 18, 16))
    top = QPainterPath()
    top.moveTo(410, 476)
    top.cubicTo(392, 234, 888, 234, 870, 476)
    top.cubicTo(848, 384, 776, 334, 676, 360)
    top.cubicTo(560, 390, 456, 396, 410, 476)
    p.drawPath(top)
    # a few swept strands, to read as "combed back" rather than a helmet
    p.setPen(pen(6, hair_dark))
    for x0, y0, x1, y1 in ((476, 340, 578, 282), (578, 306, 692, 270), (692, 282, 806, 320)):
        strand = QPainterPath()
        strand.moveTo(x0, y0)
        strand.cubicTo((x0 + x1) / 2, y0 - 34, (x0 + x1) / 2, y1 - 10, x1, y1)
        p.drawPath(strand)
    # brows
    p.setPen(pen(12, hair_dark.darker(112)))
    p.drawLine(QPointF(494, 478), QPointF(596, 470))
    p.drawLine(QPointF(786, 478), QPointF(684, 470))
    p.end()
    layers.append(save(img, folder, "08Hair.png"))

    # 06/07 eyes — grey-blue, calm
    centers = [QPointF(552, 522), QPointF(728, 522)]
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(6))
    p.setBrush(QBrush(QColor("#fbfbfa")))
    for c in centers:
        p.drawEllipse(c, 50, 32)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#7e9bb0")))
    for c in centers:
        p.drawEllipse(c, 23, 23)
    p.setBrush(QBrush(INK))
    for c in centers:
        p.drawEllipse(c, 10, 10)
    p.setBrush(QBrush(QColor(255, 255, 255, 225)))
    for c in centers:
        p.drawEllipse(QPointF(c.x() - 7, c.y() - 8), 6, 6)
    # upper lash line
    p.setPen(pen(5, INK))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for c in centers:
        p.drawArc(QRectF(c.x() - 50, c.y() - 34, 100, 64), 20 * 16, 140 * 16)
    p.end()
    layers.append(save(img, folder, "06Eyes_Open.png"))

    img = new_layer()
    p = painter_for(img)
    blink_lids(p, skin, centers, 50, 32)
    p.end()
    layers.append(save(img, folder, "07Eyes_Closed.png"))

    # 09/10 mouth, sitting inside the moustache/goatee
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(6))
    p.setBrush(QBrush(QColor("#8a4444")))
    p.drawEllipse(QPointF(640, 664), 46, 32)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#f4f0e8")))
    p.drawRoundedRect(QRectF(606, 640, 68, 14), 6, 6)
    p.end()
    layers.append(save(img, folder, "09Mouth_Open.png"))

    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(7))
    p.setBrush(Qt.BrushStyle.NoBrush)
    line = QPainterPath()
    line.moveTo(598, 658)
    line.cubicTo(640, 678, 640, 678, 682, 658)
    p.drawPath(line)
    p.end()
    layers.append(save(img, folder, "10Mouth_Closed.png"))

    # 13 goatee + moustache — the signature feature
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(6, hair_dark))
    p.setBrush(shade(hair, QRectF(540, 600, 200, 290), 14, 14))
    goatee = QPainterPath()
    # Wide at the jaw, tapering to a long point — the reference's defining
    # feature, and it has to sit under the moustache it joins.
    goatee.moveTo(544, 608)
    goatee.cubicTo(516, 742, 578, 886, 640, 918)
    goatee.cubicTo(702, 886, 764, 742, 736, 608)
    goatee.cubicTo(706, 690, 574, 690, 544, 608)
    p.drawPath(goatee)
    moustache = QPainterPath()
    moustache.moveTo(558, 622)
    moustache.cubicTo(590, 590, 690, 590, 722, 622)
    moustache.cubicTo(700, 646, 668, 630, 640, 630)
    moustache.cubicTo(612, 630, 580, 646, 558, 622)
    p.drawPath(moustache)
    p.end()
    layers.append(save(img, folder, "13Goatee.png"))

    # 15 loose front strand (sways)
    img = new_layer()
    p = painter_for(img)
    p.setPen(pen(6, hair_dark))
    p.setBrush(QBrush(hair.lighter(106)))
    strand = QPainterPath()
    strand.moveTo(784, 300)
    strand.cubicTo(856, 236, 880, 182, 862, 142)
    strand.cubicTo(842, 186, 818, 244, 760, 294)
    strand.closeSubpath()
    p.drawPath(strand)
    p.end()
    layers.append(save(img, folder, "15Strand.png"))

    write_manifest(
        folder, "Coder",
        ["01HairBehind.png", "02Body.png", "03Ear_Right.png", "12Ear_Left.png", "05Head.png",
         "13Goatee.png", "08Hair.png", "15Strand.png"],
        {
            "eyes": {"order": 5, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
            "mouth": {"order": 5, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
        },
        ["15Strand.png"],
        ["03Ear_Right.png", "12Ear_Left.png"],
    )


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 - QPainter/QImage need an app instance
    for name, build in (("Orc", build_orc), ("Ranger", build_ranger), ("Coder", build_coder)):
        folder = OUT_ROOT / name
        build(folder)
        print(f"{name}: {len(list(folder.glob('*.png')))} layers -> {folder}")


if __name__ == "__main__":
    main()
