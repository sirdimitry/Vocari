"""The programmer avatar, pixel art built from the user's reference photo:
sandy-grey hair swept back and slightly tousled, a chin-only goatee (no
moustache - the mouth corners are bare in the photo), deep-set grey-blue
eyes under a heavy brow, a broad weathered face, a stonewashed denim jacket
worn open over a dark graphic tee. See tools/art/pixel.py for the low-res-
grid-then-upscale approach.

GRID=160 (8x upscale) - twice the resolution of the first pass, enough for
eyelid creases, jaw stubble and individual hair strands to read clearly
instead of just blocky colour masses.
"""
from __future__ import annotations

from tools.art.pixel import PixelCanvas

GRID = 160  # 1280 / 160 = 8x upscale, exact

CX = 80
TOP = 22          # top of the hair mass
HAIRLINE = 40     # where hair meets forehead skin
CHIN = 100
EYE_Y = 60
BROW_Y = 52
NOSE_Y = 70
MOUTH_Y = 83
JAW_W = 32  # half-width at the cheekbones - a broad, heavy-set face

SKIN = "#d2a077"
SKIN_LIGHT = "#e8bd94"
SKIN_LIGHTER = "#f4d4ae"
SKIN_SHADOW = "#a97a52"
SKIN_DEEP = "#7c5636"
SKIN_DEEPER = "#5c3f28"

HAIR = "#a4825a"
HAIR_LIGHT = "#c7a374"
HAIR_LIGHTER = "#dcc090"
HAIR_GREY = "#aaa290"
HAIR_GREY_LIGHT = "#c4beac"
HAIR_DARK = "#6d5030"
HAIR_DEEP = "#4a3620"

GOATEE = "#87693f"
GOATEE_LIGHT = "#a5875a"
GOATEE_DARK = "#513c20"
GOATEE_GREY = "#9c9483"

EYE_IRIS = "#5a7684"
EYE_IRIS_LIGHT = "#93b1ba"
EYE_IRIS_DARK = "#3c525c"
EYE_DARK = "#1c1e1f"
EYE_WHITE = "#e4ddce"
EYE_WHITE_SHADE = "#c9c0ac"
BROW_COLOR = "#6e5636"
BROW_LIGHT = "#8a6e46"

JACKET = "#5c7791"
JACKET_LIGHT = "#8aa6ba"
JACKET_LIGHTER = "#b3c8d4"
JACKET_DARK = "#3b4e60"
JACKET_DEEP = "#2a3844"
JACKET_SEAM = "#22303c"
TEE = "#26262a"
TEE_LIGHT = "#3a3a40"
TEE_GRAPHIC = "#9c4438"
TEE_GRAPHIC_LIGHT = "#d6cfc0"


def _head_half_width(row: int) -> float:
    """Procedural head silhouette width per grid row - broad through the
    cheeks/jaw (a heavier-set middle-aged face), narrowing only a little at
    the chin rather than tapering to a point."""
    t = max(0.0, min(1.0, (row - HAIRLINE) / (CHIN - HAIRLINE)))
    if t < 0.5:
        return JAW_W * (0.66 + 0.34 * (t / 0.5))
    t2 = (t - 0.5) / 0.5
    return JAW_W - (JAW_W - 15) * (t2 ** 1.3)


def _skin_tone(row: int, col: int) -> str:
    """Left-lit shading with more tiers than a flat fill: a lit patch upper-
    left, a mid tone across most of the face, shadow toward the jaw edge and
    right side, and a rim-dark silhouette edge."""
    hw = _head_half_width(row)
    if hw <= 0:
        return SKIN
    edge = abs(col - CX) / hw
    on_left = col < CX
    upper = row < EYE_Y + 4

    if edge > 0.92:
        return SKIN_DEEP
    if edge > 0.78:
        return SKIN_SHADOW
    if on_left and upper and edge < 0.55:
        return SKIN_LIGHTER if edge < 0.25 else SKIN_LIGHT
    if not on_left and row > NOSE_Y:
        return SKIN_SHADOW if edge > 0.4 else SKIN
    return SKIN


