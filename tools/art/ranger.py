"""Ranger: an original sci-fi trooper (not a copy of any Overwatch 2 hero —
see tools/art/README notes) built from the same painterly construction as the
other two: gradients, rim light, soft shadows. No exposed eyes — a visor with
a single glowing slit stands in for them, which also gives an easy "eye
lights up red" beat the plain QPainter version couldn't do.
"""
from __future__ import annotations

from tools.art.svgkit import Layer, fmt, mirror

CX = 640.0
TOP = 232.0
CHIN = 812.0
HALF_W = 300.0  # helmet is bulkier than a bare head
H = CHIN - TOP

VISOR_Y = 566.0
VISOR_H = 132.0
JAW_Y = 748.0

METAL_LIGHT = "#aab7c9"
METAL = "#7c8798"
METAL_MID = "#586275"
METAL_DARK = "#333c4c"
METAL_DEEP = "#1c2230"
LINE = "#161a24"

ACCENT = "#ff7a1a"
ACCENT_DARK = "#c2530a"
VISOR_GLASS = "#0d1620"
VISOR_GLOW = "#39d6ff"
VISOR_GLOW_DARK = "#0f6a86"
ALERT_RED = "#ff3b3b"

PADDING_DARK = "#232833"
PADDING = "#3a4150"


def _helmet_path() -> str:
    """A rounded helmet shell — wider and flatter on top than a bare skull,
    narrowing to a chin guard rather than a soft jaw."""
    r = HALF_W
    top, chin, cx = TOP, CHIN, CX
    h = chin - top
    return (
        f"M {fmt(cx)},{fmt(top)} "
        f"C {fmt(cx + r * 0.62)},{fmt(top)} {fmt(cx + r)},{fmt(top + h * 0.10)} "
        f"{fmt(cx + r)},{fmt(top + h * 0.34)} "
        f"C {fmt(cx + r)},{fmt(top + h * 0.52)} {fmt(cx + r * 0.94)},{fmt(top + h * 0.62)} "
        f"{fmt(cx + r * 0.82)},{fmt(top + h * 0.72)} "
        f"C {fmt(cx + r * 0.78)},{fmt(top + h * 0.86)} {fmt(cx + r * 0.55)},{fmt(chin - h * 0.03)} "
        f"{fmt(cx + r * 0.20)},{fmt(chin)} "
        f"C {fmt(cx + r * 0.08)},{fmt(chin + 6)} {fmt(cx - r * 0.08)},{fmt(chin + 6)} "
        f"{fmt(cx - r * 0.20)},{fmt(chin)} "
        f"C {fmt(cx - r * 0.55)},{fmt(chin - h * 0.03)} {fmt(cx - r * 0.78)},{fmt(top + h * 0.86)} "
        f"{fmt(cx - r * 0.82)},{fmt(top + h * 0.72)} "
        f"C {fmt(cx - r * 0.94)},{fmt(top + h * 0.62)} {fmt(cx - r)},{fmt(top + h * 0.52)} "
        f"{fmt(cx - r)},{fmt(top + h * 0.34)} "
        f"C {fmt(cx - r)},{fmt(top + h * 0.10)} {fmt(cx - r * 0.62)},{fmt(top)} "
        f"{fmt(cx)},{fmt(top)} Z"
    )


HELMET_D = _helmet_path()


