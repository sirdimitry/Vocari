"""The programmer avatar, styled after the user's supplied reference photo:
hair swept back, a goatee-and-moustache combo, grey-blue eyes, a denim jacket
over a dark tee. Deliberately the least stylised of the three - smaller
eyes, more naturalistic proportions - since the brief was "not too cartoony".
"""
from __future__ import annotations

from tools.art import face
from tools.art.svgkit import Layer, fmt, head_path, mirror

CX = 640.0
TOP = 258.0
CHIN = 820.0
HALF_W = 244.0
H = CHIN - TOP

EYE_Y = 574.0
EYE_DX = 112.0
BROW_Y = 522.0
NOSE_Y = 640.0
MOUTH_Y = 716.0

SKIN_LIGHT = "#f2c9a8"
SKIN = "#e0ab84"
SKIN_MID = "#c68f68"
SKIN_DARK = "#a06f4d"
SKIN_DEEP = "#7c5238"
LINE = "#3a281d"

HAIR = "#8a6a45"
HAIR_LIGHT = "#c79a63"
HAIR_DARK = "#5c4429"

DENIM = "#5b7a9c"
DENIM_LIGHT = "#7fa0bf"
DENIM_DARK = "#3c5470"
TEE = "#26282e"

# Smaller, calmer eye than the anime-scaled Ariral/Orc ones — reads as an
# adult human rather than a cartoon.
EYE_W = 118.0
EYE_H = 58.0

HEAD_D = head_path(CX, TOP, CHIN, HALF_W, temple=0.90, cheek=0.98, jaw=0.66, chin_round=0.30)


def head() -> Layer:
    layer = Layer("head")
    clip = face.skin(
        layer, HEAD_D, base=SKIN, light=SKIN_LIGHT, shadow=SKIN_MID, deep=SKIN_DEEP,
        cx=CX, top=TOP, chin=CHIN, half_w=HALF_W, rim="#ffe8cf", rim_opacity=0.35,
    )

    # Cheekbone + nose bridge shading, kept subtle - the least cartoony face
    # of the three leans on soft gradient work rather than graphic shapes.
    layer.soft(
        f"M {fmt(CX - 12)},{fmt(BROW_Y + 10)} L {fmt(CX - 20)},{fmt(NOSE_Y + 20)} "
        f"L {fmt(CX + 6)},{fmt(NOSE_Y + 20)} L {fmt(CX - 2)},{fmt(BROW_Y + 10)} Z",
        SKIN_DARK, 10, 0.25, clip=clip,
    )
    for sign in (-1, 1):
        layer.soft(
            f"M {fmt(CX + sign * 70)},{fmt(EYE_Y + 30)} "
            f"C {fmt(CX + sign * 130)},{fmt(EYE_Y + 46)} {fmt(CX + sign * 150)},{fmt(NOSE_Y + 40)} "
            f"{fmt(CX + sign * 120)},{fmt(MOUTH_Y - 10)} "
            f"L {fmt(CX + sign * 60)},{fmt(MOUTH_Y - 30)} Z",
            SKIN_MID, 16, 0.28, clip=clip,
        )
    # Nose: a simple bridge + tip + one nostril shadow each side, no outline.
    layer.soft(
        f"M {fmt(CX - 14)},{fmt(NOSE_Y - 10)} "
        f"C {fmt(CX - 26)},{fmt(NOSE_Y + 24)} {fmt(CX - 24)},{fmt(NOSE_Y + 44)} "
        f"{fmt(CX)},{fmt(NOSE_Y + 52)} "
        f"C {fmt(CX + 24)},{fmt(NOSE_Y + 44)} {fmt(CX + 26)},{fmt(NOSE_Y + 24)} "
        f"{fmt(CX + 14)},{fmt(NOSE_Y - 10)} Z",
        SKIN_DARK, 10, 0.3, clip=clip,
    )
    layer.ellipse(CX, NOSE_Y + 48, 22, 10, SKIN_LIGHT, opacity=0.6, blur=layer.blur(8), clip=clip)
    for sign in (-1, 1):
        layer.ellipse(CX + sign * 13, NOSE_Y + 50, 6, 5, SKIN_DEEP, opacity=0.5, clip=clip)

    # Faint smile lines and a hint of stubble shadow around the jaw (a
    # goateed adult reads oddly clean-shaven without it).
    layer.soft(HEAD_D, SKIN_DARK, 14, 0.16, clip=clip)
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.5)},{fmt(CHIN - H * 0.10)} "
        f"C {fmt(CX - HALF_W * 0.2)},{fmt(CHIN + H * 0.02)} "
        f"{fmt(CX + HALF_W * 0.2)},{fmt(CHIN + H * 0.02)} "
        f"{fmt(CX + HALF_W * 0.5)},{fmt(CHIN - H * 0.10)} "
        f"L {fmt(CX + HALF_W * 0.5)},{fmt(CHIN + H * 0.16)} "
        f"L {fmt(CX - HALF_W * 0.5)},{fmt(CHIN + H * 0.16)} Z",
        "#5c4028", 14, 0.14, clip=clip,
    )
    face.grain_over(layer, HEAD_D, opacity=0.12, frequency=2.0, strength=0.45)
    layer.draw(HEAD_D, fill="none", stroke=LINE, width=4, opacity=0.35)
    return layer


