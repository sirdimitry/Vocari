"""The programmer avatar, pixel art matching the user's own reference
drawing: a chibi-proportioned head with spiky windswept sandy hair (lighter
at the tips), large dark half-lidded "cool" eyes, thin scars, a light patchy
goatee, and an open denim jacket over a dark tee with a red/blue graphic.
The reference is a full standing figure; this keeps the head-and-shoulders
bust framing the other three bundled avatars share, so scale/perspective in
the queue stays consistent, with the jacket collar/shoulders and folded arms
implied rather than the legs/shoes.

See tools/art/pixel.py for the low-res-grid-then-upscale approach: flat
fills with antialiasing off, then a nearest-neighbor upscale to the shared
1280x1280 canvas, which is what keeps pixels as hard blocks instead of
blurring into gradients.
"""
from __future__ import annotations

from tools.art.pixel import PixelCanvas

GRID = 160  # 1280 / 160 = 8x upscale, exact

CX = 80
TOP = 6            # top of the tallest hair spikes
HAIRLINE = 32       # where hair meets forehead skin
CHIN = 90
EYE_Y = 57
BROW_Y = 48
NOSE_Y = 65
MOUTH_Y = 76
JAW_W = 29  # half-width at the cheekbones - a rounder, younger chibi face

SKIN = "#eec9a3"
SKIN_LIGHT = "#f8e0bd"
SKIN_SHADOW = "#d1a276"
SKIN_DEEP = "#a97850"

HAIR = "#b78a54"
HAIR_LIGHT = "#e0bd85"
HAIR_LIGHTER = "#f2dcae"
HAIR_DARK = "#8a6238"
HAIR_DEEP = "#5f4325"

GOATEE = "#c7a06a"
GOATEE_LIGHT = "#e0c290"
GOATEE_DARK = "#8a6a3e"

EYE = "#20304a"
EYE_LIGHT = "#3c567c"
EYE_HIGHLIGHT = "#c7d8ee"
BROW_COLOR = "#8a6238"
SCAR = "#c2544a"

JACKET = "#3c5c86"
JACKET_LIGHT = "#5b7ea8"
JACKET_LIGHTER = "#89aecf"
JACKET_DARK = "#28405f"
JACKET_SEAM = "#1c3049"
TEE = "#1c2027"
TEE_LIGHT = "#2c313c"
TEE_GRAPHIC = "#b03a34"
TEE_GRAPHIC_BLUE = "#3c5c86"


def _head_half_width(row: int) -> float:
    """Round chibi head silhouette per grid row - fuller through the cheeks,
    a soft rounded chin rather than a heavy jaw."""
    t = max(0.0, min(1.0, (row - HAIRLINE) / (CHIN - HAIRLINE)))
    if t < 0.58:
        return JAW_W * (0.70 + 0.30 * (t / 0.58))
    t2 = (t - 0.58) / 0.42
    return JAW_W - (JAW_W - 12) * (t2 ** 1.2)


def _skin_tone(row: int, col: int) -> str:
    hw = _head_half_width(row)
    if hw <= 0:
        return SKIN
    edge = abs(col - CX) / hw
    on_left = col < CX
    if edge > 0.90:
        return SKIN_SHADOW
    if on_left and row < EYE_Y + 6 and edge < 0.55:
        return SKIN_LIGHT
    return SKIN


