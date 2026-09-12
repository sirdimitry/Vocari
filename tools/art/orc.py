"""The orc: heavy-jawed, tusked, cartoonishly ferocious but still friendly
enough to sit on a stream overlay all day.

Design notes that matter if this ever gets retouched: the silhouette is what
reads at overlay size, so the ears, tusks and topknot all break the outline in
different directions; the face keeps a light source at the upper left
throughout; and the green stays desaturated in shadow rather than going black,
which is what stops it looking like flat clip art.
"""
from __future__ import annotations

from tools.art import face
from tools.art.svgkit import Layer, fmt, head_path, mirror

CX = 640.0
TOP = 262.0
CHIN = 806.0
HALF_W = 286.0
H = CHIN - TOP

EYE_Y = 586.0
EYE_DX = 143.0
BROW_Y = 498.0
NOSE_Y = 648.0
MOUTH_Y = 726.0

SKIN_LIGHT = "#a8cf6b"
SKIN = "#7aa848"
SKIN_MID = "#5f8a37"
SKIN_DARK = "#3f6129"
SKIN_DEEP = "#2a441d"
LINE = "#22331a"

TUSK_LIGHT = "#fbf6e4"
TUSK = "#e4d9ba"
TUSK_DARK = "#b8a883"

HAIR = "#241a17"
HAIR_LIGHT = "#4a3730"
LEATHER = "#6d4a30"
LEATHER_DARK = "#3f2a1b"
FUR = "#c9b088"
GOLD = "#e0ae3c"
GOLD_DARK = "#966b18"
WAR_PAINT = "#b03127"

HEAD_D = head_path(CX, TOP, CHIN, HALF_W, temple=0.92, cheek=1.03, jaw=0.95, chin_round=0.52)


def _wart(layer: Layer, x: float, y: float, r: float) -> None:
    """A bump, not a dot: dark underside, lit crown, tiny contact shadow, and
    a thin outline so it reads clearly against the green rather than
    disappearing into it."""
    layer.ellipse(x, y + r * 0.34, r * 1.2, r * 0.9, SKIN_DEEP, opacity=0.4,
                  blur=layer.blur(r * 0.35))
    layer.ellipse(x, y, r, r * 0.92, SKIN_MID)
    layer.raw(
        f'<ellipse cx="{fmt(x)}" cy="{fmt(y)}" rx="{fmt(r)}" ry="{fmt(r * 0.92)}" '
        f'fill="none" stroke="{SKIN_DEEP}" stroke-width="2.5" opacity="0.6"/>'
    )
    layer.ellipse(x - r * 0.28, y - r * 0.3, r * 0.46, r * 0.36, SKIN_LIGHT, opacity=0.85)