def ear(side: int) -> Layer:
    layer = Layer("ear")
    g = layer.sub()
    x, y = CX + HALF_W * 0.98, EYE_Y + 40
    shape = (
        f"M {fmt(x - 8)},{fmt(y - 58)} "
        f"C {fmt(x + 36)},{fmt(y - 60)} {fmt(x + 46)},{fmt(y - 10)} "
        f"{fmt(x + 32)},{fmt(y + 36)} "
        f"C {fmt(x + 20)},{fmt(y + 70)} {fmt(x - 4)},{fmt(y + 72)} "
        f"{fmt(x - 14)},{fmt(y + 48)} Z"
    )
    clip = g.clip(shape)
    fill = g.radial([(0.0, SKIN_LIGHT), (0.7, SKIN), (1.0, SKIN_MID)], x, y, 60)
    g.draw(shape, fill=fill)
    g.soft(
        f"M {fmt(x + 4)},{fmt(y - 30)} C {fmt(x + 22)},{fmt(y - 28)} {fmt(x + 26)},{fmt(y - 4)} "
        f"{fmt(x + 14)},{fmt(y + 14)}",
        SKIN_DARK, 8, 0.4, clip=clip,
    )
    g.draw(shape, fill="none", stroke=LINE, width=3, opacity=0.3)
    markup = layer.take(g)
    if side < 0:
        layer.group(markup, transform=mirror(CX))
    else:
        layer.raw(markup)
    return layer


def eyes(closed: bool) -> Layer:
    layer = Layer("eyes")
    spec = face.EyeSpec(
        cx=CX - EYE_DX, cy=EYE_Y, w=EYE_W, h=EYE_H,
        iris_light="#9fc3d6", iris_dark="#41667a", iris_rim="#1c2e38",
        pupil="#161414", sclera_light="#fffaf4", sclera_shade="#e6d9cb",
        lash=LINE, lash_width=9, lid_lift=0.06, iris_scale=0.90, highlight=0.85,
    )
    markup = face.eye_closed(layer, spec) if closed else face.eye_open(layer, spec)
    layer.raw(markup)
    layer.group(markup, transform=mirror(CX))
    return layer


def eye_shine() -> Layer:
    """The "occasional cool glint" effect layer - a bright diagonal sparkle
    over one eye, flashing rarely like a camera catchlight."""
    layer = Layer("eye_shine")
    for cx in (CX - EYE_DX, CX + EYE_DX):
        cy = EYE_Y - EYE_H * 0.1
        r = EYE_H * 0.5
        layer.draw(
            f"M {fmt(cx)},{fmt(cy - r)} L {fmt(cx + r * 0.22)},{fmt(cy - r * 0.22)} "
            f"L {fmt(cx + r)},{fmt(cy)} L {fmt(cx + r * 0.22)},{fmt(cy + r * 0.22)} "
            f"L {fmt(cx)},{fmt(cy + r)} L {fmt(cx - r * 0.22)},{fmt(cy + r * 0.22)} "
            f"L {fmt(cx - r)},{fmt(cy)} L {fmt(cx - r * 0.22)},{fmt(cy - r * 0.22)} Z",
            fill="#ffffff", opacity=0.95, blur=layer.blur(2),
        )
    return layer