def head() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(HAIRLINE, CHIN + 1):
        hw = _head_half_width(row)
        x0, x1 = round(CX - hw), round(CX + hw)
        for x in range(x0, x1 + 1):
            c.px(x, row, _skin_tone(row, x))

    # Temple hollows (the skull narrows just below the hairline before the
    # cheekbone flares back out).
    for row in range(HAIRLINE, HAIRLINE + 6):
        hw = _head_half_width(row)
        c.px(round(CX - hw) + 1, row, SKIN_SHADOW, alpha=0.5)
        c.px(round(CX + hw) - 1, row, SKIN_SHADOW, alpha=0.4)

    # Brow ridge shadow - the single strongest "weathered/heavy face" cue.
    c.row(BROW_Y - 3, CX - 20, CX + 20, SKIN_SHADOW, alpha=0.45)
    c.row(BROW_Y - 2, CX - 19, CX + 19, SKIN_SHADOW, alpha=0.3)

    # Cheekbone highlight and hollow beneath it, then jaw/jowl shadow - a
    # fuller face reads through the jaw line sagging slightly, not a hard
    # jut.
    for sign in (-1, 1):
        c.px(CX + sign * 20, NOSE_Y - 2, SKIN_LIGHT, alpha=0.5)
        c.row(NOSE_Y + 6, CX + sign * 14, CX + sign * 22, SKIN_SHADOW, alpha=0.35)
    for row in range(CHIN - 8, CHIN + 1):
        hw = _head_half_width(row) * 0.75
        c.row(row, round(CX - hw), round(CX + hw), SKIN_DEEP, alpha=0.3)
    c.row(CHIN - 1, CX - 8, CX + 8, SKIN_DEEP, alpha=0.4)

    # Nose: bridge, wings, tip highlight, nostril shadows.
    c.col(CX - 1, BROW_Y + 2, NOSE_Y + 2, SKIN_SHADOW, alpha=0.45)
    c.col(CX + 1, BROW_Y + 2, NOSE_Y + 2, SKIN_LIGHT, alpha=0.35)
    c.row(NOSE_Y + 3, CX - 3, CX + 3, SKIN_LIGHTER, alpha=0.7)
    for sign in (-1, 1):
        c.px(CX + sign * 5, NOSE_Y + 5, SKIN_DEEP, alpha=0.6)
        c.px(CX + sign * 6, NOSE_Y + 4, SKIN_SHADOW, alpha=0.5)

    # Nasolabial folds + smile lines - weathered-face detail that a flat
    # cartoon face skips.
    for sign in (-1, 1):
        for i in range(6):
            c.px(CX + sign * (13 + i), MOUTH_Y - 8 + i, SKIN_SHADOW, alpha=0.32)
        c.px(CX + sign * 22, MOUTH_Y + 2, SKIN_SHADOW, alpha=0.3)
        c.px(CX + sign * 23, MOUTH_Y + 3, SKIN_SHADOW, alpha=0.25)
    # Forehead crease lines.
    for row in (BROW_Y - 10, BROW_Y - 14):
        c.row(row, CX - 14, CX + 14, SKIN_SHADOW, alpha=0.18)
    # Crow's feet by the eyes.
    for sign in (-1, 1):
        for i in range(3):
            c.px(CX + sign * (25 + i), EYE_Y - 2 + i, SKIN_SHADOW, alpha=0.3)

    # Ears, folded into the head layer.
    for side in (-1, 1):
        x = CX + side * (JAW_W - 1)
        for row in range(EYE_Y - 2, EYE_Y + 15):
            c.px(x, row, SKIN_SHADOW)
            c.px(x + side, row, SKIN)
        c.px(x + side, EYE_Y + 2, SKIN_LIGHT)
        c.px(x + side, EYE_Y + 9, SKIN_DEEP, alpha=0.6)
        c.px(x, EYE_Y + 6, SKIN_DEEP, alpha=0.4)

    # Fine skin grain to break up the flat fills a little.
    for row in range(HAIRLINE + 2, CHIN - 6, 2):
        hw = _head_half_width(row)
        for col in range(round(CX - hw) + 3, round(CX + hw) - 2, 3):
            c.px(col, row, SKIN_SHADOW, alpha=0.10)
    return c