def head() -> Layer:
    layer = Layer("head")
    clip = face.skin(
        layer, HEAD_D, base=SKIN, light=SKIN_LIGHT, shadow=SKIN_MID, deep=SKIN_DEEP,
        cx=CX, top=TOP, chin=CHIN, half_w=HALF_W, rim="#dcf5a0", rim_opacity=0.5,
    )

    # Heavy brow ridge: a lit shelf with a hard shadow pooled under it. This is
    # the feature that makes the whole face read as "orc" before any tusk does.
    ridge = (
        f"M {fmt(CX - HALF_W * 0.92)},{fmt(BROW_Y + 40)} "
        f"C {fmt(CX - HALF_W * 0.80)},{fmt(BROW_Y - 52)} "
        f"{fmt(CX - HALF_W * 0.30)},{fmt(BROW_Y - 76)} "
        f"{fmt(CX)},{fmt(BROW_Y - 56)} "
        f"C {fmt(CX + HALF_W * 0.30)},{fmt(BROW_Y - 76)} "
        f"{fmt(CX + HALF_W * 0.80)},{fmt(BROW_Y - 52)} "
        f"{fmt(CX + HALF_W * 0.92)},{fmt(BROW_Y + 40)} "
        f"C {fmt(CX + HALF_W * 0.60)},{fmt(BROW_Y + 8)} "
        f"{fmt(CX - HALF_W * 0.60)},{fmt(BROW_Y + 8)} "
        f"{fmt(CX - HALF_W * 0.92)},{fmt(BROW_Y + 40)} Z"
    )
    layer.soft(ridge, SKIN_LIGHT, 16, 0.55, clip=clip)
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.95)},{fmt(BROW_Y + 34)} "
        f"C {fmt(CX - HALF_W * 0.55)},{fmt(BROW_Y + 2)} "
        f"{fmt(CX + HALF_W * 0.55)},{fmt(BROW_Y + 2)} "
        f"{fmt(CX + HALF_W * 0.95)},{fmt(BROW_Y + 34)} "
        f"C {fmt(CX + HALF_W * 0.80)},{fmt(EYE_Y + 10)} "
        f"{fmt(CX - HALF_W * 0.80)},{fmt(EYE_Y + 10)} "
        f"{fmt(CX - HALF_W * 0.95)},{fmt(BROW_Y + 34)} Z",
        SKIN_DEEP, 22, 0.45, clip=clip,
    )

    # Snout: broad, upturned, with a bridge running up between the eyes.
    snout = (
        f"M {fmt(CX)},{fmt(BROW_Y + 30)} "
        f"C {fmt(CX + 34)},{fmt(NOSE_Y - 90)} {fmt(CX + 86)},{fmt(NOSE_Y - 32)} "
        f"{fmt(CX + 104)},{fmt(NOSE_Y + 22)} "
        f"C {fmt(CX + 112)},{fmt(NOSE_Y + 56)} {fmt(CX + 62)},{fmt(NOSE_Y + 70)} "
        f"{fmt(CX)},{fmt(NOSE_Y + 66)} "
        f"C {fmt(CX - 62)},{fmt(NOSE_Y + 70)} {fmt(CX - 112)},{fmt(NOSE_Y + 56)} "
        f"{fmt(CX - 104)},{fmt(NOSE_Y + 22)} "
        f"C {fmt(CX - 86)},{fmt(NOSE_Y - 32)} {fmt(CX - 34)},{fmt(NOSE_Y - 90)} "
        f"{fmt(CX)},{fmt(BROW_Y + 30)} Z"
    )
    layer.soft(snout, SKIN_DEEP, 18, 0.32, clip=clip)
    layer.soft(
        f"M {fmt(CX - 16)},{fmt(BROW_Y + 40)} "
        f"C {fmt(CX - 30)},{fmt(NOSE_Y - 40)} {fmt(CX - 40)},{fmt(NOSE_Y)} "
        f"{fmt(CX - 44)},{fmt(NOSE_Y + 30)} "
        f"L {fmt(CX + 10)},{fmt(NOSE_Y + 30)} "
        f"C {fmt(CX + 8)},{fmt(NOSE_Y - 40)} {fmt(CX + 8)},{fmt(BROW_Y + 40)} "
        f"{fmt(CX - 16)},{fmt(BROW_Y + 40)} Z",
        SKIN_LIGHT, 14, 0.45, clip=clip,
    )
    # Nostrils, angled outward, with the fleshy wing above each one.
    for sign in (-1, 1):
        layer.draw(
            f"M {fmt(CX + sign * 34)},{fmt(NOSE_Y + 44)} "
            f"C {fmt(CX + sign * 40)},{fmt(NOSE_Y + 18)} "
            f"{fmt(CX + sign * 74)},{fmt(NOSE_Y + 14)} "
            f"{fmt(CX + sign * 82)},{fmt(NOSE_Y + 44)} "
            f"C {fmt(CX + sign * 78)},{fmt(NOSE_Y + 58)} "
            f"{fmt(CX + sign * 44)},{fmt(NOSE_Y + 58)} "
            f"{fmt(CX + sign * 34)},{fmt(NOSE_Y + 44)} Z",
            fill=SKIN_DEEP, opacity=0.85,
        )
        layer.soft(
            f"M {fmt(CX + sign * 28)},{fmt(NOSE_Y + 30)} "
            f"C {fmt(CX + sign * 60)},{fmt(NOSE_Y - 4)} "
            f"{fmt(CX + sign * 104)},{fmt(NOSE_Y + 6)} "
            f"{fmt(CX + sign * 108)},{fmt(NOSE_Y + 44)} "
            f"L {fmt(CX + sign * 70)},{fmt(NOSE_Y + 48)} Z",
            SKIN_LIGHT, 10, 0.35, clip=clip,
        )

    # War paint: two slashes over the cheekbones, following the face curve.
    for sign in (-1, 1):
        layer.draw(
            f"M {fmt(CX + sign * 118)},{fmt(EYE_Y - 62)} "
            f"C {fmt(CX + sign * 186)},{fmt(EYE_Y - 48)} "
            f"{fmt(CX + sign * 236)},{fmt(EYE_Y + 10)} "
            f"{fmt(CX + sign * 250)},{fmt(EYE_Y + 92)} "
            f"L {fmt(CX + sign * 196)},{fmt(EYE_Y + 96)} "
            f"C {fmt(CX + sign * 182)},{fmt(EYE_Y + 30)} "
            f"{fmt(CX + sign * 150)},{fmt(EYE_Y - 8)} "
            f"{fmt(CX + sign * 104)},{fmt(EYE_Y - 22)} Z",
            fill=WAR_PAINT, opacity=0.82, clip=clip,
        )

    # Scar across the left brow, and a sprinkle of warts.
    layer.draw(
        f"M {fmt(CX - 214)},{fmt(BROW_Y - 44)} L {fmt(CX - 176)},{fmt(EYE_Y + 34)}",
        stroke=SKIN_DEEP, width=9, opacity=0.55, clip=clip,
    )
    layer.draw(
        f"M {fmt(CX - 214)},{fmt(BROW_Y - 44)} L {fmt(CX - 176)},{fmt(EYE_Y + 34)}",
        stroke=SKIN_LIGHT, width=4, opacity=0.7, clip=clip,
        extra=f'transform="translate(5,-3)"',
    )
    for x, y, r in ((CX - 196, NOSE_Y + 26, 15), (CX - 158, NOSE_Y + 84, 11),
                    (CX + 206, NOSE_Y - 22, 13), (CX + 168, NOSE_Y + 62, 9),
                    (CX - 60, BROW_Y - 96, 10)):
        _wart(layer, x, y, r)

    # Chin and jaw mass, then a pass of grain so the green is not a flat field.
    layer.soft(
        f"M {fmt(CX - 150)},{fmt(CHIN - 96)} "
        f"C {fmt(CX - 80)},{fmt(CHIN - 30)} {fmt(CX + 80)},{fmt(CHIN - 30)} "
        f"{fmt(CX + 150)},{fmt(CHIN - 96)} "
        f"C {fmt(CX + 110)},{fmt(CHIN + 4)} {fmt(CX - 110)},{fmt(CHIN + 4)} "
        f"{fmt(CX - 150)},{fmt(CHIN - 96)} Z",
        SKIN_LIGHT, 20, 0.35, clip=clip,
    )
    layer.draw(HEAD_D, fill="none", stroke=LINE, width=7, opacity=0.9)
    face.grain_over(layer, HEAD_D, opacity=0.16, frequency=1.6, strength=0.7)
    return layer