def head() -> Layer:
    layer = Layer("head")
    clip = layer.clip(HELMET_D)
    fill = layer.linear(
        [(0.0, METAL_LIGHT), (0.42, METAL), (0.78, METAL_MID), (1.0, METAL_DARK)],
        CX - HALF_W, TOP, CX + HALF_W * 0.6, CHIN,
    )
    layer.draw(HELMET_D, fill=fill)

    # Crown highlight - a single soft sweep, the classic hard-surface cue.
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.7)},{fmt(TOP + 30)} "
        f"C {fmt(CX - HALF_W * 0.2)},{fmt(TOP - 10)} {fmt(CX + HALF_W * 0.3)},{fmt(TOP - 6)} "
        f"{fmt(CX + HALF_W * 0.6)},{fmt(TOP + 40)} "
        f"L {fmt(CX + HALF_W * 0.5)},{fmt(TOP + 90)} "
        f"C {fmt(CX + HALF_W * 0.1)},{fmt(TOP + 50)} {fmt(CX - HALF_W * 0.4)},{fmt(TOP + 54)} "
        f"{fmt(CX - HALF_W * 0.62)},{fmt(TOP + 96)} Z",
        "#ffffff", 16, 0.5, clip=clip,
    )
    # Panel seams.
    for dx, dy in ((-0.72, 0.30), (0.72, 0.30)):
        layer.draw(
            f"M {fmt(CX + dx * HALF_W)},{fmt(TOP + H * dy)} "
            f"C {fmt(CX + dx * HALF_W * 0.7)},{fmt(TOP + H * (dy + 0.28))} "
            f"{fmt(CX + dx * HALF_W * 0.5)},{fmt(TOP + H * (dy + 0.46))} "
            f"{fmt(CX + dx * HALF_W * 0.3)},{fmt(TOP + H * (dy + 0.5))}",
            stroke=METAL_DEEP, width=4, opacity=0.5, clip=clip,
        )
    # Jaw shadow / chin guard occlusion.
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.6)},{fmt(JAW_Y - 10)} "
        f"C {fmt(CX - HALF_W * 0.3)},{fmt(JAW_Y + 60)} {fmt(CX + HALF_W * 0.3)},{fmt(JAW_Y + 60)} "
        f"{fmt(CX + HALF_W * 0.6)},{fmt(JAW_Y - 10)} "
        f"L {fmt(CX + HALF_W * 0.6)},{fmt(JAW_Y + 80)} L {fmt(CX - HALF_W * 0.6)},{fmt(JAW_Y + 80)} Z",
        METAL_DEEP, 20, 0.45, clip=clip,
    )
    layer.draw(
        f"M {fmt(CX - HALF_W * 0.42)},{fmt(JAW_Y + 4)} "
        f"C {fmt(CX - HALF_W * 0.16)},{fmt(JAW_Y + 32)} {fmt(CX + HALF_W * 0.16)},{fmt(JAW_Y + 32)} "
        f"{fmt(CX + HALF_W * 0.42)},{fmt(JAW_Y + 4)}",
        stroke=LINE, width=6, opacity=0.7, clip=clip,
    )
    # Rim light down the right edge.
    layer.soft(
        f"M {fmt(CX + HALF_W * 0.75)},{fmt(TOP + H * 0.12)} "
        f"C {fmt(CX + HALF_W * 1.02)},{fmt(TOP + H * 0.35)} "
        f"{fmt(CX + HALF_W * 0.9)},{fmt(TOP + H * 0.65)} "
        f"{fmt(CX + HALF_W * 0.55)},{fmt(CHIN - 20)} "
        f"L {fmt(CX + HALF_W * 1.1)},{fmt(CHIN)} L {fmt(CX + HALF_W * 1.1)},{fmt(TOP)} Z",
        "#d9f4ff", 14, 0.4, clip=clip,
    )
    layer.draw(HELMET_D, fill="none", stroke=LINE, width=7, opacity=0.9)
    return layer