def hair_back() -> PixelCanvas:
    """Solid backing mass, drawn first so the silhouette never shows a gap at
    the crown/sides once the front detail layer goes on top of it."""
    c = PixelCanvas(GRID)
    for row in range(TOP, HAIRLINE + 6):
        t = (row - TOP) / (HAIRLINE + 6 - TOP)
        hw = 34 * min(1.0, 0.5 + t * 0.9)
        c.row(row, round(CX - hw), round(CX + hw), HAIR_DEEP)
    return c


def _hair_front_half_width(row: int) -> float:
    t = (row - TOP) / (HAIRLINE + 5 - TOP)
    return 34 * min(1.0, 0.42 + t * 1.0)


def hair_front() -> PixelCanvas:
    """Sway layer: swept-back, slightly tousled top hair with grey streaks at
    the temples/crown, matching the reference photo's side part and
    windblown texture."""
    c = PixelCanvas(GRID)
    for row in range(TOP, HAIRLINE + 5):
        hw = _hair_front_half_width(row)
        c.row(row, round(CX - hw), round(CX + hw), HAIR)

    # Base shading: darker at the crown/back, lighter toward the front sweep.
    for row in range(TOP, HAIRLINE + 5):
        hw = _hair_front_half_width(row)
        for col in range(round(CX - hw), round(CX + hw) + 1):
            if col > CX + 4 and row < HAIRLINE - 4:
                c.px(col, row, HAIR_DARK, alpha=0.4)

    # Individual swept strands - diagonal light/dark pairs following the
    # comb direction (back-left to front-right). Every pixel is checked
    # against the row's own half-width so a strand can never poke outside
    # the filled silhouette (above the crown or past the temple).
    strand_starts = [-28, -23, -18, -13, -8, -3, 2, 7, 12, 17, 22, 27, 31]
    for i, sx in enumerate(strand_starts):
        light = (i % 2 == 0)
        color = HAIR_LIGHTER if light else HAIR_LIGHT
        sy = TOP + 1 + (2 if sx < 0 else 0)
        for j in range(9):
            x = CX + sx + j // 2
            y = sy + j
            if 0 <= x < GRID and 0 <= y < GRID and abs(x - CX) <= _hair_front_half_width(y):
                c.px(x, y, color, alpha=0.6 if light else 0.4)

    # Grey streaks at the temples/crown - the most identifying hair detail.
    grey_patches = [
        (CX - 30, HAIRLINE - 3, 4), (CX - 15, TOP + 2, 3),
        (CX + 20, HAIRLINE - 5, 4), (CX + 30, HAIRLINE - 2, 3),
        (CX - 5, TOP + 1, 3),
    ]
    for gx, gy, n in grey_patches:
        for k in range(n):
            x, y = gx + k // 2, gy + k
            if 0 <= x < GRID and TOP <= y < GRID and abs(x - CX) <= _hair_front_half_width(y):
                c.px(x, y, HAIR_GREY, alpha=0.8)
                c.px(x + 1, y, HAIR_GREY_LIGHT, alpha=0.5)

    # Side part: a darker seam left of center near the crown.
    for i in range(7):
        x, y = CX - 4 + i // 3, TOP + i
        if abs(x - CX) <= _hair_front_half_width(y):
            c.px(x, y, HAIR_DEEP, alpha=0.55)

    # Ragged, windblown hairline edge rather than a clean arc.
    edge = list(range(CX - 34, CX + 35, 2))
    for i, x in enumerate(edge):
        wobble = (i * 37) % 5 - 2  # deterministic pseudo-random jitter
        y = HAIRLINE + wobble // 2
        c.px(x, y, HAIR)
        c.px(x, y + 1, HAIR, alpha=0.55)
        if i % 4 == 0:
            c.px(x, y - 1, HAIR_LIGHT, alpha=0.5)
    return c


def brows() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        base = CX + side * 9
        for i in range(13):
            x = base + side * i
            thickness = 3 if i < 5 else (2 if i < 9 else 1)
            y0 = BROW_Y - (1 if i < 3 else 0)
            for t in range(thickness):
                color = BROW_LIGHT if t == 0 else BROW_COLOR
                c.px(x, y0 + t, color, alpha=0.95 if t else 0.6)
    return c