def brows() -> Layer:
    layer = Layer("brows")
    markup = face.brow(layer, CX - EYE_DX - 4, BROW_Y, 116, HAIR_DARK,
                       thickness=16, angle=6, arch=0.4, taper=0.4)
    layer.raw(markup)
    layer.group(markup, transform=mirror(CX))
    return layer


def mouth(open_: bool) -> Layer:
    layer = Layer("mouth")
    if open_:
        cavity = (
            f"M {fmt(CX - 66)},{fmt(MOUTH_Y - 2)} "
            f"C {fmt(CX - 30)},{fmt(MOUTH_Y - 18)} {fmt(CX + 30)},{fmt(MOUTH_Y - 18)} "
            f"{fmt(CX + 66)},{fmt(MOUTH_Y - 2)} "
            f"C {fmt(CX + 56)},{fmt(MOUTH_Y + 44)} {fmt(CX + 24)},{fmt(MOUTH_Y + 64)} "
            f"{fmt(CX)},{fmt(MOUTH_Y + 64)} "
            f"C {fmt(CX - 24)},{fmt(MOUTH_Y + 64)} {fmt(CX - 56)},{fmt(MOUTH_Y + 44)} "
            f"{fmt(CX - 66)},{fmt(MOUTH_Y - 2)} Z"
        )
        clip = layer.clip(cavity)
        inner = layer.radial([(0.0, "#7a3a3a"), (1.0, "#2c1414")], CX, MOUTH_Y + 24, 80)
        layer.draw(cavity, fill=inner)
        layer.ellipse(CX, MOUTH_Y + 8, 52, 14, "#f2f2ee", clip=clip)
        layer.ellipse(CX, MOUTH_Y + 46, 44, 22, "#c85a5a", clip=clip)
        layer.draw(cavity, fill="none", stroke=LINE, width=4, opacity=0.5)
    else:
        line = (
            f"M {fmt(CX - 70)},{fmt(MOUTH_Y + 4)} "
            f"C {fmt(CX - 30)},{fmt(MOUTH_Y + 22)} {fmt(CX + 30)},{fmt(MOUTH_Y + 22)} "
            f"{fmt(CX + 70)},{fmt(MOUTH_Y + 4)}"
        )
        layer.draw(line, stroke=LINE, width=6, opacity=0.75)
        layer.draw(
            f"M {fmt(CX - 60)},{fmt(MOUTH_Y + 20)} "
            f"C {fmt(CX - 26)},{fmt(MOUTH_Y + 36)} {fmt(CX + 26)},{fmt(MOUTH_Y + 36)} "
            f"{fmt(CX + 60)},{fmt(MOUTH_Y + 20)}",
            stroke="#c47a5a", width=10, opacity=0.35,
        )

    # Moustache, drawn into both mouth frames so it never pops.
    stache = (
        f"M {fmt(CX - 92)},{fmt(MOUTH_Y - 20)} "
        f"C {fmt(CX - 50)},{fmt(MOUTH_Y - 42)} {fmt(CX - 14)},{fmt(MOUTH_Y - 38)} "
        f"{fmt(CX)},{fmt(MOUTH_Y - 24)} "
        f"C {fmt(CX + 14)},{fmt(MOUTH_Y - 38)} {fmt(CX + 50)},{fmt(MOUTH_Y - 42)} "
        f"{fmt(CX + 92)},{fmt(MOUTH_Y - 20)} "
        f"C {fmt(CX + 70)},{fmt(MOUTH_Y - 6)} {fmt(CX + 30)},{fmt(MOUTH_Y - 2)} "
        f"{fmt(CX)},{fmt(MOUTH_Y - 10)} "
        f"C {fmt(CX - 30)},{fmt(MOUTH_Y - 2)} {fmt(CX - 70)},{fmt(MOUTH_Y - 6)} "
        f"{fmt(CX - 92)},{fmt(MOUTH_Y - 20)} Z"
    )
    stache_fill = layer.linear([(0.0, HAIR_LIGHT), (0.6, HAIR), (1.0, HAIR_DARK)],
                               CX, MOUTH_Y - 44, CX, MOUTH_Y - 2)
    layer.draw(stache, fill=stache_fill, stroke=HAIR_DARK, width=3)
    return layer


