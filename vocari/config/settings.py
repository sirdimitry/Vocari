"""Application configuration: persisted JSON settings for the overlay, TTS and Twitch modules.

Stage 1 only needs OverlayConfig; other sections are added in later stages.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class OverlayConfig:
    model_path: str = "assets/models/Ariral"
    pos_x: int = 100
    pos_y: int = 100
    scale: float = 1.0


@dataclass
class RenderConfig:
    # Тумблер в настройках (Этап 4): рендерить аватар на GPU (OpenGL/RTX) или
    # программно на CPU. Сама GPU-ветка рендера будет реализована вместе с UI
    # настроек — пока переключатель хранится в конфиге и по умолчанию выключен.
    use_gpu: bool = False
    # Лёгкое процедурное покачивание (ахоге/причёска) и подпрыгивание тела во
    # время речи. Тумблер "Покачивание" в настройках выключает оба эффекта разом.
    enable_sway: bool = True


@dataclass
class AppConfig:
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    render: RenderConfig = field(default_factory=RenderConfig)

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            return cls()
        try:
            # utf-8-sig tolerates (and strips) a UTF-8 BOM — Notepad, and some
            # PowerShell versions, save UTF-8 files with one by default, which
            # would otherwise make json.loads() fail and silently reset to
            # defaults on the very first read.
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            return cls()
        overlay = OverlayConfig(**{**asdict(OverlayConfig()), **data.get("overlay", {})})
        render = RenderConfig(**{**asdict(RenderConfig()), **data.get("render", {})})
        return cls(overlay=overlay, render=render)

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        payload = {"overlay": asdict(self.overlay), "render": asdict(self.render)}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