def _visor_path() -> str:
    hw = HALF_W * 0.78
    y, h = VISOR_Y, VISOR_H
    return (
        f"M {fmt(CX - hw)},{fmt(y + h * 0.5)} "
        f"C {fmt(CX - hw)},{fmt(y - h * 0.1)} {fmt(CX - hw * 0.5)},{fmt(y - h * 0.5)} "
        f"{fmt(CX)},{fmt(y - h * 0.5)} "
        f"C {fmt(CX + hw * 0.5)},{fmt(y - h * 0.5)} {fmt(CX + hw)},{fmt(y - h * 0.1)} "
        f"{fmt(CX + hw)},{fmt(y + h * 0.5)} "
        f"C {fmt(CX + hw)},{fmt(y + h * 1.1)} {fmt(CX + hw * 0.5)},{fmt(y + h * 1.35)} "
        f"{fmt(CX)},{fmt(y + h * 1.35)} "
        f"C {fmt(CX - hw * 0.5)},{fmt(y + h * 1.35)} {fmt(CX - hw)},{fmt(y + h * 1.1)} "
        f"{fmt(CX - hw)},{fmt(y + h * 0.5)} Z"
    )


VISOR_D = _visor_path()


def _visor_base(layer: Layer, lit: bool) -> str:
    clip = layer.clip(VISOR_D)
    glass = layer.radial(
        [(0.0, "#16222c"), (0.7, VISOR_GLASS), (1.0, "#050a0f")],
        CX, VISOR_Y + VISOR_H * 0.3, HALF_W * 0.85,
    )
    layer.draw(VISOR_D, fill=glass)
    if lit:
        # The glowing slit: a bright core line plus a soft bloom around it.
        line = (
            f"M {fmt(CX - HALF_W * 0.6)},{fmt(VISOR_Y + VISOR_H * 0.42)} "
            f"C {fmt(CX - HALF_W * 0.2)},{fmt(VISOR_Y + VISOR_H * 0.30)} "
            f"{fmt(CX + HALF_W * 0.2)},{fmt(VISOR_Y + VISOR_H * 0.30)} "
            f"{fmt(CX + HALF_W * 0.6)},{fmt(VISOR_Y + VISOR_H * 0.42)}"
        )
        layer.soft(line, VISOR_GLOW, 22, 0.65, clip=clip)
        layer.draw(line, stroke=VISOR_GLOW, width=16, opacity=0.9, clip=clip)
        layer.draw(line, stroke="#eafcff", width=6, opacity=0.95, clip=clip)
        layer.soft(
            f"M {fmt(CX - 40)},{fmt(VISOR_Y + VISOR_H * 0.36)} "
            f"L {fmt(CX + 40)},{fmt(VISOR_Y + VISOR_H * 0.36)}",
            "#ffffff", 30, 0.5, clip=clip,
        )
        # Faint scanline texture below the main slit.
        for i in range(4):
            yy = VISOR_Y + VISOR_H * (0.65 + i * 0.14)
            layer.draw(
                f"M {fmt(CX - HALF_W * 0.5)},{fmt(yy)} L {fmt(CX + HALF_W * 0.5)},{fmt(yy)}",
                stroke=VISOR_GLOW_DARK, width=3, opacity=0.35, clip=clip,
            )
    else:
        layer.soft(
            f"M {fmt(CX - HALF_W * 0.5)},{fmt(VISOR_Y + VISOR_H * 0.42)} "
            f"L {fmt(CX + HALF_W * 0.5)},{fmt(VISOR_Y + VISOR_H * 0.42)}",
            VISOR_GLOW_DARK, 14, 0.3, clip=clip,
        )
    # Glass sheen, always present.
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.55)},{fmt(VISOR_Y - VISOR_H * 0.3)} "
        f"C {fmt(CX - HALF_W * 0.1)},{fmt(VISOR_Y - VISOR_H * 0.5)} "
        f"{fmt(CX + HALF_W * 0.2)},{fmt(VISOR_Y - VISOR_H * 0.4)} "
        f"{fmt(CX + HALF_W * 0.35)},{fmt(VISOR_Y - VISOR_H * 0.1)} "
        f"L {fmt(CX + HALF_W * 0.1)},{fmt(VISOR_Y + VISOR_H * 0.2)} "
        f"L {fmt(CX - HALF_W * 0.5)},{fmt(VISOR_Y)} Z",
        "#ffffff", 12, 0.28, clip=clip,
    )
    layer.draw(VISOR_D, fill="none", stroke=LINE, width=8, opacity=0.92)
    layer.draw(VISOR_D, fill="none", stroke=METAL_LIGHT, width=3, opacity=0.5)
    return clip