def eyes(closed: bool) -> PixelCanvas:
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 15
        if closed:
            for i in range(9):
                c.px(ex + side * i, EYE_Y, EYE_DARK)
            c.row(EYE_Y + 1, ex - 8, ex + 8, SKIN_SHADOW, alpha=0.4)
            continue

        # Sclera: an almond built from explicit per-row spans (narrower at
        # top/bottom, widest through the middle) so nothing pokes outside its
        # own row range - a column-shaped accent drawn taller than the eye
        # is what caused the old "+"-shaped eyes bug.
        c.row(EYE_Y - 3, ex - 3, ex + 3, EYE_WHITE_SHADE)
        c.row(EYE_Y - 2, ex - 6, ex + 6, EYE_WHITE_SHADE)
        c.row(EYE_Y - 1, ex - 6, ex + 6, EYE_WHITE)
        c.row(EYE_Y, ex - 6, ex + 6, EYE_WHITE)
        c.row(EYE_Y + 1, ex - 5, ex + 5, EYE_WHITE, alpha=0.9)
        c.row(EYE_Y + 2, ex - 3, ex + 3, EYE_WHITE, alpha=0.7)

        # Iris: a small filled disc, same explicit-per-row-span approach,
        # then a darker rim and a centered pupil, both confined to rows the
        # iris itself occupies.
        c.row(EYE_Y - 2, ex - 2, ex + 2, EYE_IRIS_DARK)
        c.row(EYE_Y - 1, ex - 3, ex + 3, EYE_IRIS)
        c.row(EYE_Y, ex - 3, ex + 3, EYE_IRIS)
        c.row(EYE_Y + 1, ex - 2, ex + 2, EYE_IRIS_DARK)
        c.px(ex - 2, EYE_Y - 1, EYE_IRIS_LIGHT, alpha=0.75)
        c.px(ex - 1, EYE_Y - 1, EYE_IRIS_LIGHT, alpha=0.4)
        c.px(ex + 2, EYE_Y, EYE_IRIS_DARK, alpha=0.6)

        c.row(EYE_Y - 1, ex - 1, ex + 1, EYE_DARK)
        c.row(EYE_Y, ex - 1, ex + 1, EYE_DARK)
        c.px(ex - 2, EYE_Y - 1, "#ffffff", alpha=0.9)  # catchlight

        # Heavy upper lid + crease (deep-set eye cue), thin lower lid.
        c.row(EYE_Y - 4, ex - 7, ex + 7, SKIN_DEEP, alpha=0.7)
        c.row(EYE_Y - 5, ex - 6, ex + 6, SKIN_SHADOW, alpha=0.4)
        c.px(ex - 7, EYE_Y - 3, SKIN_DEEP, alpha=0.5)
        c.px(ex + 7, EYE_Y - 3, SKIN_DEEP, alpha=0.5)
        # Under-eye bag + crease.
        c.row(EYE_Y + 3, ex - 6, ex + 6, SKIN_SHADOW, alpha=0.35)
        c.row(EYE_Y + 4, ex - 5, ex + 5, SKIN_LIGHT, alpha=0.25)
    return c


def eye_shine() -> PixelCanvas:
    """The occasional-glint effect layer - a small diagonal sparkle sitting
    just off the pupil, not a symmetric cross (which reads more like an icon
    than a catchlight)."""
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 15
        c.px(ex - 2, EYE_Y - 2, "#ffffff", alpha=0.9)
        c.px(ex - 3, EYE_Y - 1, "#ffffff", alpha=0.6)
        c.px(ex - 1, EYE_Y - 3, "#ffffff", alpha=0.5)
    return c


def mouth(open_: bool) -> PixelCanvas:
    c = PixelCanvas(GRID)
    if open_:
        c.row(MOUTH_Y, CX - 9, CX + 9, "#301612")
        c.row(MOUTH_Y + 1, CX - 8, CX + 8, "#4c2420")
        c.row(MOUTH_Y + 2, CX - 6, CX + 6, "#3a1b18")
        c.row(MOUTH_Y - 1, CX - 9, CX + 9, SKIN_DEEP, alpha=0.6)
        c.px(CX - 9, MOUTH_Y - 1, SKIN_DEEP, alpha=0.7)
        c.px(CX + 9, MOUTH_Y - 1, SKIN_DEEP, alpha=0.7)
    else:
        c.row(MOUTH_Y, CX - 10, CX + 10, SKIN_DEEP, alpha=0.75)
        c.row(MOUTH_Y - 1, CX - 8, CX + 8, SKIN_DEEPER, alpha=0.3)
        c.px(CX - 10, MOUTH_Y - 1, SKIN_SHADOW, alpha=0.5)
        c.px(CX + 10, MOUTH_Y - 1, SKIN_SHADOW, alpha=0.5)
        c.row(MOUTH_Y + 1, CX - 7, CX + 7, SKIN_LIGHT, alpha=0.3)
    return c


