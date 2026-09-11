"""Pure filtering logic for turning a raw chat message into an accepted TTS
request (or a reason it was rejected). Independent of the chat source and of
Qt, so it's simple to unit-test and reusable by any future chat source."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from vocari.chat.base import ChatMessage
from vocari.config.settings import TwitchConfig


def extract_command_text(message_text: str, prefix: str) -> str | None:
    """Returns the text after `prefix`, or None if the message doesn't start
    with it (case-insensitive, per common chat-bot convention)."""
    if not prefix:
        return None
    stripped = message_text.strip()
    if not stripped.lower().startswith(prefix.lower()):
        return None
    return stripped[len(prefix) :].strip()


def has_access(message: ChatMessage, config: TwitchConfig) -> bool:
    """No access toggle enabled => everyone allowed. Otherwise any one
    matching toggle allows the message through (OR, not AND)."""
    if not (config.subs_only or config.vip_only or config.mods_only):
        return True
    if config.subs_only and message.is_subscriber:
        return True
    if config.vip_only and message.is_vip:
        return True
    if config.mods_only and (message.is_moderator or message.is_broadcaster):
        return True
    return False


def find_blacklisted_word(text: str, blacklist: list[str]) -> str | None:
    """Returns the first blacklisted word/phrase found (case-insensitive
    substring match), or None."""
    lowered = text.lower()
    for word in blacklist:
        if word and word.lower() in lowered:
            return word
    return None


@dataclass
class CooldownTracker:
    """Per-username cooldown, kept in memory only — resets on app restart,
    which is fine since a cooldown is a live-session throttle, not a record
    worth persisting."""

    _last_use_monotonic: dict[str, float] = field(default_factory=dict)

    def check_and_record(self, username: str, cooldown_seconds: int, now: float | None = None) -> bool:
        """Returns True (allowed, and records this use) or False (still on
        cooldown, use not recorded)."""
        now = now if now is not None else time.monotonic()
        last = self._last_use_monotonic.get(username)
        if last is not None and (now - last) < cooldown_seconds:
            return False
        self._last_use_monotonic[username] = now
        return True