def eyes(closed: bool) -> Layer:
    """The "eyes" state is repurposed as the visor's lit/blink state, so the
    normal blink timer still does something meaningful on a face with no
    literal eyes."""
    layer = Layer("eyes")
    _visor_base(layer, lit=not closed)
    return layer


def eye_glow() -> Layer:
    """A separate bloom layer over the visor slit that periodically flares
    brighter red — the "eye lights up red" beat — on top of the always-on
    cyan scan glow."""
    layer = Layer("eye_glow")
    clip = layer.clip(VISOR_D)
    line = (
        f"M {fmt(CX - HALF_W * 0.62)},{fmt(VISOR_Y + VISOR_H * 0.42)} "
        f"C {fmt(CX - HALF_W * 0.2)},{fmt(VISOR_Y + VISOR_H * 0.30)} "
        f"{fmt(CX + HALF_W * 0.2)},{fmt(VISOR_Y + VISOR_H * 0.30)} "
        f"{fmt(CX + HALF_W * 0.62)},{fmt(VISOR_Y + VISOR_H * 0.42)}"
    )
    layer.soft(line, ALERT_RED, 30, 0.85, clip=clip)
    layer.draw(line, stroke=ALERT_RED, width=20, opacity=0.9, clip=clip)
    layer.draw(line, stroke="#ffe2e2", width=7, opacity=0.9, clip=clip)
    return layer


def brows() -> Layer:
    """No brows on a helmet - kept as an empty layer so the shared z-order
    slot (states order counting) still lines up if a future model swaps in."""
    return Layer("brows")


def mouth(open_: bool) -> Layer:
    """A vocoder grille under the visor: a row of slats that light up while
    talking instead of a jaw moving."""
    layer = Layer("mouth")
    y = JAW_Y + 26
    w = HALF_W * 0.62
    plate = (
        f"M {fmt(CX - w)},{fmt(y - 20)} "
        f"C {fmt(CX - w * 0.4)},{fmt(y - 38)} {fmt(CX + w * 0.4)},{fmt(y - 38)} "
        f"{fmt(CX + w)},{fmt(y - 20)} "
        f"L {fmt(CX + w * 0.9)},{fmt(y + 34)} "
        f"C {fmt(CX + w * 0.3)},{fmt(y + 48)} {fmt(CX - w * 0.3)},{fmt(y + 48)} "
        f"{fmt(CX - w * 0.9)},{fmt(y + 34)} Z"
    )
    plate_fill = layer.linear([(0.0, METAL_MID), (1.0, METAL_DEEP)], CX, y - 30, CX, y + 40)
    layer.draw(plate, fill=plate_fill, stroke=LINE, width=5)
    slat_color = ACCENT if open_ else METAL_DEEP
    glow = layer.blur(10) if open_ else None
    for i in range(5):
        t = (i - 2) / 2
        x = CX + t * w * 0.68
        yy = y + abs(t) * 8
        if open_:
            layer.draw(
                f"M {fmt(x)},{fmt(yy - 16)} L {fmt(x)},{fmt(yy + 20)}",
                stroke=ACCENT, width=8, opacity=0.95, blur=glow,
            )
        layer.draw(
            f"M {fmt(x)},{fmt(yy - 16)} L {fmt(x)},{fmt(yy + 20)}",
            stroke=slat_color, width=6, opacity=0.9,
        )
    return layer