def goatee() -> PixelCanvas:
    """Sway layer (pivot "top"): a chin-only goatee with thin sideburn stubs
    toward the ears - no moustache, matching the photo, where the mouth
    corners themselves are bare."""
    c = PixelCanvas(GRID)

    # Thin jaw-line connectors toward the ears.
    for side in (-1, 1):
        for i, row in enumerate(range(MOUTH_Y - 5, MOUTH_Y + 3)):
            width = 17 - i
            c.px(CX + side * width, row, GOATEE, alpha=0.7)
            c.px(CX + side * (width - 1), row, GOATEE, alpha=0.5)

    rows = {
        MOUTH_Y - 1: (CX - 14, CX + 14),
        MOUTH_Y: (CX - 15, CX + 15),
        MOUTH_Y + 1: (CX - 16, CX + 16),
        MOUTH_Y + 2: (CX - 16, CX + 16),
        MOUTH_Y + 3: (CX - 15, CX + 15),
        MOUTH_Y + 4: (CX - 14, CX + 14),
        MOUTH_Y + 5: (CX - 12, CX + 12),
        MOUTH_Y + 6: (CX - 10, CX + 10),
        MOUTH_Y + 7: (CX - 8, CX + 8),
        MOUTH_Y + 8: (CX - 6, CX + 6),
        MOUTH_Y + 9: (CX - 4, CX + 4),
        MOUTH_Y + 10: (CX - 3, CX + 3),
        MOUTH_Y + 11: (CX - 2, CX + 2),
        MOUTH_Y + 12: (CX - 1, CX + 1),
        MOUTH_Y + 13: (CX, CX),
    }
    for row, (x0, x1) in rows.items():
        c.row(row, x0, x1, GOATEE)

    # Wiry texture: alternating light/dark vertical strokes rather than a
    # flat fill, plus a darker edge.
    for row, (x0, x1) in rows.items():
        c.px(x0, row, GOATEE_DARK, alpha=0.65)
        c.px(x1, row, GOATEE_DARK, alpha=0.65)
    for col_offset in range(-14, 15, 2):
        x = CX + col_offset
        for row in range(MOUTH_Y - 1, MOUTH_Y + 11):
            if (row + col_offset) % 3 == 0:
                c.px(x, row, GOATEE_LIGHT, alpha=0.35)

    # A scatter of grey hairs, as in the photo.
    for x, y in ((CX - 8, MOUTH_Y + 2), (CX + 6, MOUTH_Y + 4), (CX, MOUTH_Y + 7),
                 (CX - 4, MOUTH_Y + 9), (CX + 9, MOUTH_Y), (CX - 11, MOUTH_Y + 1)):
        c.px(x, y, GOATEE_GREY, alpha=0.8)
    return c


