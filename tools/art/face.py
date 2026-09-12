"""Shared facial features for the generated avatars.

The three bundled characters are deliberately built from the same construction
(same eye anatomy, same lid/lash logic, same mouth interior) with different
proportions and palettes, so they read as one cast rather than three unrelated
doodles. Everything here is authored once for the left eye/corner and mirrored
by the caller, which keeps the faces symmetrical for free.
"""
from __future__ import annotations

from dataclasses import dataclass

from tools.art.svgkit import Layer, fmt


@dataclass
class EyeSpec:
    """One eye, authored with its outer corner on the left and inner corner on
    the right (i.e. the viewer-left eye of a forward-facing head)."""

    cx: float
    cy: float
    w: float  # full width of the opening
    h: float  # full height of the opening
    iris_light: str = "#8fd7ff"
    iris_dark: str = "#1d5f92"
    iris_rim: str = "#0d2a45"
    pupil: str = "#120f1a"
    sclera_light: str = "#ffffff"
    sclera_shade: str = "#d8dfeb"
    lash: str = "#241a26"
    lash_width: float = 17.0
    lid_lift: float = 0.10  # how much the outer corner rides above the inner one
    iris_scale: float = 0.96  # iris diameter relative to the opening height
    look_x: float = 0.0  # iris offset, for a slightly off-axis gaze
    look_y: float = 0.0
    highlight: float = 1.0  # catchlight strength
    glow: str | None = None  # optional coloured bloom around the iris


def _opening(spec: EyeSpec) -> str:
    """The eyelid opening: a lens with a high, late-peaking upper lid (the
    single strongest cue that reads as anime rather than cartoon)."""
    cx, cy = spec.cx, spec.cy
    hw, hh = spec.w / 2, spec.h / 2
    lift = hh * spec.lid_lift
    return (
        f"M {fmt(cx - hw)},{fmt(cy - lift)} "
        f"C {fmt(cx - hw * 0.86)},{fmt(cy - hh * 0.80)} "
        f"{fmt(cx - hw * 0.36)},{fmt(cy - hh * 1.04)} "
        f"{fmt(cx + hw * 0.12)},{fmt(cy - hh * 0.86)} "
        f"C {fmt(cx + hw * 0.56)},{fmt(cy - hh * 0.68)} "
        f"{fmt(cx + hw * 0.90)},{fmt(cy - hh * 0.18)} "
        f"{fmt(cx + hw)},{fmt(cy + hh * 0.20)} "
        f"C {fmt(cx + hw * 0.72)},{fmt(cy + hh * 0.66)} "
        f"{fmt(cx + hw * 0.06)},{fmt(cy + hh * 0.96)} "
        f"{fmt(cx - hw * 0.52)},{fmt(cy + hh * 0.64)} "
        f"C {fmt(cx - hw * 0.80)},{fmt(cy + hh * 0.44)} "
        f"{fmt(cx - hw)},{fmt(cy + hh * 0.18)} "
        f"{fmt(cx - hw)},{fmt(cy - lift)} Z"
    )


def _upper_lid(spec: EyeSpec) -> str:
    """Just the upper lid stroke, reused for the lash line."""
    cx, cy = spec.cx, spec.cy
    hw, hh = spec.w / 2, spec.h / 2
    lift = hh * spec.lid_lift
    return (
        f"M {fmt(cx - hw)},{fmt(cy - lift)} "
        f"C {fmt(cx - hw * 0.86)},{fmt(cy - hh * 0.80)} "
        f"{fmt(cx - hw * 0.36)},{fmt(cy - hh * 1.04)} "
        f"{fmt(cx + hw * 0.12)},{fmt(cy - hh * 0.86)} "
        f"C {fmt(cx + hw * 0.56)},{fmt(cy - hh * 0.68)} "
        f"{fmt(cx + hw * 0.90)},{fmt(cy - hh * 0.18)} "
        f"{fmt(cx + hw)},{fmt(cy + hh * 0.20)}"
    )


