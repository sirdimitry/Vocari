"""The programmer avatar, redone as pixel art from the user's reference photo:
sandy hair going grey at the temples and swept back messily, a chin-only
goatee (no moustache), grey-blue eyes, a weathered/fuller face, a stonewashed
denim jacket over a dark tee. Animation stays the same shape as the SVG
version it replaces (hair/goatee sway, an occasional eye glint) - only the
art style changed, see tools/art/pixel.py for the low-res-grid-then-upscale
approach and why it suits "as close to the photo as we can get" better than
parametric SVG shapes.
"""
from __future__ import annotations

from tools.art.pixel import PixelCanvas

GRID = 80  # 1280 / 80 = 16x upscale, exact

CX = 40
TOP = 12       # top of the hair mass
HAIRLINE = 21  # where hair meets forehead skin
CHIN = 50
EYE_Y = 30
BROW_Y = 27
NOSE_Y = 35
MOUTH_Y = 41
JAW_W = 15  # half-width at the cheekbones (the widest point of the face)

SKIN = "#d3a077"
SKIN_LIGHT = "#e9bd93"
SKIN_SHADOW = "#ab7850"
SKIN_DEEP = "#7e5535"

HAIR = "#a9865a"
HAIR_LIGHT = "#c7a374"
HAIR_GREY = "#a9a08e"
HAIR_DARK = "#71542f"

GOATEE = "#8f7047"
GOATEE_LIGHT = "#ab8c5c"
GOATEE_DARK = "#54401f"
GOATEE_GREY = "#8c8574"

EYE_IRIS = "#5d7986"
EYE_IRIS_LIGHT = "#8aa8b2"
EYE_DARK = "#232527"
EYE_WHITE = "#e8e1d2"
BROW_COLOR = "#7d6140"

JACKET = "#5c7791"
JACKET_LIGHT = "#89a6ba"
JACKET_DARK = "#3b4e60"
JACKET_SEAM = "#2b3946"
TEE = "#28282c"
TEE_GRAPHIC = "#a8483c"
TEE_GRAPHIC_LIGHT = "#d9d3c6"


def _head_half_width(row: int) -> float:
    """Procedural head silhouette width per grid row - a fuller, broader face
    than the earlier SVG coder (this one is a heavier-set middle-aged face,
    matching the reference photo's build)."""
    t = max(0.0, min(1.0, (row - HAIRLINE) / (CHIN - HAIRLINE)))
    if t < 0.55:
        return JAW_W * (0.62 + 0.38 * (t / 0.55))
    t2 = (t - 0.55) / 0.45
    return JAW_W - (JAW_W - 6) * (t2 ** 1.15)


def _skin_shade(row: int, col: int) -> str:
    """Cheap left-lit shading: lighter toward the upper-left, darker lower-
    right and at the silhouette edge."""
    hw = _head_half_width(row)
    edge = abs(col - CX) / max(hw, 1)
    lit = (col < CX) and (row < EYE_Y + 6)
    if edge > 0.85:
        return SKIN_SHADOW
    if lit and edge < 0.5:
        return SKIN_LIGHT
    return SKIN


