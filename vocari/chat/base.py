"""Generic chat-source abstraction. The `!tts` handling (filters, cooldown,
queue) is written against this interface, not against twitchio directly —
so a YouTube (or any other) chat source can plug in later without touching
that logic, per the spec's "не завязывайся жёстко на Twitch-специфику"."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class ChatMessage:
    username: str
    display_name: str
    text: str
    is_subscriber: bool = False
    is_vip: bool = False
    is_moderator: bool = False
    is_broadcaster: bool = False


class ChatSource(ABC):
    @abstractmethod
    async def start(
        self,
        on_message: Callable[[ChatMessage], None],
        on_connected: Callable[[], None] | None = None,
    ) -> None:
        """Connect and listen until stop() is called (or the connection
        drops) — blocks for the lifetime of the connection. `on_message` is
        called for every chat message (unfiltered — command parsing and
        filters live in vocari.chat.filters, not here). `on_connected`, if
        given, fires once the connection is actually confirmed (not just
        attempted) — e.g. after credentials are validated — so a caller can
        tell "connecting" from "connected" instead of assuming success."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect; makes the pending start() call return."""
