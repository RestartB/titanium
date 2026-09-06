import logging
import os
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from discord.utils import utcnow

if TYPE_CHECKING:
    from main import TitaniumBot


class WatcherCog(commands.Cog):
    """Watcher to check if the bot has gotten stuck connecting while running"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("watcher")

        self.down_time: datetime | None = utcnow()
        self.has_connected: bool = False

    async def cog_load(self) -> None:
        self.time_checker.start()

    async def cog_unload(self) -> None:
        self.time_checker.cancel()

    @commands.Cog.listener()
    async def on_connect(self) -> None:
        self.down_time = None
        self.has_connected = True
        self.logger.debug("Bot has connected, clearing down time")

    @commands.Cog.listener()
    async def on_resumed(self) -> None:
        self.down_time = None
        self.has_connected = True
        self.logger.debug("Bot has resumed session, clearing down time")

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        if self.has_connected and not self.down_time:
            self.down_time = utcnow()
            self.logger.info("Bot has disconnected from socket, set down time")

    @tasks.loop(seconds=10)
    async def time_checker(self) -> None:
        if (
            not self.has_connected
            or not self.down_time
            or ((utcnow() - self.down_time) < timedelta(minutes=10))
        ):
            return

        self.logger.critical("Bot has been disconnected for over 10 minutes! Killing process")
        os._exit(1)


async def setup(bot: TitaniumBot):
    await bot.add_cog(WatcherCog(bot))