def head() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(HAIRLINE, CHIN + 1):
        hw = _head_half_width(row)
        x0, x1 = round(CX - hw), round(CX + hw)
        for x in range(x0, x1 + 1):
            c.px(x, row, _skin_shade(row, x))
    # Jaw/neck shadow under the chin.
    for row in range(CHIN - 3, CHIN + 1):
        hw = _head_half_width(row) * 0.7
        c.row(row, round(CX - hw), round(CX + hw), SKIN_DEEP, alpha=0.35)
    # Cheek flush (a little life in an otherwise flat fill).
    for dx in (-1, 0):
        c.px(CX - 9 + dx, 38, SKIN_SHADOW, alpha=0.4)
        c.px(CX + 9 - dx, 38, SKIN_SHADOW, alpha=0.4)
    # Nose bridge + tip, drawn with three shades for a hint of volume.
    c.col(CX, NOSE_Y - 4, NOSE_Y + 2, SKIN_SHADOW, alpha=0.5)
    c.row(NOSE_Y + 3, CX - 2, CX + 2, SKIN_LIGHT, alpha=0.6)
    c.px(CX - 3, NOSE_Y + 4, SKIN_DEEP, alpha=0.5)
    c.px(CX + 3, NOSE_Y + 4, SKIN_DEEP, alpha=0.5)
    # Forehead + smile creases - a couple of single-pixel lines, which is all
    # a "weathered" cue needs at this resolution.
    c.row(BROW_Y - 5, CX - 8, CX + 8, SKIN_SHADOW, alpha=0.25)
    for sign in (-1, 1):
        c.px(CX + sign * 11, MOUTH_Y - 1, SKIN_SHADOW, alpha=0.35)
        c.px(CX + sign * 12, MOUTH_Y, SKIN_SHADOW, alpha=0.3)
    # Ears, folded straight into the head layer rather than kept separate -
    # this face has no ear-specific motion in the pixel version.
    for side in (-1, 1):
        x = CX + side * (JAW_W - 1)
        for row in range(EYE_Y - 1, EYE_Y + 7):
            c.px(x, row, SKIN_SHADOW)
        c.px(x + (1 if side < 0 else -1), EYE_Y + 1, SKIN_LIGHT)
        c.px(x + (1 if side < 0 else -1), EYE_Y + 4, SKIN)
    return c


def hair_back() -> PixelCanvas:
    """The solid backing mass - drawn first, behind the head and the front
    hair detail, so the silhouette never shows a gap at the crown/sides."""
    c = PixelCanvas(GRID)
    for row in range(TOP, HAIRLINE + 4):
        t = (row - TOP) / (HAIRLINE + 4 - TOP)
        hw = 17 * min(1.0, 0.5 + t * 0.9)
        c.row(row, round(CX - hw), round(CX + hw), HAIR_DARK)
    return c


