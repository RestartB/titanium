import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import delete, select

from lib.sql.sql import AvailableWebhook, GuildSettings, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


# INFO - if we ever switch from 1 shard / autosharding, this will need a rewrite
class DataRetention(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("db")

        self.left_server_check.start()

    async def cog_unload(self) -> None:
        self.left_server_check.cancel()

    # Handle scanning after coming online
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        async with get_session() as session:
            stmt = select(GuildSettings).where(GuildSettings.leave_date.is_(None))
            servers = (await session.execute(stmt)).scalars().all()

            for server in servers:
                # skip if we are in the server still
                if self.bot.get_guild(server.guild_id) or server.leave_date:
                    continue

                # delete all stored webhooks - they are deleted from discord when titanium leaves anyway
                stmt = delete(AvailableWebhook).where(AvailableWebhook.guild_id == server.guild_id)
                await session.execute(stmt)

                # delete config or set leaver date
                if server.delete_after_3_days:
                    self.logger.info(
                        f"Left server while bot is offline - {server.guild_id}. Setting leave date."
                    )
                    server.leave_date = datetime.now(timezone.utc)
                else:
                    self.logger.info(
                        f"Left server while bot is offline - {server.guild_id}. Deleting config."
                    )
                    await self.bot.delete_guild_config(guild_id=server.guild_id)

    # Listen for Titanium rejoining servers
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            settings = await session.get(GuildSettings, guild.id)

            if settings and settings.leave_date:
                self.logger.info(f"Rejoined server - {guild.id}. Clearing leave date.")
                settings.leave_date = None

    # Listen for Titanium leaving servers
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        # guild isn't available, let's not touch it
        # could be a discord outage sending false events
        if guild.unavailable:
            return

        await self.bot.wait_until_ready()
        config = await self.bot.fetch_guild_config(guild.id, create_config=False)

        if not config:
            # no config to remove
            return

        async with get_session() as session:
            # delete all stored webhooks - they are deleted from discord when titanium leaves anyway
            stmt = delete(AvailableWebhook).where(AvailableWebhook.guild_id == guild.id)
            await session.execute(stmt)

            # delete config or set leaver date
            if config.delete_after_3_days:
                settings = await session.get(GuildSettings, guild.id)

                if not settings:
                    return

                self.logger.info(f"Left server - {guild.id}. Setting leave date.")
                settings.leave_date = datetime.now(timezone.utc)
                self.bot.remove_cached_config(guild_id=guild.id)
            else:
                self.logger.info(f"Left server - {guild.id}. Deleting config.")
                await self.bot.delete_guild_config(guild_id=guild.id)

    # Check for old servers
    @tasks.loop(hours=1)
    async def left_server_check(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            # get servers where we left more than 3 days ago
            stmt = select(GuildSettings).where(
                GuildSettings.leave_date <= datetime.now(timezone.utc) - timedelta(days=3)
            )
            old_servers = (await session.execute(stmt)).scalars().all()

            for server in old_servers:
                if self.bot.get_guild(server.guild_id):
                    # skip if we are still in the server
                    self.logger.info(f"Rejoined server {server.guild_id}. Clearing leave date.")
                    server.leave_date = None
                    continue

                self.logger.info(f"3 days passed for server {server.guild_id}. Deleting config.")
                await self.bot.delete_guild_config(guild_id=server.guild_id)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(DataRetention(bot))