def ear(side: int) -> Layer:
    """One ear. `side` is -1 for the viewer-left ear, +1 for the right; the art
    is authored on the right and mirrored, so both stay identical."""
    layer = Layer("ear")
    g = layer.sub()
    base_x, base_y = CX + 236, 556.0
    shape = (
        f"M {fmt(base_x)},{fmt(base_y - 62)} "
        f"C {fmt(base_x + 84)},{fmt(base_y - 132)} {fmt(base_x + 178)},{fmt(base_y - 176)} "
        f"{fmt(base_x + 214)},{fmt(base_y - 150)} "
        f"C {fmt(base_x + 232)},{fmt(base_y - 108)} {fmt(base_x + 160)},{fmt(base_y - 24)} "
        f"{fmt(base_x + 96)},{fmt(base_y + 46)} "
        f"C {fmt(base_x + 60)},{fmt(base_y + 84)} {fmt(base_x + 10)},{fmt(base_y + 74)} "
        f"{fmt(base_x - 6)},{fmt(base_y + 32)} Z"
    )
    clip = g.clip(shape)
    fill = g.linear([(0.0, SKIN_LIGHT), (0.6, SKIN), (1.0, SKIN_DARK)],
                    base_x, base_y - 160, base_x + 60, base_y + 60)
    g.draw(shape, fill=fill)
    # Inner hollow, slightly translucent at the thin edge like real cartilage.
    g.soft(
        f"M {fmt(base_x + 22)},{fmt(base_y - 40)} "
        f"C {fmt(base_x + 92)},{fmt(base_y - 104)} {fmt(base_x + 162)},{fmt(base_y - 140)} "
        f"{fmt(base_x + 186)},{fmt(base_y - 124)} "
        f"C {fmt(base_x + 176)},{fmt(base_y - 86)} {fmt(base_x + 112)},{fmt(base_y - 12)} "
        f"{fmt(base_x + 66)},{fmt(base_y + 34)} Z",
        SKIN_DEEP, 14, 0.45, clip=clip,
    )
    g.draw(
        f"M {fmt(base_x + 150)},{fmt(base_y - 148)} "
        f"C {fmt(base_x + 196)},{fmt(base_y - 150)} {fmt(base_x + 214)},{fmt(base_y - 128)} "
        f"{fmt(base_x + 198)},{fmt(base_y - 96)}",
        stroke="#e6ffb4", width=9, opacity=0.55, clip=clip,
    )
    g.draw(shape, fill="none", stroke=LINE, width=7, opacity=0.9)
    # Gold ring through the upper edge.
    g.raw(
        f'<ellipse cx="{fmt(base_x + 150)}" cy="{fmt(base_y - 92)}" rx="30" ry="34" '
        f'fill="none" stroke="{GOLD_DARK}" stroke-width="13" '
        f'transform="rotate(-24 {fmt(base_x + 150)} {fmt(base_y - 92)})"/>'
    )
    g.raw(
        f'<ellipse cx="{fmt(base_x + 148)}" cy="{fmt(base_y - 94)}" rx="30" ry="34" '
        f'fill="none" stroke="{GOLD}" stroke-width="8" '
        f'transform="rotate(-24 {fmt(base_x + 148)} {fmt(base_y - 94)})"/>'
    )
    markup = layer.take(g)
    if side < 0:
        layer.group(markup, transform=mirror(CX))
    else:
        layer.raw(markup)
    return layer