def goatee() -> Layer:
    """Sway layer: the beard tuft, hanging from the chin (pivot "top")."""
    layer = Layer("goatee")
    shape = (
        f"M {fmt(CX - 58)},{fmt(MOUTH_Y + 26)} "
        f"C {fmt(CX - 66)},{fmt(MOUTH_Y + 78)} {fmt(CX - 40)},{fmt(CHIN + 62)} "
        f"{fmt(CX)},{fmt(CHIN + 86)} "
        f"C {fmt(CX + 40)},{fmt(CHIN + 62)} {fmt(CX + 66)},{fmt(MOUTH_Y + 78)} "
        f"{fmt(CX + 58)},{fmt(MOUTH_Y + 26)} "
        f"C {fmt(CX + 36)},{fmt(MOUTH_Y + 62)} {fmt(CX - 36)},{fmt(MOUTH_Y + 62)} "
        f"{fmt(CX - 58)},{fmt(MOUTH_Y + 26)} Z"
    )
    fill = layer.linear([(0.0, HAIR_LIGHT), (0.55, HAIR), (1.0, HAIR_DARK)],
                        CX, MOUTH_Y + 20, CX, CHIN + 90)
    layer.soft(shape, "#2c2013", 10, 0.3)
    layer.draw(shape, fill=fill, stroke=HAIR_DARK, width=4)

    # Thin connector alongside each mouth corner so the moustache and the
    # chin beard read as one continuous goatee rather than two floating
    # shapes — a real goatee frames the mouth, it doesn't skip it.
    for sign in (-1, 1):
        connector = (
            f"M {fmt(CX + sign * 90)},{fmt(MOUTH_Y - 22)} "
            f"C {fmt(CX + sign * 100)},{fmt(MOUTH_Y - 2)} {fmt(CX + sign * 76)},{fmt(MOUTH_Y + 20)} "
            f"{fmt(CX + sign * 58)},{fmt(MOUTH_Y + 30)} "
            f"C {fmt(CX + sign * 70)},{fmt(MOUTH_Y + 6)} {fmt(CX + sign * 78)},{fmt(MOUTH_Y - 10)} "
            f"{fmt(CX + sign * 90)},{fmt(MOUTH_Y - 22)} Z"
        )
        layer.draw(connector, fill=fill, stroke=HAIR_DARK, width=3, opacity=0.95)

    for i in range(5):
        t = (i - 2) / 2
        x = CX + t * 34
        layer.draw(
            f"M {fmt(x)},{fmt(MOUTH_Y + 40)} L {fmt(x + t * 6)},{fmt(CHIN + 70)}",
            stroke=HAIR_DARK, width=3, opacity=0.4,
        )
    return layer