def eye_open(layer: Layer, spec: EyeSpec) -> str:
    """Returns the markup for one open eye (not appended - the caller places it,
    usually once directly and once through a mirror transform)."""
    g = layer.sub()
    cx, cy = spec.cx, spec.cy
    hw, hh = spec.w / 2, spec.h / 2
    opening = _opening(spec)
    clip = g.clip(opening)

    # Sclera: never pure white across the whole eye - it picks up shadow from
    # the lid above and light from below.
    sclera = g.linear(
        [(0.0, spec.sclera_shade), (0.45, spec.sclera_light), (1.0, spec.sclera_light)],
        cx, cy - hh, cx, cy + hh,
    )
    g.draw(opening, fill=sclera)

    icx = cx + spec.look_x
    icy = cy - hh * 0.04 + spec.look_y
    ir = hh * spec.iris_scale

    if spec.glow:
        g.ellipse(icx, icy, ir * 1.5, ir * 1.5, spec.glow, opacity=0.55,
                  blur=g.blur(ir * 0.45), clip=clip)

    # Iris: lit from below (light bounces off the cheek into the eye), rimmed
    # dark at the top where the lid shadows it.
    iris = g.radial(
        [(0.0, spec.iris_light), (0.55, spec.iris_dark), (1.0, spec.iris_rim)],
        icx, icy + ir * 0.35, ir * 1.25,
    )
    g.ellipse(icx, icy, ir, ir, iris, clip=clip)
    # Bright pool at the bottom of the iris.
    g.ellipse(icx, icy + ir * 0.42, ir * 0.72, ir * 0.44, spec.iris_light,
              opacity=0.75, blur=g.blur(ir * 0.12), clip=clip)
    # Radial fibres - a few thin spokes keep the iris from looking like a decal.
    spokes = []
    for i in range(12):
        angle = i * 30
        spokes.append(
            f'<line x1="{fmt(icx)}" y1="{fmt(icy)}" '
            f'x2="{fmt(icx)}" y2="{fmt(icy - ir * 0.86)}" '
            f'transform="rotate({angle} {fmt(icx)} {fmt(icy)})"/>'
        )
    g.raw(
        f'<g stroke="{spec.iris_rim}" stroke-width="{fmt(ir * 0.075)}" opacity="0.28" '
        f'clip-path="url(#{clip})">{"".join(spokes)}</g>'
    )
    g.ellipse(icx, icy, ir, ir, "none", clip=clip)
    g.raw(
        f'<ellipse cx="{fmt(icx)}" cy="{fmt(icy)}" rx="{fmt(ir)}" ry="{fmt(ir)}" '
        f'fill="none" stroke="{spec.iris_rim}" stroke-width="{fmt(ir * 0.16)}" '
        f'opacity="0.85" clip-path="url(#{clip})"/>'
    )
    g.ellipse(icx, icy, ir * 0.44, ir * 0.5, spec.pupil, clip=clip)

    # Catchlights: one large soft one facing the key light, one small sparkle
    # opposite it. Cheap, and it is what makes eyes look wet.
    if spec.highlight > 0:
        g.ellipse(icx - ir * 0.34, icy - ir * 0.40, ir * 0.32, ir * 0.26, "#ffffff",
                  opacity=0.95 * spec.highlight, rotate=-20, clip=clip)
        g.ellipse(icx + ir * 0.36, icy + ir * 0.34, ir * 0.15, ir * 0.13, "#ffffff",
                  opacity=0.70 * spec.highlight, clip=clip)
        g.ellipse(icx - ir * 0.10, icy + ir * 0.62, ir * 0.40, ir * 0.14, "#ffffff",
                  opacity=0.30 * spec.highlight, blur=g.blur(ir * 0.10), clip=clip)

    # Shadow cast by the upper lid onto the eyeball.
    g.draw(
        f"M {fmt(cx - hw)},{fmt(cy - hh * 1.3)} L {fmt(cx + hw)},{fmt(cy - hh * 1.3)} "
        f"L {fmt(cx + hw)},{fmt(cy - hh * 0.05)} "
        f"C {fmt(cx + hw * 0.4)},{fmt(cy - hh * 0.34)} "
        f"{fmt(cx - hw * 0.4)},{fmt(cy - hh * 0.34)} "
        f"{fmt(cx - hw)},{fmt(cy - hh * 0.02)} Z",
        fill="#101018", opacity=0.26, blur=g.blur(hh * 0.10), clip=clip,
    )

    # Lash line: a heavy upper lid stroke plus a flick past the outer corner.
    lid = _upper_lid(spec)
    g.draw(lid, stroke=spec.lash, width=spec.lash_width, fill="none")
    g.draw(
        f"M {fmt(cx - hw * 1.02)},{fmt(cy - hh * spec.lid_lift - spec.lash_width * 0.2)} "
        f"C {fmt(cx - hw * 1.16)},{fmt(cy - hh * 0.52)} "
        f"{fmt(cx - hw * 1.18)},{fmt(cy - hh * 0.86)} "
        f"{fmt(cx - hw * 1.30)},{fmt(cy - hh * 1.15)} "
        f"C {fmt(cx - hw * 1.02)},{fmt(cy - hh * 0.98)} "
        f"{fmt(cx - hw * 0.90)},{fmt(cy - hh * 0.62)} "
        f"{fmt(cx - hw * 0.84)},{fmt(cy - hh * 0.30)} Z",
        fill=spec.lash,
    )
    # Lower lid: thinner and warmer, it should never match the lash weight.
    g.draw(
        f"M {fmt(cx - hw * 0.62)},{fmt(cy + hh * 0.70)} "
        f"C {fmt(cx - hw * 0.1)},{fmt(cy + hh * 1.02)} "
        f"{fmt(cx + hw * 0.62)},{fmt(cy + hh * 0.74)} "
        f"{fmt(cx + hw * 0.98)},{fmt(cy + hh * 0.26)}",
        stroke=spec.lash, width=spec.lash_width * 0.38, fill="none", opacity=0.75,
    )
    return layer.take(g)