def body() -> PixelCanvas:
    c = PixelCanvas(GRID)
    # Neck, shaded so it reads as a cylinder rather than a flat rectangle.
    c.rect(CX - 13, CHIN, 27, 10, SKIN_SHADOW)
    c.rect(CX - 10, CHIN, 9, 10, SKIN)
    c.rect(CX - 2, CHIN, 4, 10, SKIN_LIGHT, alpha=0.5)
    c.rect(CX + 8, CHIN, 5, 10, SKIN_DEEP, alpha=0.5)

    # Tee, visible through the open jacket front.
    for row in range(CHIN + 8, GRID):
        t = (row - (CHIN + 8)) / (GRID - (CHIN + 8))
        hw = 15 + t * 12
        c.row(row, round(CX - hw), round(CX + hw), TEE)
    for row in range(CHIN + 8, GRID, 4):
        c.px(round(CX - 15 - (row - CHIN - 8) * 0.1), row, TEE_LIGHT, alpha=0.4)
    # Graphic swash on the tee.
    for row in range(CHIN + 20, CHIN + 30):
        t = (row - (CHIN + 20)) / 10
        hw = 9 - abs(t - 0.5) * 4
        c.row(row, round(CX - hw), round(CX + hw), TEE_GRAPHIC, alpha=0.75)
    c.row(CHIN + 24, CX - 7, CX + 7, TEE_GRAPHIC_LIGHT, alpha=0.55)
    c.row(CHIN + 26, CX - 5, CX + 5, TEE_GRAPHIC_LIGHT, alpha=0.4)

    # Denim jacket: two open panels, shoulder to hem, with a proper collar
    # notch, lapel fold, and worn/faded shading rather than a flat wash.
    for side in (-1, 1):
        for row in range(CHIN - 2, GRID):
            t = (row - (CHIN - 2)) / (GRID - (CHIN - 2))
            outer = 48 + t * 26
            if row < CHIN + 8:
                inner = 20 - (row - (CHIN - 2)) * 1.1
            else:
                inner = 13 + t * 10
            x0 = CX + side * round(inner)
            x1 = CX + side * round(outer)
            lo, hi = (x0, x1) if x0 < x1 else (x1, x0)
            c.row(row, lo, hi, JACKET)

        # Shoulder highlight (top seam catching the light).
        for row in range(CHIN - 2, CHIN + 10):
            t = (row - (CHIN - 2)) / 12
            outer = round(48 + t * 10)
            c.px(CX + side * outer, row, JACKET_LIGHTER, alpha=0.65)
            c.px(CX + side * (outer - 1), row, JACKET_LIGHT, alpha=0.5)

        # Lapel fold shading along the open edge, darker where it curls in.
        for row in range(CHIN + 2, GRID, 2):
            t = (row - (CHIN - 2)) / (GRID - (CHIN - 2))
            inner = round(13 + t * 10) if row >= CHIN + 8 else round(20 - (row - (CHIN - 2)) * 1.1)
            c.px(CX + side * inner, row, JACKET_DEEP, alpha=0.6)
            c.px(CX + side * (inner + 2), row, JACKET_DARK, alpha=0.4)

        # Worn/faded patches - lighter blotches scattered on the panel, a
        # stonewash cue.
        fade_spots = [(0.3, 0.35), (0.55, 0.6), (0.75, 0.3), (0.4, 0.75)]
        for ft, fx in fade_spots:
            row = round((CHIN - 2) + ft * (GRID - (CHIN - 2)))
            outer = 48 + ft * 26
            inner = 13 + ft * 10
            x = CX + side * round(inner + fx * (outer - inner))
            c.px(x, row, JACKET_LIGHT, alpha=0.35)
            c.px(x + 1, row, JACKET_LIGHT, alpha=0.25)
            c.px(x, row + 1, JACKET_LIGHT, alpha=0.25)

        # Collar, folded open over the shoulder.
        collar = (
            (CX + side * 6, CHIN - 3), (CX + side * 10, CHIN - 1),
            (CX + side * 13, CHIN + 2), (CX + side * 16, CHIN + 5),
        )
        for x, y in collar:
            c.px(x, y, JACKET_DARK, alpha=0.85)
            c.px(x, y + 1, JACKET_LIGHT, alpha=0.5)

        # Seam stitching down the lapel edge and a button.
        for row in range(CHIN + 12, GRID, 6):
            t = (row - (CHIN - 2)) / (GRID - (CHIN - 2))
            inner = round(13 + t * 10)
            c.px(CX + side * (inner + 3), row, JACKET_SEAM, alpha=0.5)
        c.px(CX + side * 20, CHIN + 24, JACKET_SEAM, alpha=0.85)
        c.px(CX + side * 20, CHIN + 40, JACKET_SEAM, alpha=0.85)
    return c


def back() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(CHIN - 10, GRID):
        t = (row - (CHIN - 10)) / (GRID - (CHIN - 10))
        hw = 58 + t * 16
        c.row(row, round(CX - hw), round(CX + hw), JACKET_DEEP, alpha=0.85)
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
        {"file": "18HairFront.png", "degrees": 5, "period": 2.8, "pivot": "bottom"},
        {"file": "13Goatee.png", "degrees": 4, "period": 2.3, "pivot": "top"},
    ],
    "effect_layers": [
        {"file": "19EyeShine.png", "effect": "sparkle", "period": 5.5, "duty": 0.06, "max_opacity": 0.9},
    ],
}