def head() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(HAIRLINE, CHIN + 1):
        hw = _head_half_width(row)
        x0, x1 = round(CX - hw), round(CX + hw)
        for x in range(x0, x1 + 1):
            c.px(x, row, _skin_tone(row, x))

    # Jaw/chin soft shadow, cheek highlight.
    for row in range(CHIN - 6, CHIN + 1):
        hw = _head_half_width(row) * 0.7
        c.row(row, round(CX - hw), round(CX + hw), SKIN_SHADOW, alpha=0.3)
    for sign in (-1, 1):
        c.px(CX + sign * 18, NOSE_Y - 2, SKIN_LIGHT, alpha=0.45)

    # Nose: just a soft hint, chibi faces stay mostly flat there.
    c.px(CX, NOSE_Y, SKIN_SHADOW, alpha=0.4)
    c.px(CX, NOSE_Y + 1, SKIN_LIGHT, alpha=0.4)

    # Scars: one under the left eye, one by the left ear - small, angled
    # marks, a character detail straight from the reference art.
    for i in range(4):
        c.px(CX - 24 + i, EYE_Y + 6 + i, SCAR, alpha=0.85)
    for i in range(3):
        c.px(CX - JAW_W + 2 + i // 2, EYE_Y - 2 + i, SCAR, alpha=0.7)

    # Ears.
    for side in (-1, 1):
        x = CX + side * (JAW_W - 1)
        for row in range(EYE_Y, EYE_Y + 11):
            c.px(x, row, SKIN_SHADOW)
            c.px(x + side, row, SKIN)
        c.px(x + side, EYE_Y + 3, SKIN_LIGHT)

    return c


# Each spike is (x offset from center at its base, sideways drift by the
# tip, base half-width, length) - rooted at/below the hairline, so the
# silhouette itself is jagged rather than a smooth dome with lines painted
# on top of it.
SPIKES = [
    (-32, -3, 7, 14),
    (-24, -2, 8, 20),
    (-15, 1, 8, 26),
    (-5, 3, 9, 30),
    (5, 6, 9, 32),
    (15, 9, 8, 28),
    (24, 8, 7, 21),
    (32, 5, 6, 12),
]
HAIR_BASE_Y = HAIRLINE + 6  # spikes root a bit below the hairline itself
# Tallest spike's tip must stay within the canvas (row 0) with a small
# margin - the earlier lengths above put it a few rows above row 0, clipped
# clean off by the canvas edge.


def hair_back() -> PixelCanvas:
    """Solid backing mass, one shade darker, sitting behind the spikes - the
    gaps between spikes in hair_front reveal slivers of this instead of the
    transparent background, reading as shadow between strands."""
    c = PixelCanvas(GRID)
    for row in range(TOP - 2, HAIR_BASE_Y + 2):
        t = max(0.0, (row - (TOP - 2)) / (HAIR_BASE_Y + 2 - (TOP - 2)))
        hw = 35 * min(1.0, 0.35 + t * 0.85)
        c.row(row, round(CX - hw), round(CX + hw), HAIR_DEEP)
    return c


def hair_front() -> PixelCanvas:
    """Sway layer: tall, messy, windswept spikes leaning to the upper right,
    lighter toward the tips - the reference's most distinctive feature. Each
    spike is its own tapering triangle (wide at the root, narrow at the tip)
    instead of a filled dome with texture lines drawn over it, so the actual
    silhouette reads as spiky rather than a smooth cap."""
    c = PixelCanvas(GRID)
    for sx, drift, base_w, length in SPIKES:
        tip_y = HAIR_BASE_Y - length
        for row in range(tip_y, HAIR_BASE_Y + 1):
            t = (row - tip_y) / length  # 0 at the tip, 1 at the root
            width = max(1.0, base_w * (0.12 + 0.88 * t))
            center = CX + sx * t + drift * (1 - t)
            x0, x1 = round(center - width / 2), round(center + width / 2)
            tip_amount = 1 - t
            color = (
                HAIR_LIGHTER if tip_amount > 0.65 else
                HAIR_LIGHT if tip_amount > 0.3 else
                HAIR
            )
            c.row(row, x0, x1, color)
            c.px(x0, row, HAIR_DARK, alpha=0.4)
    # A few stray flyaway single-pixel wisps for extra messiness.
    for sx, tip_y_off in ((-28, -20), (-8, -30), (10, -34), (22, -24)):
        x, y = CX + sx, HAIR_BASE_Y + tip_y_off
        if 0 <= x < GRID and 0 <= y < GRID:
            c.px(x, y, HAIR_LIGHTER, alpha=0.7)
            c.px(x, y + 1, HAIR_LIGHT, alpha=0.6)
    return c


def brows() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        base = CX + side * 9
        for i in range(10):
            x = base + side * i
            y = BROW_Y - (1 if i > 6 else 0) + (1 if side * i < -6 else 0)
            c.px(x, y, BROW_COLOR)
    return c


def eyes(closed: bool) -> PixelCanvas:
    """Large, solid, half-lidded "cool" eyes - no visible iris/sclera detail
    in the reference, just a dark almond shape with one soft highlight."""
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 15
        if closed:
            for i in range(11):
                c.px(ex + side * i - side * 4, EYE_Y + 3, EYE, alpha=0.9)
            continue
        rows = {
            EYE_Y - 3: (ex - 6, ex + 7),
            EYE_Y - 2: (ex - 8, ex + 9),
            EYE_Y - 1: (ex - 9, ex + 9),
            EYE_Y: (ex - 9, ex + 8),
            EYE_Y + 1: (ex - 8, ex + 7),
            EYE_Y + 2: (ex - 6, ex + 5),
            EYE_Y + 3: (ex - 3, ex + 3),
        }
        for row, (x0, x1) in rows.items():
            c.row(row, x0, x1, EYE)
        # Under-lid shading and a single soft highlight, per the reference.
        for row, (x0, x1) in rows.items():
            c.px(x1, row, EYE_LIGHT, alpha=0.5)
        c.px(ex - 4, EYE_Y - 1, EYE_HIGHLIGHT, alpha=0.55)
        c.px(ex - 3, EYE_Y, EYE_HIGHLIGHT, alpha=0.3)
    return c


def eye_shine() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 15
        c.px(ex - 5, EYE_Y - 2, "#ffffff", alpha=0.9)
        c.px(ex - 6, EYE_Y - 1, "#ffffff", alpha=0.5)
    return c


def mouth(open_: bool) -> PixelCanvas:
    c = PixelCanvas(GRID)
    if open_:
        c.row(MOUTH_Y, CX - 5, CX + 5, "#2c1512")
        c.row(MOUTH_Y + 1, CX - 4, CX + 4, "#442019")
        c.row(MOUTH_Y - 1, CX - 5, CX + 5, SKIN_DEEP, alpha=0.5)
    else:
        # A subtle closed smirk, curving slightly up on one side.
        c.row(MOUTH_Y, CX - 6, CX + 2, SKIN_DEEP, alpha=0.75)
        c.px(CX + 3, MOUTH_Y - 1, SKIN_DEEP, alpha=0.7)
        c.px(CX + 4, MOUTH_Y - 1, SKIN_DEEP, alpha=0.55)
        c.row(MOUTH_Y + 1, CX - 5, CX + 3, SKIN_LIGHT, alpha=0.3)
    return c


def goatee() -> PixelCanvas:
    """Sway layer (pivot "top"): a light, patchy chin-only goatee - thin
    enough that skin shows through in the texture pass, matching the
    reference's sparse look rather than a solid mass."""
    c = PixelCanvas(GRID)
    rows = {
        MOUTH_Y + 1: (CX - 9, CX + 9),
        MOUTH_Y + 2: (CX - 10, CX + 10),
        MOUTH_Y + 3: (CX - 10, CX + 10),
        MOUTH_Y + 4: (CX - 9, CX + 9),
        MOUTH_Y + 5: (CX - 7, CX + 7),
        MOUTH_Y + 6: (CX - 5, CX + 5),
        MOUTH_Y + 7: (CX - 3, CX + 3),
        MOUTH_Y + 8: (CX - 1, CX + 1),
    }
    for row, (x0, x1) in rows.items():
        c.row(row, x0, x1, GOATEE, alpha=0.85)
    # Patchy texture: skip pixels in a checker-ish pattern so it reads as
    # sparse stubble rather than a solid beard mass.
    for row, (x0, x1) in rows.items():
        for x in range(x0, x1 + 1):
            if (x + row) % 3 == 0:
                c.px(x, row, SKIN, alpha=0.35)
            elif (x + row) % 5 == 0:
                c.px(x, row, GOATEE_LIGHT, alpha=0.6)
        c.px(x0, row, GOATEE_DARK, alpha=0.6)
        c.px(x1, row, GOATEE_DARK, alpha=0.6)
    return c


def body() -> PixelCanvas:
    """Sway layer (pivot "bottom"): the torso/jacket itself gently rocks
    side to side from its base, an idle "standing and swaying" motion."""
    c = PixelCanvas(GRID)
    c.rect(CX - 11, CHIN, 23, 9, SKIN_SHADOW)
    c.rect(CX - 8, CHIN, 8, 9, SKIN)

    for row in range(CHIN + 6, GRID):
        t = (row - (CHIN + 6)) / (GRID - (CHIN + 6))
        hw = 16 + t * 13
        c.row(row, round(CX - hw), round(CX + hw), TEE)
    for row in range(CHIN + 14, CHIN + 24):
        t = (row - (CHIN + 14)) / 10
        hw = 9 - abs(t - 0.5) * 3
        c.row(row, round(CX - hw), round(CX + hw), TEE_GRAPHIC, alpha=0.8)
    c.row(CHIN + 18, CX - 7, CX + 7, TEE_GRAPHIC_BLUE, alpha=0.6)
    for row in range(CHIN + 6, GRID, 5):
        c.px(round(CX - 16 - (row - CHIN) * 0.1), row, TEE_LIGHT, alpha=0.35)

    for side in (-1, 1):
        for row in range(CHIN - 1, GRID):
            t = (row - (CHIN - 1)) / (GRID - (CHIN - 1))
            outer = 46 + t * 24
            inner = (18 - (row - (CHIN - 1)) * 1.0) if row < CHIN + 7 else (12 + t * 9)
            x0 = CX + side * round(inner)
            x1 = CX + side * round(outer)
            lo, hi = (x0, x1) if x0 < x1 else (x1, x0)
            c.row(row, lo, hi, JACKET)

        for row in range(CHIN - 1, CHIN + 9):
            t = (row - (CHIN - 1)) / 10
            outer = round(46 + t * 8)
            c.px(CX + side * outer, row, JACKET_LIGHTER, alpha=0.65)
            c.px(CX + side * (outer - 1), row, JACKET_LIGHT, alpha=0.45)

        for row in range(CHIN + 2, GRID, 2):
            t = (row - (CHIN - 1)) / (GRID - (CHIN - 1))
            inner = round((18 - (row - (CHIN - 1)) * 1.0) if row < CHIN + 7 else (12 + t * 9))
            c.px(CX + side * inner, row, JACKET_DARK, alpha=0.55)
            c.px(CX + side * (inner + 2), row, JACKET_SEAM, alpha=0.35)

        collar = ((6, -3), (10, -1), (13, 2), (16, 5))
        for dx, dy in collar:
            c.px(CX + side * dx, CHIN + dy, JACKET_DARK, alpha=0.85)
            c.px(CX + side * dx, CHIN + dy + 1, JACKET_LIGHT, alpha=0.5)

        c.px(CX + side * 19, CHIN + 22, JACKET_SEAM, alpha=0.85)
        c.px(CX + side * 19, CHIN + 38, JACKET_SEAM, alpha=0.85)
    return c


def back() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(CHIN - 8, GRID):
        t = (row - (CHIN - 8)) / (GRID - (CHIN - 8))
        hw = 54 + t * 14
        c.row(row, round(CX - hw), round(CX + hw), JACKET_DARK, alpha=0.85)
    return c


LAYERS = {
    "01Back.png": lambda: back().export(),
    "17HairBack.png": lambda: hair_back().export(),
    "02Body.png": lambda: body().export(),
    "05Head.png": lambda: head().export(),
    "08Brows.png": lambda: brows().export(),
    "06Eyes_Open.png": lambda: eyes(False).export(),
    "07Eyes_Closed.png": lambda: eyes(True).export(),
    "19EyeShine.png": lambda: eye_shine().export(),
    "09Mouth_Open.png": lambda: mouth(True).export(),
    "10Mouth_Closed.png": lambda: mouth(False).export(),
    "13Goatee.png": lambda: goatee().export(),
    "18HairFront.png": lambda: hair_front().export(),
}

MANIFEST = {
    "name": "Coder",
    "base_layers": [
        "01Back.png", "17HairBack.png", "02Body.png",
        "05Head.png", "08Brows.png", "19EyeShine.png", "13Goatee.png", "18HairFront.png",
    ],
    "states": {
        "eyes": {"order": 5, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
        "mouth": {"order": 6, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
    },
    "sway_layers": [
        # Hair sways gently on its own clock; the goatee dangles from its
        # root at the chin. The body itself gets a slow idle "standing and
        # swaying" rock from its base (the hips, off the bottom of the
        # frame), and the head nods slightly in time with the bounce/talk
        # signal instead of its own clock - a small motion while speaking,
        # still while silent.
        {"file": "18HairFront.png", "degrees": 4, "period": 3.1, "pivot": "bottom"},
        {"file": "13Goatee.png", "degrees": 5, "period": 2.4, "pivot": "top"},
        {"file": "02Body.png", "degrees": 3, "period": 4.2, "pivot": "bottom"},
        {"file": "05Head.png", "degrees": 0.35, "pivot": "bottom", "follow_bounce": True},
    ],
    "effect_layers": [
        {"file": "19EyeShine.png", "effect": "sparkle", "period": 5.5, "duty": 0.06, "max_opacity": 0.9},
    ],
}