def eye_closed(layer: Layer, spec: EyeSpec) -> str:
    """The blink frame: lids meeting in a relaxed downward arc, with the same
    lash flick as the open eye so the corner does not jump between frames."""
    g = layer.sub()
    cx, cy = spec.cx, spec.cy
    hw, hh = spec.w / 2, spec.h / 2
    lid_y = cy + hh * 0.18
    arc = (
        f"M {fmt(cx - hw)},{fmt(lid_y - hh * 0.34)} "
        f"C {fmt(cx - hw * 0.55)},{fmt(lid_y + hh * 0.30)} "
        f"{fmt(cx + hw * 0.35)},{fmt(lid_y + hh * 0.34)} "
        f"{fmt(cx + hw)},{fmt(lid_y - hh * 0.16)}"
    )
    g.draw(arc, stroke=spec.lash, width=spec.lash_width * 1.05, fill="none")
    g.draw(
        f"M {fmt(cx - hw * 1.02)},{fmt(lid_y - hh * 0.40)} "
        f"C {fmt(cx - hw * 1.16)},{fmt(cy - hh * 0.52)} "
        f"{fmt(cx - hw * 1.18)},{fmt(cy - hh * 0.86)} "
        f"{fmt(cx - hw * 1.30)},{fmt(cy - hh * 1.15)} "
        f"C {fmt(cx - hw * 1.02)},{fmt(cy - hh * 0.98)} "
        f"{fmt(cx - hw * 0.90)},{fmt(cy - hh * 0.62)} "
        f"{fmt(cx - hw * 0.84)},{fmt(cy - hh * 0.30)} Z",
        fill=spec.lash,
    )
    # A hint of the lash fringe below the closed lid.
    for t in (0.25, 0.5, 0.75):
        x = cx - hw + spec.w * t
        y = lid_y + hh * (0.30 - abs(t - 0.5) * 0.45)
        g.draw(
            f"M {fmt(x)},{fmt(y)} L {fmt(x - hw * 0.06)},{fmt(y + hh * 0.30)}",
            stroke=spec.lash, width=spec.lash_width * 0.34, fill="none", opacity=0.8,
        )
    return layer.take(g)


