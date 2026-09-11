"""twitchio-based ChatSource implementation (twitchio 2.x's classic
token-authenticated IRC bot — see requirements.txt for why it's pinned
below 3.0). Just connects and forwards chat messages; parsing `!tts`,
filters and cooldowns all live in vocari.chat.filters, not here."""
from __future__ import annotations

from typing import Callable

from twitchio import Message
from twitchio.ext import commands

from vocari.chat.base import ChatMessage, ChatSource
from vocari.config.settings import TwitchConfig
from vocari.logging_setup import get_logger

logger = get_logger("twitch.source")


class TwitchChatSource(ChatSource):
    def __init__(self, config: TwitchConfig):
        self.config = config
        self._bot: commands.Bot | None = None

    async def start(
        self,
        on_message: Callable[[ChatMessage], None],
        on_connected: Callable[[], None] | None = None,
    ) -> None:
        channel = self.config.channel.strip().lstrip("#")

        class _Bot(commands.Bot):
            async def event_ready(self) -> None:
                logger.info("Twitch: подключено как %s к каналу %s", self.nick, channel)
                if on_connected:
                    on_connected()

            async def event_message(self, message: Message) -> None:
                if message.echo or message.author is None:
                    return
                author = message.author
                chat_message = ChatMessage(
                    username=author.name,
                    display_name=author.display_name or author.name,
                    text=message.content or "",
                    is_subscriber=bool(author.is_subscriber),
                    is_vip=bool(author.is_vip),
                    is_moderator=bool(author.is_mod),
                    is_broadcaster=bool(author.is_broadcaster),
                )
                on_message(chat_message)

        self._bot = _Bot(
            token=self.config.oauth_token,
            prefix="!",  # unused: we parse the configurable command_prefix ourselves
            initial_channels=[channel],
        )
        await self._bot.start()  # blocks until close()

    async def stop(self) -> None:
        if self._bot is not None:
            await self._bot.close()