def antenna() -> Layer:
    """Sway layer: a whip antenna rooted at the helmet crown, tipped with the
    emitter dot the radio-wave effect radiates from."""
    layer = Layer("antenna")
    base_x, base_y = CX + 70, TOP + 6
    tip_x, tip_y = base_x + 46, base_y - 190
    rod = f"M {fmt(base_x)},{fmt(base_y)} C {fmt(base_x + 30)},{fmt(base_y - 90)} {fmt(tip_x - 14)},{fmt(base_y - 150)} {fmt(tip_x)},{fmt(tip_y)}"
    layer.draw(rod, stroke=METAL_DARK, width=13, opacity=0.9)
    layer.draw(rod, stroke=METAL_LIGHT, width=5, opacity=0.7)
    layer.ellipse(base_x, base_y + 4, 20, 14, METAL_MID)
    layer.ellipse(tip_x, tip_y, 15, 15, ACCENT_DARK)
    layer.ellipse(tip_x, tip_y, 15, 15, ACCENT, opacity=0.85, blur=layer.blur(4))
    layer.ellipse(tip_x - 4, tip_y - 4, 6, 6, "#ffe6cc", opacity=0.9)
    return layer


def emitter_dot() -> Layer:
    """A standalone copy of just the antenna tip, used purely as the source
    pixmap for the 'emit' radio-wave effect (kept separate from the antenna
    rod so the expanding echoes don't drag the rod along with them)."""
    layer = Layer("emitter_dot")
    base_x, base_y = CX + 70, TOP + 6
    tip_x, tip_y = base_x + 46, base_y - 190
    layer.ellipse(tip_x, tip_y, 17, 17, ACCENT, opacity=0.55, blur=layer.blur(6))
    layer.draw(
        f"M {fmt(tip_x - 22)},{fmt(tip_y)} L {fmt(tip_x + 22)},{fmt(tip_y)}",
        stroke=ACCENT, width=3, opacity=0.7,
    )
    layer.draw(
        f"M {fmt(tip_x)},{fmt(tip_y - 22)} L {fmt(tip_x)},{fmt(tip_y + 22)}",
        stroke=ACCENT, width=3, opacity=0.7,
    )
    return layer


def ear(side: int) -> Layer:
    """Side comm-pucks on the helmet rather than organic ears - still get the
    bounce-react lag so the head's motion reads through them."""
    layer = Layer("ear")
    g = layer.sub()
    base_x, base_y = CX + HALF_W * 0.92, VISOR_Y + 30
    shape = (
        f"M {fmt(base_x - 18)},{fmt(base_y - 58)} "
        f"C {fmt(base_x + 34)},{fmt(base_y - 70)} {fmt(base_x + 60)},{fmt(base_y - 30)} "
        f"{fmt(base_x + 54)},{fmt(base_y + 20)} "
        f"C {fmt(base_x + 48)},{fmt(base_y + 62)} {fmt(base_x + 6)},{fmt(base_y + 74)} "
        f"{fmt(base_x - 22)},{fmt(base_y + 54)} Z"
    )
    clip = g.clip(shape)
    fill = g.linear([(0.0, METAL_LIGHT), (0.6, METAL), (1.0, METAL_DARK)],
                    base_x - 20, base_y - 60, base_x + 50, base_y + 60)
    g.draw(shape, fill=fill)
    g.ellipse(base_x + 14, base_y - 8, 20, 20, VISOR_GLASS, clip=clip)
    g.ellipse(base_x + 14, base_y - 8, 20, 20, VISOR_GLOW, opacity=0.7,
              blur=g.blur(6), clip=clip)
    g.draw(shape, fill="none", stroke=LINE, width=6, opacity=0.9)
    markup = layer.take(g)
    if side < 0:
        layer.group(markup, transform=mirror(CX))
    else:
        layer.raw(markup)
    return layer


