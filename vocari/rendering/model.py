"""Loading and z-ordering of avatar models from a model.json manifest.

Manifest format (model.json, lives next to the layer PNGs):

    {
      "name": "Ariral",
      "canvas": [1280, 1280],
      "base_layers": ["01HairBehind.png", "02Body.png", ...],
      "states": {
        "eyes":  {"order": 5, "open": "06Eyes_Open.png", "closed": "07Eyes_Closed.png"},
        "mouth": {"order": 6, "open": "09Mouth_Open.png", "closed": "10Mouth_Closed.png"}
      },
      "sway_layers": ["16Ahoge.png"],
      "bounce_react_layers": ["03Ear_Right.png", "12Ear_Left.png"]
    }

`base_layers` is the z-order (back to front) of every layer that never changes at
runtime. `states` describes swappable layer groups (eyes, mouth, and later any other
animated part) with an arbitrary number of named frames each; "order" says how many
entries of `base_layers` sit behind that group (so the group is spliced into the
z-order at that index). This keeps the format working for models with a different
number of layers or state groups than Ariral's, which is required since users will
import their own models with arbitrary layer sets.

`sway_layers` (optional) names static base layers that should get a subtle
idle sway animation (see rendering/overlay_window.py) — purely a procedural
transform, no extra art needed. Defaults to an empty list (no sway) when
absent, which is what auto-imported models get since we can't guess which
part is meant to sway.

`bounce_react_layers` (optional) names layers that should additionally
rotate around their own attachment point when the avatar bounces (talking,
or the idle bob) — e.g. ears: the edge nearest the head moves exactly with
it, while the outer tip lags behind and eases into the rotation, instead of
translating in rigid lockstep with everything else. Also defaults to empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class StateGroup:
    order: int
    frames: dict[str, str]  # frame name -> PNG filename, e.g. {"open": "...", "closed": "..."}


@dataclass
class AvatarModel:
    name: str
    canvas_size: tuple[int, int]
    base_layers: list[str]
    states: dict[str, StateGroup]
    directory: Path
    sway_layers: list[str] = field(default_factory=list)
    bounce_react_layers: list[str] = field(default_factory=list)

    def layer_path(self, filename: str) -> Path:
        return self.directory / filename

    def all_filenames(self) -> set[str]:
        names = set(self.base_layers)
        for group in self.states.values():
            names.update(group.frames.values())
        return names

    def build_z_order(self) -> list[tuple[str, str]]:
        """Return the full back-to-front render order.

        Each entry is ("layer", filename) for a static layer, or ("state", state_key)
        for a swappable group — the renderer resolves the latter to whichever frame
        is currently active for that state.
        """
        items: list[tuple[str, str]] = [("layer", fn) for fn in self.base_layers]
        state_entries = sorted(self.states.items(), key=lambda kv: kv[1].order)
        offset = 0
        for key, group in state_entries:
            insert_at = max(0, min(len(items), group.order + offset))
            items.insert(insert_at, ("state", key))
            offset += 1
        return items


def load_model(directory: Path) -> AvatarModel:
    directory = Path(directory)
    manifest_path = directory / "model.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    base_layers = list(data["base_layers"])
    states: dict[str, StateGroup] = {}
    for key, raw in data.get("states", {}).items():
        frames = {k: v for k, v in raw.items() if k != "order"}
        order = raw.get("order", len(base_layers))
        states[key] = StateGroup(order=order, frames=frames)

    return AvatarModel(
        name=data["name"],
        canvas_size=(int(data["canvas"][0]), int(data["canvas"][1])),
        base_layers=base_layers,
        states=states,
        directory=directory,
        sway_layers=list(data.get("sway_layers", [])),
        bounce_react_layers=list(data.get("bounce_react_layers", [])),
    )
