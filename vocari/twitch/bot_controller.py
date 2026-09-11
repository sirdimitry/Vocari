"""Runs the Twitch connection on a background thread — twitchio needs its
own asyncio event loop, separate from Qt's — and marshals incoming messages
and status changes back to the Qt main thread via signals (the same
cross-thread pattern used for logging in logging_setup.py)."""
from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QObject, Signal

from vocari.chat.base import ChatMessage
from vocari.config.settings import TwitchConfig
from vocari.logging_setup import get_logger
from vocari.twitch.twitch_source import TwitchChatSource

logger = get_logger("twitch.controller")


class TwitchBotController(QObject):
    message_received = Signal(object)  # ChatMessage
    status_changed = Signal(str, str)  # state: "connecting"|"connected"|"disconnected"|"error", detail

    def __init__(self, config: TwitchConfig):
        super().__init__()
        self.config = config
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._source: TwitchChatSource | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        self.status_changed.emit("connecting", "")
        self._thread = threading.Thread(target=self._run, name="twitch-bot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop is not None and self._source is not None:
            asyncio.run_coroutine_threadsafe(self._source.stop(), self._loop)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._source = TwitchChatSource(self.config)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as exc:  # noqa: BLE001 - surface any connection error to the UI
            logger.exception("Twitch: ошибка соединения")
            self.status_changed.emit("error", str(exc))
        else:
            self.status_changed.emit("disconnected", "")
        finally:
            self._loop.close()
            self._loop = None

    async def _main(self) -> None:
        def on_message(message: ChatMessage) -> None:
            self.message_received.emit(message)

        def on_connected() -> None:
            # Only fires once twitchio's event_ready confirms the token was
            # actually accepted — emitting "connected" any earlier would be
            # premature (e.g. a bad token still shows "connected" for a
            # moment before the auth error surfaces).
            self.status_changed.emit("connected", self.config.channel)

        assert self._source is not None
        await self._source.start(on_message, on_connected)