def body() -> Layer:
    layer = Layer("body")
    neck = (
        f"M {fmt(CX - 110)},{fmt(CHIN - 40)} L {fmt(CX - 128)},{fmt(CHIN + 96)} "
        f"L {fmt(CX + 128)},{fmt(CHIN + 96)} L {fmt(CX + 110)},{fmt(CHIN - 40)} Z"
    )
    layer.draw(neck, fill=METAL_DARK)

    torso = (
        f"M {fmt(CX - 246)},{fmt(1280)} "
        f"C {fmt(CX - 258)},{fmt(1060)} {fmt(CX - 320)},{fmt(980)} "
        f"{fmt(CX - 418)},{fmt(944)} "
        f"C {fmt(CX - 300)},{fmt(902)} {fmt(CX - 190)},{fmt(884)} "
        f"{fmt(CX - 140)},{fmt(CHIN + 90)} "
        f"C {fmt(CX - 60)},{fmt(CHIN + 130)} {fmt(CX + 60)},{fmt(CHIN + 130)} "
        f"{fmt(CX + 140)},{fmt(CHIN + 90)} "
        f"C {fmt(CX + 190)},{fmt(884)} {fmt(CX + 300)},{fmt(902)} "
        f"{fmt(CX + 418)},{fmt(944)} "
        f"C {fmt(CX + 320)},{fmt(980)} {fmt(CX + 258)},{fmt(1060)} "
        f"{fmt(CX + 246)},{fmt(1280)} Z"
    )
    clip = layer.clip(torso)
    torso_fill = layer.linear([(0.0, METAL_LIGHT), (0.4, METAL), (1.0, METAL_DARK)],
                              CX - 100, 900, CX + 60, 1280)
    layer.draw(torso, fill=torso_fill)
    layer.soft(
        f"M {fmt(CX - 180)},{fmt(CHIN + 70)} "
        f"C {fmt(CX - 90)},{fmt(CHIN + 160)} {fmt(CX + 90)},{fmt(CHIN + 160)} "
        f"{fmt(CX + 180)},{fmt(CHIN + 70)} "
        f"L {fmt(CX + 180)},{fmt(CHIN - 10)} L {fmt(CX - 180)},{fmt(CHIN - 10)} Z",
        METAL_DEEP, 26, 0.5, clip=clip,
    )
    # Chest plate with beveled panel lines.
    plate = (
        f"M {fmt(CX - 140)},{fmt(990)} "
        f"C {fmt(CX - 60)},{fmt(960)} {fmt(CX + 60)},{fmt(960)} {fmt(CX + 140)},{fmt(990)} "
        f"L {fmt(CX + 150)},{fmt(1220)} "
        f"C {fmt(CX + 70)},{fmt(1260)} {fmt(CX - 70)},{fmt(1260)} {fmt(CX - 150)},{fmt(1220)} Z"
    )
    plate_fill = layer.linear([(0.0, PADDING), (1.0, PADDING_DARK)], CX, 960, CX, 1240)
    layer.draw(plate, fill=plate_fill, stroke=LINE, width=6, clip=clip)
    layer.draw(
        f"M {fmt(CX)},{fmt(1010)} L {fmt(CX)},{fmt(1230)}",
        stroke=LINE, width=4, opacity=0.5, clip=clip,
    )
    # Status core light.
    layer.ellipse(CX, 1080, 34, 34, ACCENT_DARK, clip=clip)
    layer.ellipse(CX, 1080, 34, 34, ACCENT, opacity=0.9, blur=layer.blur(10), clip=clip)
    layer.ellipse(CX, 1080, 16, 16, "#ffe9cf", opacity=0.9, clip=clip)
    for i in range(3):
        yy = 1150 + i * 34
        layer.draw(
            f"M {fmt(CX - 60)},{fmt(yy)} L {fmt(CX + 60)},{fmt(yy)}",
            stroke=METAL_DEEP, width=5, opacity=0.4, clip=clip,
        )

    # Pauldrons.
    for sign in (-1, 1):
        x0 = CX + sign * 300
        pauldron = (
            f"M {fmt(x0 - sign * 140)},{fmt(940)} "
            f"C {fmt(x0)},{fmt(880)} {fmt(x0 + sign * 90)},{fmt(880)} "
            f"{fmt(x0 + sign * 150)},{fmt(950)} "
            f"C {fmt(x0 + sign * 160)},{fmt(1030)} {fmt(x0 + sign * 100)},{fmt(1110)} "
            f"{fmt(x0)},{fmt(1140)} "
            f"C {fmt(x0 - sign * 110)},{fmt(1080)} {fmt(x0 - sign * 150)},{fmt(1000)} "
            f"{fmt(x0 - sign * 140)},{fmt(940)} Z"
        )
        p_fill = layer.linear([(0.0, METAL_LIGHT), (0.5, METAL), (1.0, METAL_DARK)],
                              x0 - 100, 880, x0 + 100, 1140)
        layer.soft(pauldron, "#0c0f14", 20, 0.4)
        layer.draw(pauldron, fill=p_fill, stroke=LINE, width=7)
        layer.draw(
            f"M {fmt(x0 - sign * 90)},{fmt(940)} "
            f"C {fmt(x0)},{fmt(910)} {fmt(x0 + sign * 60)},{fmt(912)} "
            f"{fmt(x0 + sign * 110)},{fmt(950)}",
            stroke="#e8f4ff", width=10, opacity=0.55,
        )
        layer.draw(
            f"M {fmt(x0 - sign * 40)},{fmt(1000)} L {fmt(x0 + sign * 60)},{fmt(1000)}",
            stroke=ACCENT, width=8, opacity=0.85, blur=layer.blur(3),
        )
    return layer