EYE_SPEC = face.EyeSpec(
    cx=CX - EYE_DX, cy=EYE_Y, w=178, h=104,
    iris_light="#ffd14a", iris_dark="#d2521a", iris_rim="#5e1607",
    pupil="#160a06", sclera_light="#fff4cf", sclera_shade="#dcc37f",
    lash=LINE, lash_width=15, lid_lift=0.30, iris_scale=0.82,
)


def eyes(closed: bool) -> Layer:
    """Sclera + lids only - the iris is a separate layer (see iris()) so the
    "eyes dart" animation can slide just the pupil inside a fixed socket
    instead of sliding the whole eye (lashes included) across the face."""
    layer = Layer("eyes")
    if closed:
        markup = face.eye_closed(layer, EYE_SPEC)
    else:
        markup = face.eye_socket_open(layer, EYE_SPEC)
    layer.raw(markup)
    layer.group(markup, transform=mirror(CX))
    return layer


def iris() -> Layer:
    """The gaze_layer: drawn underneath the open-eye socket so it peeks
    through the hole punched there, and nudged left/right by the renderer for
    a wandering, slightly nervous look. Not drawn at all during a blink -
    the closed lid (on top, in z-order) fully covers this layer's area."""
    layer = Layer("iris")
    markup = face.eye_iris(layer, EYE_SPEC)
    layer.raw(markup)
    layer.group(markup, transform=mirror(CX))
    return layer


def brows() -> Layer:
    layer = Layer("brows")
    markup = face.brow(layer, CX - EYE_DX - 6, BROW_Y, 196, HAIR,
                       thickness=40, angle=34, arch=0.30, taper=0.5)
    layer.raw(markup)
    layer.group(markup, transform=mirror(CX))
    return layer


def _tusks(layer: Layer) -> None:
    """Lower tusks poking up from the mouth corners, drawn into both mouth
    frames so they never pop in and out. Sized to clear the lower lip without
    reaching anywhere near the eyes — a common mistake once tip_y drifts too
    far up the face."""
    for sign in (-1, 1):
        x = CX + sign * 122
        tip_y = MOUTH_Y - 92
        base_y = MOUTH_Y + 34
        shape = (
            f"M {fmt(x - 26)},{fmt(base_y)} "
            f"C {fmt(x - 30)},{fmt(base_y - 60)} {fmt(x - 18)},{fmt(tip_y + 22)} "
            f"{fmt(x + sign * 3)},{fmt(tip_y)} "
            f"C {fmt(x + 20)},{fmt(tip_y + 26)} {fmt(x + 24)},{fmt(base_y - 56)} "
            f"{fmt(x + 22)},{fmt(base_y)} Z"
        )
        fill = layer.linear([(0.0, TUSK_LIGHT), (0.65, TUSK), (1.0, TUSK_DARK)],
                            x - 28, tip_y, x + 28, base_y)
        layer.soft(shape, "#20180c", 10, 0.3)
        layer.draw(shape, fill=fill, stroke=LINE, width=6, opacity=0.95)
        layer.draw(
            f"M {fmt(x - 12)},{fmt(base_y - 14)} "
            f"C {fmt(x - 14)},{fmt(base_y - 46)} {fmt(x - 6)},{fmt(tip_y + 30)} "
            f"{fmt(x - 1)},{fmt(tip_y + 14)}",
            stroke="#ffffff", width=6, opacity=0.6,
        )


