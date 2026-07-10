import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import select

from lib.enums.server_counters import ServerCounterType
from lib.helpers.log_error import log_error
from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import ServerCounterChannel, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCountersCog(commands.Cog):
    """Automatic task to update server counter channel names"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("counters")

    async def cog_load(self) -> None:
        # Start tasks
        self.channel_update.start()

    async def cog_unload(self) -> None:
        # Stop tasks on unload
        self.channel_update.cancel()

    # Channel update task
    @tasks.loop(minutes=15)
    async def channel_update(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            results = await session.execute(select(ServerCounterChannel))
            channels = results.scalars().all()

        cached_guilds: dict[int, discord.GuildPreview] = {}

        # TODO: run every server at once so we don't wait for chunking
        for count_channel in channels:
            self.logger.debug(f"Updating {count_channel.id}")
            guild = self.bot.get_guild(count_channel.guild_id)

            if not guild:
                self.logger.debug("No guild")
                continue

            guild_settings = await self.bot.fetch_guild_config(guild.id)
            if not guild_settings or not guild_settings.server_counters_enabled:
                self.logger.debug("Counters are disabled")
                continue

            discord_channel = guild.get_channel(count_channel.id)
            if not discord_channel or not isinstance(discord_channel, discord.VoiceChannel):
                self.logger.debug("Not a voice channel")
                continue

            members = list(guild.members)
            if (
                count_channel.count_type == ServerCounterType.USERS
                or count_channel.count_type == ServerCounterType.BOTS
            ) and not guild.chunked:
                self.logger.debug("Guild is not chunked and it is required, chunking")
                members = await guild.chunk()

            if (
                count_channel.count_type == ServerCounterType.ONLINE_MEMBERS
                or count_channel.count_type == ServerCounterType.OFFLINE_MEMBERS
            ):
                if guild.id not in cached_guilds:
                    self.logger.debug("Getting guild preview")
                    guild = await self.bot.fetch_guild_preview(guild.id)
                    cached_guilds[guild.id] = guild
                else:
                    self.logger.debug("Using cached guild preview")
                    guild = cached_guilds[guild.id]

            new_name = await resolve_counter(
                guild, count_channel.count_type, count_channel.name, members
            )

            if discord_channel.name == new_name:
                self.logger.debug("No updates to name")
                continue

            try:
                await discord_channel.edit(name=new_name, reason="Automated server counter update")
                self.logger.debug(f"Updated name: {new_name}")
            except discord.Forbidden as e:
                await log_error(
                    bot=self.bot,
                    module="Server Counters",
                    guild_id=guild.id,
                    error=f"Titanium was not allowed to update counter channel {discord_channel.name} ({discord_channel.id})",
                    details=e.text,
                    exc=e,
                )
            except discord.HTTPException as e:
                await log_error(
                    bot=self.bot,
                    module="Server Counters",
                    guild_id=guild.id,
                    error=f"Unknown Discord error while updating counter channel {discord_channel.name} ({discord_channel.id})",
                    details=e.text,
                    exc=e,
                )


async def setup(bot: TitaniumBot):
    await bot.add_cog(ServerCountersCog(bot))
