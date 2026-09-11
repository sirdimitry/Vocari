"""Application configuration: persisted JSON settings for the overlay, TTS and Twitch modules.

Stage 1 only needs OverlayConfig; other sections are added in later stages.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from vocari.paths import app_root

PROJECT_ROOT = app_root()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class OverlayConfig:
    model_path: str = "assets/models/Ariral"
    # -1 / 0.0 are "not yet set" sentinels: on first run (no saved config.json
    # yet), main.py replaces them with values computed from the user's actual
    # screen resolution and the model's native canvas size — rendering a
    # PNG's full native pixel size (often 1000+ px) at a screen-agnostic
    # scale=1.0 could dwarf the user's whole monitor. Once saved, whatever
    # the user drags/scrolls to is kept as-is on every later run.
    pos_x: int = -1
    pos_y: int = -1
    scale: float = 0.0


@dataclass
class RenderConfig:
    # Тумблер в настройках (Этап 4): рендерить аватар на GPU (OpenGL/RTX) или
    # программно на CPU. Сама GPU-ветка рендера будет реализована вместе с UI
    # настроек — пока переключатель хранится в конфиге и по умолчанию выключен.
    use_gpu: bool = False
    # Лёгкое процедурное покачивание (ахоге/причёска) и подпрыгивание тела во
    # время речи. Тумблер "Покачивание" в настройках выключает оба эффекта разом.
    enable_sway: bool = True
    # Держать окно аватара поверх всех остальных окон на экране пользователя.
    # OBS Window Capture захватывает содержимое окна напрямую по хэндлу, не по
    # области экрана, так что запись работает даже когда окно закрыто другим
    # приложением/игрой — этот тумблер только про то, что видно на самом
    # экране стримера, не про то, что попадает в OBS.
    always_on_top: bool = True
    # Which side the queue/entrance/exit corridor is on. False (default) =
    # everyone jumps in and out on the left, matching the original spec;
    # True mirrors the whole stage layout to the right instead.
    entrance_from_right: bool = False


@dataclass
class HotkeyConfig:
    # A QKeySequence string (e.g. "F9" or "Ctrl+Alt+S"), empty = disabled.
    # Registered as a system-wide hotkey (works even while a game/OBS has
    # focus) that cuts the currently-speaking avatar's line short and sends
    # it through the normal exit animation, as if it had just finished.
    skip_message: str = ""


@dataclass
class TTSConfig:
    provider: str = "edge"  # "edge" (cloud, free, no setup) | "silero" (local/offline)
    voice_ru: str = "ru-RU-SvetlanaNeural"  # edge-tts voice
    voice_en: str = "en-US-JennyNeural"  # edge-tts voice
    silero_voice_ru: str = "baya"
    silero_voice_en: str = "en_0"
    rate_percent: int = 0  # edge-tts speaking-rate offset, e.g. -10 .. +50 (Silero ignores this)
    volume_percent: int = 0  # playback volume offset, e.g. -50 .. +50 (applies to any provider)
    auto_detect_language: bool = True
    manual_lang: str = "ru"  # used instead of detection when auto_detect_language is off
    max_chars: int = 200
    random_voice: bool = False  # pick a random voice (see tts/voices.py) per utterance, for whichever provider is selected


@dataclass
class TwitchConfig:
    # Stage 4 only stores these; the bot itself connects in Stage 5.
    channel: str = ""
    oauth_token: str = ""
    command_prefix: str = "!tts"
    cooldown_seconds: int = 10
    subs_only: bool = False
    vip_only: bool = False
    mods_only: bool = False
    blacklist_words: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    twitch: TwitchConfig = field(default_factory=TwitchConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)

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
        tts = TTSConfig(**{**asdict(TTSConfig()), **data.get("tts", {})})
        twitch = TwitchConfig(**{**asdict(TwitchConfig()), **data.get("twitch", {})})
        hotkey = HotkeyConfig(**{**asdict(HotkeyConfig()), **data.get("hotkey", {})})
        return cls(overlay=overlay, render=render, tts=tts, twitch=twitch, hotkey=hotkey)

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        payload = {
            "overlay": asdict(self.overlay),
            "render": asdict(self.render),
            "tts": asdict(self.tts),
            "twitch": asdict(self.twitch),
            "hotkey": asdict(self.hotkey),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