def drool() -> Layer:
    """A thread of drool off the right tusk, ending in a hanging drop. Its own
    layer (not baked into the mouth art) so it can sway independently and
    spawn falling-droplet echoes — see MANIFEST's sway/effect entries."""
    layer = Layer("drool")
    x = CX + 148
    strand = (
        f"M {fmt(x)},{fmt(MOUTH_Y + 34)} "
        f"C {fmt(x + 8)},{fmt(MOUTH_Y + 96)} {fmt(x - 4)},{fmt(MOUTH_Y + 142)} "
        f"{fmt(x + 2)},{fmt(MOUTH_Y + 186)}"
    )
    fill = layer.radial([(0.0, "#ffffff", 0.9), (1.0, "#9fd6e8", 0.75)],
                        x - 6, MOUTH_Y + 196, 34)
    layer.draw(strand, stroke="#cfeaf4", width=11, opacity=0.8)
    layer.draw(strand, stroke="#ffffff", width=4, opacity=0.85)
    layer.draw(
        f"M {fmt(x + 2)},{fmt(MOUTH_Y + 176)} "
        f"C {fmt(x + 30)},{fmt(MOUTH_Y + 206)} {fmt(x + 26)},{fmt(MOUTH_Y + 246)} "
        f"{fmt(x)},{fmt(MOUTH_Y + 248)} "
        f"C {fmt(x - 26)},{fmt(MOUTH_Y + 246)} {fmt(x - 30)},{fmt(MOUTH_Y + 206)} "
        f"{fmt(x - 2)},{fmt(MOUTH_Y + 176)} Z",
        fill=fill, stroke="#bfe4f0", width=4, opacity=0.92,
    )
    layer.ellipse(x - 9, MOUTH_Y + 214, 7, 11, "#ffffff", opacity=0.9)
    return layer


def mouth(open_: bool) -> Layer:
    layer = Layer("mouth")
    if open_:
        cavity = (
            f"M {fmt(CX - 168)},{fmt(MOUTH_Y - 6)} "
            f"C {fmt(CX - 96)},{fmt(MOUTH_Y - 44)} {fmt(CX + 96)},{fmt(MOUTH_Y - 44)} "
            f"{fmt(CX + 168)},{fmt(MOUTH_Y - 6)} "
            f"C {fmt(CX + 150)},{fmt(MOUTH_Y + 122)} {fmt(CX + 74)},{fmt(MOUTH_Y + 168)} "
            f"{fmt(CX)},{fmt(MOUTH_Y + 168)} "
            f"C {fmt(CX - 74)},{fmt(MOUTH_Y + 168)} {fmt(CX - 150)},{fmt(MOUTH_Y + 122)} "
            f"{fmt(CX - 168)},{fmt(MOUTH_Y - 6)} Z"
        )
        clip = layer.clip(cavity)
        inner = layer.radial([(0.0, "#7a1f2c"), (0.7, "#3d0d16"), (1.0, "#1c050b")],
                             CX, MOUTH_Y + 30, 190)
        layer.draw(cavity, fill=inner)
        # Tongue.
        layer.ellipse(CX, MOUTH_Y + 150, 116, 74, "#c8566a", clip=clip)
        layer.ellipse(CX, MOUTH_Y + 138, 96, 52, "#e0798a", opacity=0.85,
                      blur=layer.blur(12), clip=clip)
        layer.draw(
            f"M {fmt(CX)},{fmt(MOUTH_Y + 96)} L {fmt(CX)},{fmt(MOUTH_Y + 172)}",
            stroke="#a63e52", width=8, opacity=0.6, clip=clip,
        )
        # Upper teeth: uneven, because an orc has no orthodontist.
        for i, (dx, w, hgt) in enumerate(
            ((-128, 40, 46), (-84, 44, 58), (-38, 40, 50), (6, 42, 54),
             (50, 38, 44), (92, 42, 52), (134, 36, 40))
        ):
            x = CX + dx
            layer.draw(
                f"M {fmt(x)},{fmt(MOUTH_Y - 34)} L {fmt(x + w)},{fmt(MOUTH_Y - 34)} "
                f"L {fmt(x + w - 5)},{fmt(MOUTH_Y - 34 + hgt)} "
                f"Q {fmt(x + w / 2)},{fmt(MOUTH_Y - 24 + hgt)} "
                f"{fmt(x + 5)},{fmt(MOUTH_Y - 34 + hgt)} Z",
                fill=TUSK_LIGHT if i % 2 else TUSK, stroke=TUSK_DARK, width=3, clip=clip,
            )
        layer.soft(
            f"M {fmt(CX - 180)},{fmt(MOUTH_Y - 30)} L {fmt(CX + 180)},{fmt(MOUTH_Y - 30)} "
            f"L {fmt(CX + 180)},{fmt(MOUTH_Y + 16)} L {fmt(CX - 180)},{fmt(MOUTH_Y + 16)} Z",
            "#000000", 16, 0.5, clip=clip,
        )
        layer.draw(cavity, fill="none", stroke=LINE, width=8)
    else:
        line = (
            f"M {fmt(CX - 170)},{fmt(MOUTH_Y + 4)} "
            f"C {fmt(CX - 96)},{fmt(MOUTH_Y + 46)} {fmt(CX + 96)},{fmt(MOUTH_Y + 46)} "
            f"{fmt(CX + 170)},{fmt(MOUTH_Y + 4)}"
        )
        layer.draw(line, stroke=LINE, width=13)
        layer.draw(
            f"M {fmt(CX - 150)},{fmt(MOUTH_Y + 44)} "
            f"C {fmt(CX - 80)},{fmt(MOUTH_Y + 82)} {fmt(CX + 80)},{fmt(MOUTH_Y + 82)} "
            f"{fmt(CX + 150)},{fmt(MOUTH_Y + 44)}",
            stroke=SKIN_LIGHT, width=14, opacity=0.4,
        )
        layer.soft(
            f"M {fmt(CX - 160)},{fmt(MOUTH_Y + 10)} "
            f"C {fmt(CX - 80)},{fmt(MOUTH_Y + 54)} {fmt(CX + 80)},{fmt(MOUTH_Y + 54)} "
            f"{fmt(CX + 160)},{fmt(MOUTH_Y + 10)} "
            f"L {fmt(CX + 160)},{fmt(MOUTH_Y + 30)} L {fmt(CX - 160)},{fmt(MOUTH_Y + 30)} Z",
            SKIN_DEEP, 10, 0.35,
        )
    _tusks(layer)
    return layer


