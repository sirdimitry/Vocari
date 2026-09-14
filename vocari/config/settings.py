"""Application configuration: persisted JSON settings for the overlay, TTS and Twitch modules.

Stage 1 only needs OverlayConfig; other sections are added in later stages.

config.json is encrypted at rest (Windows DPAPI — see load()/save() and
vocari/config/dpapi.py), not plain JSON on disk.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
import json

from vocari.config import dpapi
from vocari.paths import app_root

PROJECT_ROOT = app_root()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


def _merge_section(section_cls, saved: dict):
    """Builds a config section from its defaults overlaid with whatever was
    saved, dropping any saved key that isn't a field on the dataclass anymore
    — otherwise loading an older config.json after a field is renamed/removed
    (e.g. render.use_gpu) would crash with an unexpected-keyword TypeError
    instead of just ignoring the stale key."""
    known = {f.name for f in fields(section_cls)}
    merged = {**asdict(section_cls()), **{k: v for k, v in saved.items() if k in known}}
    return section_cls(**merged)


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
    # Pick a random bundled model per message instead of always using
    # model_path. Different avatars can then share the stage at once.
    random_model: bool = False
    # Which model names are eligible when random_model is on — a model with
    # an unchecked box in Settings → Модель never gets picked. Empty means
    # "everyone eligible" (the default, and also what an unchecked-everyone
    # state falls back to, since a pool nobody can be drawn from isn't a
    # useful configuration).
    random_pool: list[str] = field(default_factory=list)
    # Relative weight per model name when random_model picks among the pool
    # above — a model missing here defaults to 1.0 (see
    # overlay_window.py's _pick_model_name), so importing a new model needs
    # no bookkeeping here until the user actually wants to tune its odds.
    model_weights: dict[str, float] = field(default_factory=dict)
    # Chat nickname (lowercased) -> model name: that person's messages
    # always use this avatar instead of random_model's pick, regardless of
    # whether random_model is even on. Settings → Ники.
    user_model_bindings: dict[str, str] = field(default_factory=dict)
    # Nicknames the app has actually seen say a !tts command, in the order
    # first seen — lets Settings → Ники offer a picker instead of requiring
    # the streamer to type a nick by hand (and risk a typo that silently
    # never matches).
    known_nicks: list[str] = field(default_factory=list)


@dataclass
class RenderConfig:
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
    # How long the avatar stands in the speaking slot before the line starts,
    # and how long it holds the pose afterwards (100..5000 ms each). The
    # pre-speech pause doubles as cover for synthesis latency: if synthesis
    # takes longer than this, playback starts as soon as the audio is ready.
    pre_speech_delay_ms: int = 500
    post_speech_hold_ms: int = 500
    # How fast the avatar slides off stage, as an absolute 1..100 dial
    # (1 = crawls off, 100 = gone in a single frame) — see stage.py.
    exit_speed: int = 33


@dataclass
class BubbleConfig:
    """The speech bubble drawn above/next to the speaking avatar: the message
    itself plus who sent it. Sizes here are in the model's canvas pixels (the
    same space the avatar art lives in), so the bubble scales with the avatar
    instead of needing to be re-tuned every time the overlay scale changes."""
    enabled: bool = True
    # cloud | rounded | ellipse | glass | banner | custom — see rendering/bubble.py
    style: str = "cloud"
    custom_image: str = ""  # PNG used when style == "custom" (9-slice stretched)
    scale: float = 1.0  # 0.5..2.0, on top of the automatic text-driven sizing
    appear_speed: int = 90  # 1..100, how fast it pops in (same dial style as exit_speed)
    # Hard ceiling on the bubble, as a fraction of the avatar's canvas width /
    # height — the bubble grows to fit the text but never past this.
    max_width_fraction: float = 1.6
    max_height_fraction: float = 0.9
    position: str = "top-right"  # top | top-left | top-right | left | right
    offset_x: int = 0  # extra nudge in canvas px, on top of `position`
    offset_y: int = 0

    # 8-digit hex colours here are Qt's own #AARRGGBB (alpha first — see
    # QColor::NameFormat.HexArgb, what ColorButton reads/writes), not the
    # #RRGGBBAA order the name might suggest.
    background_color: str = "#f0f7f7fb"  # near-white, ~94% opaque
    border_color: str = "#2b2b33"
    # Overall backdrop transparency, 0..100 (%). Multiplies the fill/outline
    # alpha; the text itself stays fully opaque so it never becomes unreadable.
    # Default is 0 (backdrop fully invisible) on purpose: with white text and
    # a dark stroke (below), that reads clean over any stream background
    # without needing a visible bubble shape behind it at all.
    opacity: int = 0

    text_color: str = "#ffffffff"  # white — see the opacity note above
    text_font: str = "Cascadia Code"
    text_size: int = 46
    # Outline drawn behind the fill so the text stays legible over any
    # backdrop colour/image — 0 width disables it. Sizes are canvas px, same
    # space as text_size.
    text_stroke_color: str = "#a8000000"  # black, ~66% opaque
    text_stroke_width: int = 3
    text_uppercase: bool = False

    nick_color: str = "#00d0d0"
    nick_font: str = "Segoe UI Black"
    nick_size: int = 70
    nick_bold: bool = True
    nick_italic: bool = False
    nick_stroke_color: str = "#a8000000"
    nick_stroke_width: int = 3
    nick_uppercase: bool = False

    # Speaks the sender's name before the message itself — a separate
    # synthesis pass isn't needed, the phrase is just prepended to the text
    # that gets sent to TTS (see tts/tts_queue.py); the bubble's own text
    # stays just the message, since the nickname is already shown there
    # separately. "Ник" in the phrase is replaced with the actual sender
    # name; leave it out to speak a fixed phrase with no name at all.
    announce_nick: bool = True
    announce_phrase: str = "Ник навайбкодил"


@dataclass
class HotkeyConfig:
    # A QKeySequence string (e.g. "F9" or "Ctrl+Alt+S"), empty = disabled.
    # Registered as a system-wide hotkey (works even while a game/OBS has
    # focus) that cuts the currently-speaking avatar's line short and sends
    # it through the normal exit animation, as if it had just finished.
    skip_message: str = ""


@dataclass
class TTSConfig:
    provider: str = "edge"  # "edge" (cloud, free, no setup) | "silero" | "piper" (both local/offline)
    voice_ru: str = "ru-RU-SvetlanaNeural"  # edge-tts voice
    voice_en: str = "en-US-JennyNeural"  # edge-tts voice
    silero_voice_ru: str = "baya"
    silero_voice_en: str = "en_0"
    # Piper voice ids (see vocari/tts/piper_provider.py) - whatever's been
    # downloaded via Settings -> Piper; these two are just the default
    # starter voices offered there.
    piper_voice_ru: str = "ru_RU-irina-medium"
    piper_voice_en: str = "en_US-lessac-medium"
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
    bubble: BubbleConfig = field(default_factory=BubbleConfig)

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            return cls()
        try:
            raw = path.read_bytes()
        except OSError:
            return cls()

        try:
            plaintext = dpapi.unprotect(raw)
        except OSError:
            # Not DPAPI ciphertext — most likely a config.json saved before
            # encryption-at-rest was added (see save()). Read it as plain
            # JSON so upgrading doesn't silently wipe the user's settings;
            # the next save() re-writes it encrypted.
            plaintext = raw

        try:
            # utf-8-sig tolerates (and strips) a UTF-8 BOM — Notepad, and some
            # PowerShell versions, save UTF-8 files with one by default, which
            # would otherwise make json.loads() fail and silently reset to
            # defaults on the very first read.
            data = json.loads(plaintext.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return cls()
        overlay = _merge_section(OverlayConfig, data.get("overlay", {}))
        render = _merge_section(RenderConfig, data.get("render", {}))
        tts = _merge_section(TTSConfig, data.get("tts", {}))
        twitch = _merge_section(TwitchConfig, data.get("twitch", {}))
        hotkey = _merge_section(HotkeyConfig, data.get("hotkey", {}))
        bubble = _merge_section(BubbleConfig, data.get("bubble", {}))
        return cls(
            overlay=overlay, render=render, tts=tts, twitch=twitch, hotkey=hotkey, bubble=bubble
        )

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        payload = {
            "overlay": asdict(self.overlay),
            "render": asdict(self.render),
            "tts": asdict(self.tts),
            "twitch": asdict(self.twitch),
            "hotkey": asdict(self.hotkey),
            "bubble": asdict(self.bubble),
        }
        plaintext = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            # Encrypted at rest (Windows DPAPI, tied to this Windows user) so
            # config.json isn't plain, hand-editable JSON on disk — the
            # Twitch OAuth token especially has no business being readable/
            # editable in a text editor. See vocari/config/dpapi.py.
            path.write_bytes(dpapi.protect(plaintext))
        except OSError:
            # DPAPI unavailable for some reason — fail safe by still saving
            # something usable rather than losing the user's settings.
            path.write_bytes(plaintext)