def hair_back() -> Layer:
    layer = Layer("hair_back")
    shape = (
        f"M {fmt(CX - HALF_W * 1.05)},{fmt(TOP + H * 0.55)} "
        f"C {fmt(CX - HALF_W * 1.1)},{fmt(TOP - 20)} {fmt(CX - HALF_W * 0.4)},{fmt(TOP - 70)} "
        f"{fmt(CX)},{fmt(TOP - 74)} "
        f"C {fmt(CX + HALF_W * 0.4)},{fmt(TOP - 70)} {fmt(CX + HALF_W * 1.1)},{fmt(TOP - 20)} "
        f"{fmt(CX + HALF_W * 1.05)},{fmt(TOP + H * 0.55)} "
        f"C {fmt(CX + HALF_W * 0.9)},{fmt(TOP + H * 0.2)} {fmt(CX + HALF_W * 0.5)},{fmt(TOP - 10)} "
        f"{fmt(CX)},{fmt(TOP - 6)} "
        f"C {fmt(CX - HALF_W * 0.5)},{fmt(TOP - 10)} {fmt(CX - HALF_W * 0.9)},{fmt(TOP + H * 0.2)} "
        f"{fmt(CX - HALF_W * 1.05)},{fmt(TOP + H * 0.55)} Z"
    )
    fill = layer.linear([(0.0, HAIR_LIGHT), (0.5, HAIR), (1.0, HAIR_DARK)],
                        CX - HALF_W, TOP - 70, CX + HALF_W * 0.4, TOP + H * 0.5)
    layer.draw(shape, fill=fill, stroke=HAIR_DARK, width=5)
    return layer


def hair_front() -> Layer:
    """Sway layer: the swept-back top hair - it has its own volume/strands so
    a light wind-sway reads as hair, not a rigid cap. The hairline sits close
    to the brow with only a shallow side part, not a deep widow's peak - the
    latter reads as a receding hairline at this face scale."""
    layer = Layer("hair_front")
    shape = (
        f"M {fmt(CX - HALF_W * 0.95)},{fmt(TOP + H * 0.40)} "
        f"C {fmt(CX - HALF_W * 0.92)},{fmt(TOP - 30)} {fmt(CX - HALF_W * 0.32)},{fmt(TOP - 68)} "
        f"{fmt(CX)},{fmt(TOP - 64)} "
        f"C {fmt(CX + HALF_W * 0.32)},{fmt(TOP - 68)} {fmt(CX + HALF_W * 0.92)},{fmt(TOP - 30)} "
        f"{fmt(CX + HALF_W * 0.95)},{fmt(TOP + H * 0.40)} "
        f"C {fmt(CX + HALF_W * 0.62)},{fmt(TOP + H * 0.27)} {fmt(CX + HALF_W * 0.16)},{fmt(TOP + H * 0.22)} "
        f"{fmt(CX + HALF_W * 0.05)},{fmt(TOP + H * 0.30)} "
        f"C {fmt(CX - HALF_W * 0.10)},{fmt(TOP + H * 0.23)} {fmt(CX - HALF_W * 0.52)},{fmt(TOP + H * 0.26)} "
        f"{fmt(CX - HALF_W * 0.95)},{fmt(TOP + H * 0.40)} Z"
    )
    fill = layer.linear([(0.0, HAIR_LIGHT), (0.5, HAIR), (1.0, HAIR_DARK)],
                        CX - HALF_W * 0.7, TOP - 66, CX + HALF_W * 0.5, TOP + H * 0.40)
    layer.draw(shape, fill=fill, stroke=HAIR_DARK, width=5)
    # A few combed strand lines for texture.
    for t in (-0.5, -0.2, 0.15, 0.5):
        x0 = CX + t * HALF_W * 0.85
        layer.draw(
            f"M {fmt(x0)},{fmt(TOP - 40)} C {fmt(x0 + 10)},{fmt(TOP + H * 0.12)} "
            f"{fmt(x0 + 4)},{fmt(TOP + H * 0.26)} {fmt(x0 - 6)},{fmt(TOP + H * 0.38)}",
            stroke=HAIR_DARK, width=3, opacity=0.4,
        )
    layer.soft(
        f"M {fmt(CX - HALF_W * 0.5)},{fmt(TOP - 56)} "
        f"C {fmt(CX - HALF_W * 0.1)},{fmt(TOP - 70)} {fmt(CX + HALF_W * 0.2)},{fmt(TOP - 62)} "
        f"{fmt(CX + HALF_W * 0.4)},{fmt(TOP - 44)} "
        f"L {fmt(CX + HALF_W * 0.3)},{fmt(TOP - 20)} "
        f"L {fmt(CX - HALF_W * 0.4)},{fmt(TOP - 24)} Z",
        "#ffffff", 10, 0.3,
    )
    return layer