def topknot() -> Layer:
    """The sway layer. It has to stick upward: the renderer roots a sway layer
    at the lowest row of its opaque pixels, so anything hanging down would
    swing about its tip instead of its base."""
    layer = Layer("topknot")
    base_y = TOP + 34
    shape = (
        f"M {fmt(CX - 58)},{fmt(base_y)} "
        f"C {fmt(CX - 70)},{fmt(base_y - 96)} {fmt(CX - 44)},{fmt(base_y - 188)} "
        f"{fmt(CX + 24)},{fmt(base_y - 244)} "
        f"C {fmt(CX - 4)},{fmt(base_y - 170)} {fmt(CX + 22)},{fmt(base_y - 120)} "
        f"{fmt(CX + 62)},{fmt(base_y - 78)} "
        f"C {fmt(CX + 78)},{fmt(base_y - 44)} {fmt(CX + 40)},{fmt(base_y + 6)} "
        f"{fmt(CX - 58)},{fmt(base_y)} Z"
    )
    fill = layer.linear([(0.0, HAIR_LIGHT), (0.55, HAIR), (1.0, "#140e0c")],
                        CX - 40, base_y - 230, CX + 60, base_y)
    layer.draw(shape, fill=fill, stroke="#140e0c", width=6)
    layer.draw(
        f"M {fmt(CX - 30)},{fmt(base_y - 26)} "
        f"C {fmt(CX - 34)},{fmt(base_y - 120)} {fmt(CX - 10)},{fmt(base_y - 186)} "
        f"{fmt(CX + 18)},{fmt(base_y - 224)}",
        stroke="#6b5045", width=10, opacity=0.7,
    )
    # Leather tie at the root.
    layer.draw(
        f"M {fmt(CX - 62)},{fmt(base_y - 30)} "
        f"C {fmt(CX - 20)},{fmt(base_y - 52)} {fmt(CX + 34)},{fmt(base_y - 44)} "
        f"{fmt(CX + 64)},{fmt(base_y - 22)} "
        f"L {fmt(CX + 58)},{fmt(base_y + 12)} "
        f"C {fmt(CX + 20)},{fmt(base_y - 10)} {fmt(CX - 26)},{fmt(base_y - 14)} "
        f"{fmt(CX - 60)},{fmt(base_y + 4)} Z",
        fill=LEATHER, stroke=LEATHER_DARK, width=5,
    )
    return layer