def back() -> Layer:
    layer = Layer("back")
    shape = (
        f"M {fmt(CX - 460)},{fmt(1280)} "
        f"C {fmt(CX - 460)},{fmt(1010)} {fmt(CX - 320)},{fmt(900)} "
        f"{fmt(CX)},{fmt(886)} "
        f"C {fmt(CX + 320)},{fmt(900)} {fmt(CX + 460)},{fmt(1010)} "
        f"{fmt(CX + 460)},{fmt(1280)} Z"
    )
    fill = layer.linear([(0.0, METAL_DARK), (1.0, METAL_DEEP)], CX, 880, CX, 1280)
    layer.draw(shape, fill=fill, opacity=0.92)
    return layer


LAYERS = {
    "01Back.png": back,
    "02Body.png": body,
    "03Ear_Right.png": lambda: ear(1),
    "12Ear_Left.png": lambda: ear(-1),
    "05Head.png": head,
    "08Brows.png": brows,
    "06Eyes_Open.png": lambda: eyes(False),
    "07Eyes_Closed.png": lambda: eyes(True),
    "09Mouth_Open.png": lambda: mouth(True),
    "10Mouth_Closed.png": lambda: mouth(False),
    "16Antenna.png": antenna,
    "17EyeGlow.png": eye_glow,
    "18Emitter.png": emitter_dot,
}

MANIFEST = {
    "name": "Ranger",
    "base_layers": [
        "01Back.png", "02Body.png", "03Ear_Right.png", "12Ear_Left.png",
        "05Head.png", "08Brows.png", "16Antenna.png", "17EyeGlow.png", "18Emitter.png",
    ],
    "states": {
        "eyes": {"order": 6, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
        "mouth": {"order": 7, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
    },
    "sway_layers": [
        {"file": "16Antenna.png", "degrees": 10, "period": 1.6, "pivot": "bottom"},
    ],
    "bounce_react_layers": ["03Ear_Right.png", "12Ear_Left.png"],
    "effect_layers": [
        # The visor's own red flare - brief and rare, like an alert blinking on.
        {"file": "17EyeGlow.png", "effect": "sparkle", "period": 6.5, "duty": 0.10, "max_opacity": 0.95},
        # Radio waves pulsing out from the antenna tip.
        {"file": "18Emitter.png", "effect": "emit", "period": 1.8, "copies": 3,
         "spread": 0.5, "max_opacity": 0.8},
    ],
}
