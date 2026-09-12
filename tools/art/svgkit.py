"""SVG authoring and rasterization toolkit for the bundled avatar models.

The avatars are drawn as SVG and rasterized by headless Chromium (Edge), which
implements the full SVG filter set: multi-stop gradients, gaussian blur,
turbulence, masks and clip paths. That is the difference between painted
looking art and flat clip art, and none of it is reachable through the QPainter
primitives this generator used before.

Every layer of a model is an independent SVG drawn on the same 1280x1280
canvas, so the rendered PNGs stack pixel-for-pixel into one character. See
rendering/model.py for the manifest that orders them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CANVAS = 1280

# Shared head geometry, so the three generated characters line up with each
# other (and roughly with the hand-drawn Ariral) when they share the stage.
HEAD_CX = 640.0
HEAD_TOP = 250.0
HEAD_CHIN = 812.0
EYE_Y = 596.0
MOUTH_Y = 726.0
SHOULDER_Y = 940.0


def _stop_markup(stops) -> str:
    out = []
    for stop in stops:
        offset, color = stop[0], stop[1]
        opacity = stop[2] if len(stop) > 2 else 1.0
        out.append(f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{opacity}"/>')
    return "".join(out)


def fmt(value: float) -> str:
    """Trims float noise out of path data, so a dumped SVG stays readable."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


class Layer:
    """One PNG worth of SVG: a defs section plus a draw list."""

    def __init__(self, name: str):
        self.name = name
        self._defs: list[str] = []
        self._body: list[str] = []
        self._seq = 0

    # --- defs -------------------------------------------------------------
    def _uid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq}"

    def linear(self, stops, x1: float, y1: float, x2: float, y2: float) -> str:
        uid = self._uid("lg")
        self._defs.append(
            f'<linearGradient id="{uid}" gradientUnits="userSpaceOnUse" '
            f'x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}">'
            f"{_stop_markup(stops)}</linearGradient>"
        )
        return f"url(#{uid})"

    def radial(self, stops, cx: float, cy: float, r: float,
               fx: float | None = None, fy: float | None = None) -> str:
        uid = self._uid("rg")
        focus = ""
        if fx is not None:
            focus = f' fx="{fmt(fx)}" fy="{fmt(fy if fy is not None else cy)}"'
        self._defs.append(
            f'<radialGradient id="{uid}" gradientUnits="userSpaceOnUse" '
            f'cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"{focus}>'
            f"{_stop_markup(stops)}</radialGradient>"
        )
        return f"url(#{uid})"

    def blur(self, std: float) -> str:
        uid = self._uid("bl")
        self._defs.append(
            f'<filter id="{uid}" x="-45%" y="-45%" width="190%" height="190%">'
            f'<feGaussianBlur stdDeviation="{fmt(std)}"/></filter>'
        )
        return f"url(#{uid})"

    def grain(self, frequency: float = 0.9, octaves: int = 4, strength: float = 0.5) -> str:
        """Fine skin/fabric grain. The turbulence is composited into the shape
        it is painted on, so it never leaks past the silhouette."""
        uid = self._uid("gr")
        self._defs.append(
            f'<filter id="{uid}" x="0%" y="0%" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{frequency}" '
            f'numOctaves="{octaves}" result="n"/>'
            f'<feColorMatrix in="n" type="matrix" values="'
            f'0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 {strength} 0" result="m"/>'
            f'<feComposite in="m" in2="SourceGraphic" operator="in"/></filter>'
        )
        return f"url(#{uid})"

    def clip(self, d: str) -> str:
        uid = self._uid("cp")
        self._defs.append(f'<clipPath id="{uid}"><path d="{d}"/></clipPath>')
        return uid

    def define(self, markup: str) -> None:
        self._defs.append(markup)

    # --- drawing ----------------------------------------------------------
    def draw(self, d: str, fill: str = "none", stroke: str | None = None,
             width: float = 0.0, opacity: float = 1.0, blur: str | None = None,
             clip: str | None = None, extra: str = "") -> None:
        parts = [f'<path d="{d}" fill="{fill}"']
        if stroke:
            parts.append(
                f' stroke="{stroke}" stroke-width="{fmt(width)}"'
                ' stroke-linecap="round" stroke-linejoin="round"'
            )
        if opacity != 1.0:
            parts.append(f' opacity="{opacity}"')
        if blur:
            parts.append(f' filter="{blur}"')
        if clip:
            parts.append(f' clip-path="url(#{clip})"')
        if extra:
            parts.append(" " + extra)
        parts.append("/>")
        self._body.append("".join(parts))

    def soft(self, d: str, color: str, std: float, opacity: float,
             clip: str | None = None) -> None:
        """A blurred filled shape: contact shadows, ambient occlusion, glows."""
        self.draw(d, fill=color, opacity=opacity, blur=self.blur(std), clip=clip)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, fill: str,
                opacity: float = 1.0, rotate: float = 0.0, blur: str | None = None,
                clip: str | None = None) -> None:
        attrs = f'cx="{fmt(cx)}" cy="{fmt(cy)}" rx="{fmt(rx)}" ry="{fmt(ry)}" fill="{fill}"'
        if opacity != 1.0:
            attrs += f' opacity="{opacity}"'
        if rotate:
            attrs += f' transform="rotate({fmt(rotate)} {fmt(cx)} {fmt(cy)})"'
        if blur:
            attrs += f' filter="{blur}"'
        if clip:
            attrs += f' clip-path="url(#{clip})"'
        self._body.append(f"<ellipse {attrs}/>")

    def group(self, markup: str, transform: str = "", opacity: float = 1.0,
              clip: str | None = None, blur: str | None = None) -> None:
        attrs = ""
        if transform:
            attrs += f' transform="{transform}"'
        if opacity != 1.0:
            attrs += f' opacity="{opacity}"'
        if clip:
            attrs += f' clip-path="url(#{clip})"'
        if blur:
            attrs += f' filter="{blur}"'
        self._body.append(f"<g{attrs}>{markup}</g>")

    def raw(self, markup: str) -> None:
        self._body.append(markup)

    def sub(self) -> "Layer":
        """A child builder that shares this layer defs, used to compose a group
        markup before wrapping it in a transform."""
        child = Layer(self.name)
        child._defs = self._defs  # shared list: child defs land in ours directly
        child._seq = self._seq
        return child

    def take(self, child: "Layer") -> str:
        self._seq = child._seq
        return "".join(child._body)

    # --- output -----------------------------------------------------------
    def svg(self, size: int = CANVAS) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {CANVAS} {CANVAS}">'
            f"<defs>{''.join(self._defs)}</defs>{''.join(self._body)}</svg>"
        )