def body() -> Layer:
    layer = Layer("body")
    neck = (
        f"M {fmt(CX - 132)},{fmt(CHIN - 90)} "
        f"C {fmt(CX - 140)},{fmt(CHIN + 60)} {fmt(CX - 160)},{fmt(CHIN + 96)} "
        f"{fmt(CX - 190)},{fmt(CHIN + 128)} "
        f"L {fmt(CX + 190)},{fmt(CHIN + 128)} "
        f"C {fmt(CX + 160)},{fmt(CHIN + 96)} {fmt(CX + 140)},{fmt(CHIN + 60)} "
        f"{fmt(CX + 132)},{fmt(CHIN - 90)} Z"
    )
    neck_fill = layer.linear([(0.0, SKIN_DARK), (1.0, SKIN_MID)],
                             CX, CHIN - 60, CX, CHIN + 120)
    layer.draw(neck, fill=neck_fill)

    torso = (
        f"M {fmt(CX - 250)},{fmt(1280)} "
        f"C {fmt(CX - 262)},{fmt(1060)} {fmt(CX - 330)},{fmt(986)} "
        f"{fmt(CX - 432)},{fmt(952)} "
        f"C {fmt(CX - 306)},{fmt(918)} {fmt(CX - 208)},{fmt(900)} "
        f"{fmt(CX - 150)},{fmt(CHIN + 112)} "
        f"C {fmt(CX - 70)},{fmt(CHIN + 150)} {fmt(CX + 70)},{fmt(CHIN + 150)} "
        f"{fmt(CX + 150)},{fmt(CHIN + 112)} "
        f"C {fmt(CX + 208)},{fmt(900)} {fmt(CX + 306)},{fmt(918)} "
        f"{fmt(CX + 432)},{fmt(952)} "
        f"C {fmt(CX + 330)},{fmt(986)} {fmt(CX + 262)},{fmt(1060)} "
        f"{fmt(CX + 250)},{fmt(1280)} Z"
    )
    clip = layer.clip(torso)
    torso_fill = layer.radial([(0.0, SKIN_LIGHT), (0.5, SKIN), (1.0, SKIN_DARK)],
                              CX - 90, 960, 520)
    layer.draw(torso, fill=torso_fill)
    # Trapezius mass and the shadow the head casts on the chest.
    layer.soft(
        f"M {fmt(CX - 190)},{fmt(CHIN + 90)} "
        f"C {fmt(CX - 90)},{fmt(CHIN + 190)} {fmt(CX + 90)},{fmt(CHIN + 190)} "
        f"{fmt(CX + 190)},{fmt(CHIN + 90)} "
        f"L {fmt(CX + 190)},{fmt(CHIN - 10)} L {fmt(CX - 190)},{fmt(CHIN - 10)} Z",
        SKIN_DEEP, 26, 0.5, clip=clip,
    )
    # Pectoral split and collarbones.
    layer.soft(
        f"M {fmt(CX)},{fmt(1030)} L {fmt(CX)},{fmt(1280)}",
        SKIN_DEEP, 14, 0.5, clip=clip,
    )
    layer.draw(
        f"M {fmt(CX)},{fmt(1040)} L {fmt(CX)},{fmt(1280)}",
        stroke=SKIN_DEEP, width=10, opacity=0.35, clip=clip,
    )
    for sign in (-1, 1):
        layer.draw(
            f"M {fmt(CX + sign * 40)},{fmt(1002)} "
            f"C {fmt(CX + sign * 160)},{fmt(986)} {fmt(CX + sign * 250)},{fmt(1006)} "
            f"{fmt(CX + sign * 320)},{fmt(1042)}",
            stroke=SKIN_DEEP, width=11, opacity=0.35, clip=clip,
        )
        layer.soft(
            f"M {fmt(CX + sign * 40)},{fmt(1016)} "
            f"C {fmt(CX + sign * 160)},{fmt(1000)} {fmt(CX + sign * 250)},{fmt(1020)} "
            f"{fmt(CX + sign * 320)},{fmt(1056)} "
            f"L {fmt(CX + sign * 320)},{fmt(1000)} Z",
            SKIN_LIGHT, 16, 0.3, clip=clip,
        )

    # Leather harness across the chest, with studs.
    strap = (
        f"M {fmt(CX - 330)},{fmt(1004)} "
        f"C {fmt(CX - 150)},{fmt(1092)} {fmt(CX + 80)},{fmt(1180)} "
        f"{fmt(CX + 190)},{fmt(1280)} "
        f"L {fmt(CX + 52)},{fmt(1280)} "
        f"C {fmt(CX - 40)},{fmt(1178)} {fmt(CX - 250)},{fmt(1090)} "
        f"{fmt(CX - 382)},{fmt(1046)} Z"
    )
    strap_fill = layer.linear([(0.0, "#8a5f3e"), (0.5, LEATHER), (1.0, LEATHER_DARK)],
                              CX - 300, 1000, CX + 120, 1240)
    layer.draw(strap, fill=strap_fill, stroke=LEATHER_DARK, width=7, clip=clip)
    for t in range(5):
        x = CX - 300 + t * 96
        y = 1040 + t * 46
        layer.ellipse(x, y, 16, 16, GOLD, clip=clip)
        layer.ellipse(x - 4, y - 5, 7, 6, "#fff0c0", opacity=0.9, clip=clip)

    # Fur-trimmed pauldron on the viewer-left shoulder.
    pauldron = (
        f"M {fmt(CX - 452)},{fmt(1010)} "
        f"C {fmt(CX - 420)},{fmt(922)} {fmt(CX - 300)},{fmt(884)} "
        f"{fmt(CX - 206)},{fmt(916)} "
        f"C {fmt(CX - 236)},{fmt(1010)} {fmt(CX - 250)},{fmt(1104)} "
        f"{fmt(CX - 244)},{fmt(1180)} "
        f"C {fmt(CX - 340)},{fmt(1150)} {fmt(CX - 420)},{fmt(1090)} "
        f"{fmt(CX - 452)},{fmt(1010)} Z"
    )
    p_fill = layer.linear([(0.0, "#8a5f3e"), (0.6, LEATHER), (1.0, "#2f1f14")],
                          CX - 440, 900, CX - 240, 1170)
    layer.soft(pauldron, "#1a1109", 22, 0.45)
    layer.draw(pauldron, fill=p_fill, stroke=LEATHER_DARK, width=8)
    layer.draw(
        f"M {fmt(CX - 410)},{fmt(972)} "
        f"C {fmt(CX - 356)},{fmt(936)} {fmt(CX - 288)},{fmt(930)} "
        f"{fmt(CX - 236)},{fmt(950)}",
        stroke="#a87a4f", width=12, opacity=0.65,
    )
    fur = []
    for i in range(11):
        t = i / 10
        x = CX - 452 + t * 250
        y = 1008 - t * 96
        fur.append(
            f"M {fmt(x)},{fmt(y)} "
            f"C {fmt(x - 22)},{fmt(y - 46)} {fmt(x + 4)},{fmt(y - 74)} "
            f"{fmt(x + 30)},{fmt(y - 40)} "
            f"C {fmt(x + 38)},{fmt(y - 14)} {fmt(x + 26)},{fmt(y + 2)} "
            f"{fmt(x)},{fmt(y)} Z"
        )
    layer.draw(" ".join(fur), fill=FUR, stroke="#8f7550", width=4, opacity=0.95)
    face.grain_over(layer, torso, opacity=0.12, frequency=1.8, strength=0.7)
    return layer