def body() -> Layer:
    layer = Layer("body")
    neck = (
        f"M {fmt(CX - 78)},{fmt(CHIN - 30)} L {fmt(CX - 92)},{fmt(CHIN + 100)} "
        f"L {fmt(CX + 92)},{fmt(CHIN + 100)} L {fmt(CX + 78)},{fmt(CHIN - 30)} Z"
    )
    layer.draw(neck, fill=SKIN_MID)
    layer.soft(neck, SKIN_DEEP, 14, 0.35)

    torso = (
        f"M {fmt(CX - 260)},{fmt(1280)} "
        f"C {fmt(CX - 270)},{fmt(1080)} {fmt(CX - 300)},{fmt(1000)} "
        f"{fmt(CX - 360)},{fmt(960)} "
        f"C {fmt(CX - 250)},{fmt(910)} {fmt(CX - 140)},{fmt(892)} "
        f"{fmt(CX - 90)},{fmt(CHIN + 96)} "
        f"C {fmt(CX - 40)},{fmt(CHIN + 130)} {fmt(CX + 40)},{fmt(CHIN + 130)} "
        f"{fmt(CX + 90)},{fmt(CHIN + 96)} "
        f"C {fmt(CX + 140)},{fmt(892)} {fmt(CX + 250)},{fmt(910)} "
        f"{fmt(CX + 360)},{fmt(960)} "
        f"C {fmt(CX + 300)},{fmt(1000)} {fmt(CX + 270)},{fmt(1080)} "
        f"{fmt(CX + 260)},{fmt(1280)} Z"
    )
    clip = layer.clip(torso)
    tee_fill = layer.linear([(0.0, "#3a3d45"), (1.0, TEE)], CX, 950, CX, 1280)
    layer.draw(torso, fill=tee_fill)
    layer.draw(
        f"M {fmt(CX - 60)},{fmt(1010)} C {fmt(CX - 30)},{fmt(1040)} {fmt(CX + 30)},{fmt(1040)} "
        f"{fmt(CX + 60)},{fmt(1010)}",
        stroke="#15161a", width=8, opacity=0.6, clip=clip,
    )

    # Denim jacket, open over the tee: each side covers shoulder-to-hem like
    # an actual sleeve/panel (clipped to the torso silhouette), with only a
    # moderate inward slope on the open front edge — a narrow-collar-to-wide-
    # hem wedge reads as a vest instead of a jacket.
    for sign in (-1, 1):
        lapel = (
            f"M {fmt(CX + sign * 26)},{fmt(958)} "
            f"C {fmt(CX + sign * 70)},{fmt(985)} {fmt(CX + sign * 96)},{fmt(1080)} "
            f"{fmt(CX + sign * 108)},{fmt(1280)} "
            f"L {fmt(CX + sign * 340)},{fmt(1280)} "
            f"C {fmt(CX + sign * 350)},{fmt(1140)} {fmt(CX + sign * 330)},{fmt(1000)} "
            f"{fmt(CX + sign * 260)},{fmt(950)} "
            f"C {fmt(CX + sign * 160)},{fmt(918)} {fmt(CX + sign * 80)},{fmt(920)} "
            f"{fmt(CX + sign * 26)},{fmt(958)} Z"
        )
        jacket_fill = layer.linear(
            [(0.0, DENIM_LIGHT), (0.5, DENIM), (1.0, DENIM_DARK)],
            CX + sign * 40, 940, CX + sign * 320, 1280,
        )
        layer.draw(lapel, fill=jacket_fill, stroke=DENIM_DARK, width=6, clip=clip)
        # Open-front edge seam and a chest pocket, both following the inner line.
        layer.draw(
            f"M {fmt(CX + sign * 40)},{fmt(1000)} "
            f"C {fmt(CX + sign * 80)},{fmt(1080)} {fmt(CX + sign * 100)},{fmt(1180)} "
            f"{fmt(CX + sign * 108)},{fmt(1280)}",
            stroke=DENIM_DARK, width=4, opacity=0.55, clip=clip,
        )
        layer.draw(
            f"M {fmt(CX + sign * 150)},{fmt(1110)} L {fmt(CX + sign * 230)},{fmt(1110)} "
            f"L {fmt(CX + sign * 230)},{fmt(1160)} L {fmt(CX + sign * 150)},{fmt(1160)} Z",
            fill="none", stroke=DENIM_DARK, width=4, opacity=0.6, clip=clip,
        )
        # Shoulder-seam highlight, the cheap cue that sells "fabric" over flat colour.
        layer.soft(
            f"M {fmt(CX + sign * 60)},{fmt(935)} L {fmt(CX + sign * 300)},{fmt(970)} "
            f"L {fmt(CX + sign * 280)},{fmt(1010)} L {fmt(CX + sign * 50)},{fmt(975)} Z",
            "#ffffff", 14, 0.3, clip=clip,
        )
        layer.ellipse(CX + sign * 90, 1230, 9, 9, DENIM_DARK, clip=clip)

    layer.soft(
        f"M {fmt(CX - 170)},{fmt(CHIN + 80)} "
        f"C {fmt(CX - 80)},{fmt(CHIN + 170)} {fmt(CX + 80)},{fmt(CHIN + 170)} "
        f"{fmt(CX + 170)},{fmt(CHIN + 80)} "
        f"L {fmt(CX + 170)},{fmt(CHIN - 10)} L {fmt(CX - 170)},{fmt(CHIN - 10)} Z",
        "#15161a", 22, 0.4, clip=clip,
    )
    return layer