def brow(layer: Layer, cx: float, cy: float, w: float, color: str,
         thickness: float = 26.0, angle: float = 0.0, arch: float = 0.55,
         taper: float = 0.35) -> str:
    """A brow drawn as a closed tapered shape rather than a stroke: thick at the
    inner end, thin at the outer tip. `angle` tilts the inner end down for an
    angry look (orc) or up for a worried one."""
    g = layer.sub()
    hw = w / 2
    inner_y = cy + angle
    outer_y = cy - angle * 0.35
    top = (
        f"M {fmt(cx + hw)},{fmt(inner_y - thickness * 0.5)} "
        f"C {fmt(cx + hw * 0.35)},{fmt(inner_y - thickness * 0.5 - w * arch * 0.12)} "
        f"{fmt(cx - hw * 0.35)},{fmt(outer_y - thickness * 0.5 - w * arch * 0.10)} "
        f"{fmt(cx - hw)},{fmt(outer_y + thickness * taper * 0.2)} "
        f"C {fmt(cx - hw * 0.35)},{fmt(outer_y + thickness * (0.5 - arch * 0.10))} "
        f"{fmt(cx + hw * 0.35)},{fmt(inner_y + thickness * 0.55)} "
        f"{fmt(cx + hw)},{fmt(inner_y + thickness * 0.5)} Z"
    )
    g.draw(top, fill=color)
    return layer.take(g)


def skin(layer: Layer, d: str, *, base: str, light: str, shadow: str, deep: str,
         cx: float, top: float, chin: float, half_w: float,
         rim: str = "#ffffff", rim_opacity: float = 0.45) -> str:
    """Paints a head (or any large skin shape) with the lighting every one of
    these characters shares: a key light from the upper left, ambient occlusion
    under the jaw and at the temples, and a rim light down the right edge.
    Returns the clip id so the caller can keep adding shading inside the
    silhouette without it spilling over the outline."""
    clip = layer.clip(d)
    h = chin - top
    fill = layer.radial(
        [(0.0, light), (0.55, base), (1.0, shadow)],
        cx - half_w * 0.35, top + h * 0.28, half_w * 1.75,
    )
    layer.draw(d, fill=fill)
    # Jaw / neck occlusion.
    layer.soft(
        f"M {fmt(cx - half_w)},{fmt(chin - h * 0.30)} "
        f"C {fmt(cx - half_w * 0.5)},{fmt(chin + h * 0.20)} "
        f"{fmt(cx + half_w * 0.5)},{fmt(chin + h * 0.20)} "
        f"{fmt(cx + half_w)},{fmt(chin - h * 0.30)} "
        f"L {fmt(cx + half_w)},{fmt(chin + h * 0.3)} "
        f"L {fmt(cx - half_w)},{fmt(chin + h * 0.3)} Z",
        deep, h * 0.055, 0.38, clip=clip,
    )
    # Temples, which on a rounded skull turn away from the light on both sides.
    for sign in (-1, 1):
        layer.soft(
            f"M {fmt(cx + sign * half_w * 1.2)},{fmt(top)} "
            f"C {fmt(cx + sign * half_w * 0.72)},{fmt(top + h * 0.30)} "
            f"{fmt(cx + sign * half_w * 0.74)},{fmt(top + h * 0.62)} "
            f"{fmt(cx + sign * half_w * 1.05)},{fmt(top + h * 0.92)} "
            f"L {fmt(cx + sign * half_w * 1.4)},{fmt(top + h)} "
            f"L {fmt(cx + sign * half_w * 1.4)},{fmt(top)} Z",
            shadow, h * 0.05, 0.30 if sign < 0 else 0.42, clip=clip,
        )
    # Rim light: the single cheapest thing that lifts a flat fill off the
    # background, which matters here because the overlay has no background.
    layer.soft(
        f"M {fmt(cx + half_w * 0.72)},{fmt(top + h * 0.10)} "
        f"C {fmt(cx + half_w * 1.06)},{fmt(top + h * 0.36)} "
        f"{fmt(cx + half_w * 1.02)},{fmt(top + h * 0.70)} "
        f"{fmt(cx + half_w * 0.52)},{fmt(chin)} "
        f"L {fmt(cx + half_w * 1.4)},{fmt(chin)} "
        f"L {fmt(cx + half_w * 1.4)},{fmt(top)} Z",
        rim, h * 0.035, rim_opacity, clip=clip,
    )
    return clip


def grain_over(layer: Layer, d: str, opacity: float = 0.25,
               frequency: float = 1.3, strength: float = 0.55) -> None:
    """Sprinkles fine noise over a shape - skin pores, fabric weave. Subtle on
    purpose: it should only break up flat fills, never be visible as texture."""
    layer.draw(d, fill="#ffffff", opacity=opacity, blur=layer.grain(frequency, 4, strength))