# --- geometry ------------------------------------------------------------

def head_path(cx: float = HEAD_CX, top: float = HEAD_TOP, chin: float = HEAD_CHIN,
              half_w: float = 258.0, temple: float = 0.97, cheek: float = 1.0,
              jaw: float = 0.62, chin_round: float = 0.20) -> str:
    """A skull built from cubics rather than an ellipse: wide cranium,
    cheekbones at ~60% height, jaw tapering into the chin. The knobs let each
    character keep the same construction with its own proportions - the orc
    gets a heavy jaw, the coder a narrower, squarer one."""
    h = chin - top
    r = half_w
    return (
        f"M {fmt(cx)},{fmt(top)} "
        f"C {fmt(cx + r * 0.60)},{fmt(top)} {fmt(cx + r * temple)},{fmt(top + h * 0.16)} "
        f"{fmt(cx + r * temple)},{fmt(top + h * 0.40)} "
        f"C {fmt(cx + r * cheek)},{fmt(top + h * 0.56)} "
        f"{fmt(cx + r * cheek * 0.94)},{fmt(top + h * 0.70)} "
        f"{fmt(cx + r * jaw)},{fmt(top + h * 0.83)} "
        f"C {fmt(cx + r * jaw * 0.70)},{fmt(chin - h * 0.045)} "
        f"{fmt(cx + r * chin_round)},{fmt(chin)} {fmt(cx)},{fmt(chin)} "
        f"C {fmt(cx - r * chin_round)},{fmt(chin)} "
        f"{fmt(cx - r * jaw * 0.70)},{fmt(chin - h * 0.045)} "
        f"{fmt(cx - r * jaw)},{fmt(top + h * 0.83)} "
        f"C {fmt(cx - r * cheek * 0.94)},{fmt(top + h * 0.70)} "
        f"{fmt(cx - r * cheek)},{fmt(top + h * 0.56)} "
        f"{fmt(cx - r * temple)},{fmt(top + h * 0.40)} "
        f"C {fmt(cx - r * temple)},{fmt(top + h * 0.16)} "
        f"{fmt(cx - r * 0.60)},{fmt(top)} {fmt(cx)},{fmt(top)} Z"
    )


def mirror(cx: float) -> str:
    """Transform that mirrors a group about a vertical axis - every face part is
    authored once for one side and reused for the other."""
    return f"translate({fmt(2 * cx)},0) scale(-1,1)"


# --- rasterization -------------------------------------------------------

_BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_browser() -> str:
    env = os.environ.get("VOCARI_SVG_BROWSER")
    if env and Path(env).exists():
        return env
    for candidate in _BROWSERS:
        if Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "No Chromium-based browser found to rasterize the SVG art. "
        "Set VOCARI_SVG_BROWSER to msedge.exe or chrome.exe."
    )


@dataclass
class Renderer:
    """Rasterizes SVG through headless Chromium.

    Rendering happens at `supersample` times the target size and is scaled back
    down, which cleans up hair strands and other sub-pixel detail that even
    Chromium analytic antialiasing leaves slightly ragged.
    """

    size: int = CANVAS
    supersample: int = 2
    browser: str = field(default_factory=find_browser)
    _workdir: Path | None = None

    def __post_init__(self) -> None:
        self._workdir = Path(tempfile.mkdtemp(prefix="vocari-svg-"))

    def render(self, layer: Layer, out_path: Path) -> Path:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage

        assert self._workdir is not None
        big = self.size * self.supersample
        html = (
            "<!doctype html><html><body style='margin:0;background:transparent;"
            "overflow:hidden'>" + layer.svg(big) + "</body></html>"
        )
        page = self._workdir / f"{out_path.stem}.html"
        page.write_text(html, encoding="utf-8")
        shot = self._workdir / f"{out_path.stem}.png"
        subprocess.run(
            [
                self.browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--force-color-profile=srgb",
                "--default-background-color=00000000",
                f"--window-size={big},{big}",
                f"--user-data-dir={self._workdir / 'profile'}",
                f"--screenshot={shot}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        image = QImage(str(shot))
        if image.isNull():
            raise RuntimeError(f"headless render produced no image for {out_path.name}")
        if image.width() != self.size:
            image = image.scaled(
                self.size, self.size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(out_path))
        return out_path

    def cleanup(self) -> None:
        if self._workdir and self._workdir.exists():
            shutil.rmtree(self._workdir, ignore_errors=True)