def back() -> Layer:
    layer = Layer("back")
    shape = (
        f"M {fmt(CX - 440)},{fmt(1280)} "
        f"C {fmt(CX - 440)},{fmt(1030)} {fmt(CX - 310)},{fmt(920)} "
        f"{fmt(CX)},{fmt(906)} "
        f"C {fmt(CX + 310)},{fmt(920)} {fmt(CX + 440)},{fmt(1030)} "
        f"{fmt(CX + 440)},{fmt(1280)} Z"
    )
    fill = layer.linear([(0.0, DENIM_DARK), (1.0, "#242f3d")], CX, 900, CX, 1280)
    layer.draw(shape, fill=fill, opacity=0.9)
    return layer


LAYERS = {
    "01Back.png": back,
    "17HairBack.png": hair_back,
    "02Body.png": body,
    "03Ear_Right.png": lambda: ear(1),
    "12Ear_Left.png": lambda: ear(-1),
    "05Head.png": head,
    "08Brows.png": brows,
    "06Eyes_Open.png": lambda: eyes(False),
    "07Eyes_Closed.png": lambda: eyes(True),
    "19EyeShine.png": eye_shine,
    "09Mouth_Open.png": lambda: mouth(True),
    "10Mouth_Closed.png": lambda: mouth(False),
    "13Goatee.png": goatee,
    "18HairFront.png": hair_front,
}

MANIFEST = {
    "name": "Coder",
    "base_layers": [
        "01Back.png", "17HairBack.png", "02Body.png", "03Ear_Right.png", "12Ear_Left.png",
        "05Head.png", "08Brows.png", "19EyeShine.png", "13Goatee.png", "18HairFront.png",
    ],
    "states": {
        # Eyes render between Brows and EyeShine, so the occasional glint sits
        # on top of the iris instead of underneath it; Mouth renders right
        # after EyeShine and before Goatee, so the beard covers its lower edge.
        "eyes": {"order": 7, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
        "mouth": {"order": 8, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"},
    },
    "sway_layers": [
        {"file": "18HairFront.png", "degrees": 5, "period": 2.8, "pivot": "bottom"},
        {"file": "13Goatee.png", "degrees": 4, "period": 2.3, "pivot": "top"},
    ],
    "bounce_react_layers": ["03Ear_Right.png", "12Ear_Left.png"],
    "effect_layers": [
        {"file": "19EyeShine.png", "effect": "sparkle", "period": 5.5, "duty": 0.06, "max_opacity": 0.9},
    ],
}