def back() -> Layer:
    """Everything behind the head: the far shoulder mass and a hint of hair."""
    layer = Layer("back")
    shape = (
        f"M {fmt(CX - 470)},{fmt(1280)} "
        f"C {fmt(CX - 470)},{fmt(1020)} {fmt(CX - 330)},{fmt(910)} "
        f"{fmt(CX)},{fmt(896)} "
        f"C {fmt(CX + 330)},{fmt(910)} {fmt(CX + 470)},{fmt(1020)} "
        f"{fmt(CX + 470)},{fmt(1280)} Z"
    )
    fill = layer.linear([(0.0, SKIN_DARK), (1.0, SKIN_DEEP)], CX, 890, CX, 1280)
    layer.draw(shape, fill=fill, opacity=0.9)
    return layer


LAYERS = {
    "01Back.png": back,
    "02Body.png": body,
    "03Ear_Right.png": lambda: ear(1),
    "12Ear_Left.png": lambda: ear(-1),
    "05Head.png": head,
    "20Iris.png": iris,
    "06Eyes_Open.png": lambda: eyes(False),
    "07Eyes_Closed.png": lambda: eyes(True),
    "08Brows.png": brows,
    "09Mouth_Open.png": lambda: mouth(True),
    "10Mouth_Closed.png": lambda: mouth(False),
    "16Topknot.png": topknot,
    "17Drool.png": drool,
}

MANIFEST = {
    "name": "Orc",
    "base_layers": [
        # 20Iris.png sits right before the eyes state so it renders
        # underneath it - the open-eye socket has a hole punched in it that
        # this shows through, and the closed-eye lid fully covers it during
        # a blink. See gaze_layer below.
        "01Back.png", "02Body.png", "03Ear_Right.png", "12Ear_Left.png",
        "05Head.png", "20Iris.png", "08Brows.png", "16Topknot.png", "17Drool.png",
    ],
    "states": {
        "eyes": {"order": 6, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
        "mouth": {"order": 7, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
    },
    # The leather-tied topknot rocks like a loose cap slipping on the head.
    # The drool strand hangs from the tusk (pivot "top" — it hangs down, so
    # rotating around its lowest pixel would swing the wrong end) and swings
    # off the bounce/talk signal instead of its own clock, so it visibly
    # reacts to the orc actually bouncing/talking rather than swaying
    # regardless — just the one strand, no separate detaching-drop effect.
    "sway_layers": [
        {"file": "16Topknot.png", "degrees": 9, "period": 3.4, "pivot": "bottom"},
        {"file": "17Drool.png", "degrees": 1.4, "pivot": "top", "follow_bounce": True},
    ],
    "bounce_react_layers": ["03Ear_Right.png", "12Ear_Left.png"],
    # A nervous, wandering gaze: only the iris moves, the socket stays put.
    "gaze_layer": "20Iris.png",
}