def hair_front() -> PixelCanvas:
    """Sway layer: swept-back, slightly tousled top hair with grey streaks at
    the temples, matching the reference photo's side part."""
    c = PixelCanvas(GRID)
    for row in range(TOP, HAIRLINE + 3):
        t = (row - TOP) / (HAIRLINE + 3 - TOP)
        hw = 17 * min(1.0, 0.45 + t * 0.95)
        c.row(row, round(CX - hw), round(CX + hw), HAIR)
    # Swept-back strand texture: diagonal light streaks following the comb
    # direction (back-left to front-right, as in the photo).
    strands = [
        (CX - 14, TOP + 1, HAIR_LIGHT), (CX - 9, TOP, HAIR_LIGHT),
        (CX - 3, TOP - 1, HAIR_LIGHT), (CX + 4, TOP, HAIR_LIGHT),
        (CX + 11, TOP + 1, HAIR_LIGHT), (CX + 16, TOP + 3, HAIR_LIGHT),
    ]
    for sx, sy, color in strands:
        for i in range(9):
            x, y = sx + i // 2, sy + i
            if 0 <= x < GRID and 0 <= y < GRID:
                c.px(x, y, color, alpha=0.55)
    # Grey streaks at the temples/front - the most identifying hair detail.
    grey = [
        (CX - 15, HAIRLINE - 2), (CX - 14, HAIRLINE - 1), (CX - 13, HAIRLINE),
        (CX - 6, TOP + 1), (CX - 5, TOP + 2),
        (CX + 10, HAIRLINE - 3), (CX + 11, HAIRLINE - 2), (CX + 12, HAIRLINE - 1),
    ]
    for x, y in grey:
        c.px(x, y, HAIR_GREY, alpha=0.85)
    # Side part: a thin darker seam left of center near the crown.
    for i in range(4):
        c.px(CX - 2 + i // 2, TOP - 1 + i, HAIR_DARK, alpha=0.5)
    # Hairline edge, slightly ragged rather than a clean arc.
    edge = [CX - 17, CX - 15, CX - 12, CX - 8, CX - 3, CX + 2, CX + 7, CX + 11, CX + 14, CX + 17]
    for i, x in enumerate(edge):
        y = HAIRLINE + (1 if i % 3 == 1 else 0)
        c.px(x, y, HAIR)
        c.px(x, y + 1, HAIR, alpha=0.6)
    return c


def brows(raised: bool = False) -> PixelCanvas:
    c = PixelCanvas(GRID)
    dy = -1 if raised else 0
    for side in (-1, 1):
        base = CX + side * 5
        for i in range(7):
            x = base + side * i
            y = BROW_Y + dy + (0 if i < 4 else 1)
            c.px(x, y, BROW_COLOR)
            c.px(x, y - 1, BROW_COLOR, alpha=0.8)
    return c


def eyes(closed: bool) -> PixelCanvas:
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 7
        if closed:
            for i in range(5):
                c.px(ex + side * i, EYE_Y, EYE_DARK)
            continue
        # Socket: sclera row, iris, pupil, single highlight pixel.
        c.row(EYE_Y - 1, ex - 3, ex + 3, EYE_WHITE)
        c.row(EYE_Y, ex - 3, ex + 3, EYE_WHITE)
        c.col(ex, EYE_Y - 1, EYE_Y, EYE_IRIS)
        c.px(ex - 1, EYE_Y, EYE_IRIS)
        c.px(ex + 1, EYE_Y, EYE_IRIS)
        c.px(ex, EYE_Y, EYE_DARK)
        c.px(ex - 1, EYE_Y - 1, EYE_IRIS_LIGHT, alpha=0.8)
        # Lid line + a slight squint (deep-set, weathered eyes).
        c.row(EYE_Y - 2, ex - 4, ex + 4, SKIN_DEEP, alpha=0.55)
        c.px(ex - 4, EYE_Y - 1, SKIN_DEEP, alpha=0.4)
        c.px(ex + 4, EYE_Y - 1, SKIN_DEEP, alpha=0.4)
        # Under-eye crease.
        c.row(EYE_Y + 2, ex - 3, ex + 3, SKIN_SHADOW, alpha=0.3)
    return c


def eye_shine() -> PixelCanvas:
    """The occasional-glint effect layer - one bright pixel per eye."""
    c = PixelCanvas(GRID)
    for side in (-1, 1):
        ex = CX + side * 7
        c.px(ex - 1, EYE_Y - 1, "#ffffff", alpha=0.95)
    return c


def mouth(open_: bool) -> PixelCanvas:
    c = PixelCanvas(GRID)
    if open_:
        c.row(MOUTH_Y, CX - 4, CX + 4, "#3a1c18")
        c.row(MOUTH_Y + 1, CX - 3, CX + 3, "#5c2a24")
        c.row(MOUTH_Y - 1, CX - 4, CX + 4, SKIN_DEEP, alpha=0.6)
    else:
        c.row(MOUTH_Y, CX - 5, CX + 5, SKIN_DEEP, alpha=0.7)
        c.px(CX - 5, MOUTH_Y - 1, SKIN_SHADOW, alpha=0.4)
        c.px(CX + 5, MOUTH_Y - 1, SKIN_SHADOW, alpha=0.4)
    return c


def goatee() -> PixelCanvas:
    """Sway layer (pivot "top"): a chin-only goatee - no moustache, matching
    the photo, where the mouth corners are essentially bare."""
    c = PixelCanvas(GRID)
    # Thin sideburn stubs along the jaw, suggesting the goatee connects up
    # toward the ears without a full beard - just enough to not look like a
    # floating chin-patch.
    for side in (-1, 1):
        for i, row in enumerate(range(MOUTH_Y - 2, MOUTH_Y + 2)):
            c.px(CX + side * (8 - i), row, GOATEE, alpha=0.75)
    rows = {
        MOUTH_Y + 1: (CX - 7, CX + 7),
        MOUTH_Y + 2: (CX - 8, CX + 8),
        MOUTH_Y + 3: (CX - 8, CX + 8),
        MOUTH_Y + 4: (CX - 7, CX + 7),
        MOUTH_Y + 5: (CX - 6, CX + 6),
        MOUTH_Y + 6: (CX - 5, CX + 5),
        MOUTH_Y + 7: (CX - 4, CX + 4),
        MOUTH_Y + 8: (CX - 3, CX + 3),
        MOUTH_Y + 9: (CX - 2, CX + 2),
        MOUTH_Y + 10: (CX - 1, CX + 1),
        MOUTH_Y + 11: (CX, CX),
    }
    for row, (x0, x1) in rows.items():
        c.row(row, x0, x1, GOATEE)
    # Light/dark texture strokes for a wiry, not-solid look.
    for row, (x0, x1) in rows.items():
        c.px(x0, row, GOATEE_DARK, alpha=0.6)
        c.px(x1, row, GOATEE_DARK, alpha=0.6)
        if row % 2 == 0:
            c.px((x0 + x1) // 2, row, GOATEE_LIGHT, alpha=0.6)
    # A few grey hairs, as in the photo.
    for x, y in ((CX - 3, MOUTH_Y + 4), (CX + 2, MOUTH_Y + 6), (CX, MOUTH_Y + 8),
                 (CX - 5, MOUTH_Y + 2), (CX + 4, MOUTH_Y + 3)):
        c.px(x, y, GOATEE_GREY, alpha=0.8)
    return c


def body() -> PixelCanvas:
    c = PixelCanvas(GRID)
    # Neck.
    c.rect(CX - 6, CHIN, 13, 5, SKIN_SHADOW)
    c.rect(CX - 5, CHIN, 4, 5, SKIN)

    # Tee, visible through the open jacket front.
    for row in range(CHIN + 4, GRID):
        t = (row - (CHIN + 4)) / (GRID - (CHIN + 4))
        hw = 8 + t * 6
        c.row(row, round(CX - hw), round(CX + hw), TEE)
    # A hint of a graphic on the tee.
    for row in range(CHIN + 10, CHIN + 15):
        c.row(row, CX - 4, CX + 4, TEE_GRAPHIC, alpha=0.7)
    c.row(CHIN + 12, CX - 3, CX + 3, TEE_GRAPHIC_LIGHT, alpha=0.5)

    # Denim jacket: two open panels, shoulder to hem, collar notch at the neck.
    for side in (-1, 1):
        for row in range(CHIN - 1, GRID):
            t = (row - (CHIN - 1)) / (GRID - (CHIN - 1))
            outer = 24 + t * 14
            inner = 11 + t * 6 if row > CHIN + 3 else 10 - (row - (CHIN - 1))
            x0 = CX + side * round(inner)
            x1 = CX + side * round(outer)
            lo, hi = (x0, x1) if x0 < x1 else (x1, x0)
            c.row(row, lo, hi, JACKET)
        # Shoulder highlight + hem/seam shading for a worn-denim read.
        for row in range(CHIN - 1, CHIN + 6):
            t = (row - (CHIN - 1)) / 7
            outer = round(24 + t * 5)
            c.px(CX + side * outer, row, JACKET_LIGHT, alpha=0.6)
        for row in range(CHIN + 6, GRID, 3):
            t = (row - (CHIN - 1)) / (GRID - (CHIN - 1))
            inner = round(11 + t * 6)
            c.px(CX + side * inner, row, JACKET_DARK, alpha=0.6)
        # Collar.
        c.px(CX + side * 6, CHIN - 1, JACKET_DARK, alpha=0.8)
        c.px(CX + side * 8, CHIN, JACKET)
    # A couple of buttons/stitch dots.
    c.px(CX - 12, CHIN + 20, JACKET_SEAM, alpha=0.8)
    c.px(CX + 12, CHIN + 20, JACKET_SEAM, alpha=0.8)
    return c


def back() -> PixelCanvas:
    c = PixelCanvas(GRID)
    for row in range(CHIN - 6, GRID):
        t = (row - (CHIN - 6)) / (GRID - (CHIN - 6))
        hw = 30 + t * 8
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
        {"file": "18HairFront.png", "degrees": 5, "period": 2.8, "pivot": "bottom"},
        {"file": "13Goatee.png", "degrees": 4, "period": 2.3, "pivot": "top"},
    ],
    "effect_layers": [
        {"file": "19EyeShine.png", "effect": "sparkle", "period": 5.5, "duty": 0.06, "max_opacity": 0.9},
    ],
}
